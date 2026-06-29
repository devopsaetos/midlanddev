from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class OpenFileAssignment(models.Model):
    _name = 'open.file.assignment'
    _description = 'Open File Assignment'

    # Char fields
    name = fields.Char('Serial Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    prefix = fields.Char(string='Prefix', related='prefix_id.prefix', store=True)
    prefix_id = fields.Many2one('unit.batch.generation.line')
    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    open_file_assignment_line_ids = fields.One2many('open.file.assignment.line', 'open_file_assignment_id')
    undo_assignment_line_ids = fields.One2many('undo.assignment.history', 'open_file_assignment_id')
    assignment_date = fields.Date(default=fields.Date.today())
    is_assignment_created = fields.Boolean(default=False)
    prefix_starting_number = fields.Char(related='prefix_id.starting_number')
    prefix_ending_number = fields.Char(related='prefix_id.ending_number')

    # @api.onchange('batch_id')
    # def deal_data_in_line(self):
    #     for rec in self:
    #         if rec.batch_id.deal_pack_id:
    #             rec.open_file_assignment_line_ids = [(0, 0, {
    #                 'sector_id': recs.sector_id.id,
    #                 'category_id': recs.category_id.id,
    #                 'unit_category_type_id': recs.unit_category_type_id.id,
    #             }) for recs in rec.batch_id.deal_pack_id.deal_pack_lines_ids]

    # @api.constrains('open_file_assignment_line_ids')
    # def _check_exist_number_in_line(self):
    #     ending_number_list = []
    #     starting_number_list = []
    #     for rec in self:
    #         for line in rec.open_file_assignment_line_ids:
    #             ending_number_list.append(line.unit_booking_ending_id.number)
    #
    #             starting_number_list.append(line.unit_booking_starting_id.number)
    #
    #             if (starting_number > line.unit_booking_ending_id.number for starting_number in starting_number_list):
    #                 raise ValidationError(_('Starting and Ending Number must have unique ranges in line'))
    #             if (ending_number < line.unit_booking_starting_id.number for ending_number in ending_number_list):
    #                 raise ValidationError(_('Starting and Ending Number must have unique ranges in line'))

    def create_jv(self, record):
        if self.env.company.unit_booking_journal_id:
            if not self.env.company.unit_booking_journal_id.profit_account_id:
                raise ValidationError(_("Please select profit account in selected journal"))
            if not self.env.company.unit_booking_journal_id.loss_account_id:
                raise ValidationError(_("Please select loss account in selected journal"))
            move = {
                'date': fields.Date.today(),
                'journal_id': self.env.company.unit_booking_journal_id.id,
                'company_id': self.env.company.id,
                'move_type': 'entry',
                'state': 'draft',
                'ref': record.sequence_number + '- ' + record.name,
                'units_booking_id': record.id,
                'line_ids': [(0, 0, {
                    'account_id': self.env.company.unit_booking_journal_id.profit_account_id.id,
                    'debit': record.initial_payment}),
                             (0, 0, {
                                 'account_id': self.env.company.unit_booking_journal_id.loss_account_id.id,
                                 'credit': record.initial_payment
                             })]
            }
            move_id = self.env['account.move'].create(move)

            move_id.action_post()
            record.jv_id = move_id.id
        else:
            raise ValidationError(_('Please Select Journal in configuration'))

    def file_assignment(self):
        unit_booking_record = self.env['units.booking']
        if not self.open_file_assignment_line_ids:
            raise ValidationError(_('Add at least one line before assignment'))
        for rec in self:
            for recs in rec.open_file_assignment_line_ids:
                data = unit_booking_record.search([('prefix_id', '=', rec.prefix_id.id),
                                                   ('batch_id', '=', rec.batch_id.id),
                                                   ('number', '>=', int(recs.unit_booking_starting_id.number)),
                                                   ('number', '<=', int(recs.unit_booking_ending_id.number)),
                                                   ('state', '=', 'open'),
                                                   ('sector_id', '=', False),
                                                   ('category_id', '=', False),
                                                   ('unit_category_type_id', '=', False),
                                                   ('unit_size_id', '=', False),
                                                   ('is_assigned', '=', False)
                                                   ])
                if data:
                    initial_payment = 0
                    if rec.batch_id.plan_type == 'custom':
                        if rec.batch_id.initial_payment_basis == 'percentage':
                            initial_payment = round((recs.unit_price * rec.batch_id.value), 2) / 100
                        if rec.batch_id.initial_payment_basis == 'fix':
                            initial_payment = rec.batch_id.value

                    for record in data:
                        record.write({
                            'booking_date': rec.batch_id.open_date,
                            'starting_date': rec.batch_id.installment_starting_date,
                            'sector_id': recs.sector_id.id,
                            'category_id': recs.category_id.id,
                            'unit_category_type_id': recs.unit_category_type_id.id,
                            'unit_size_id': recs.unit_size_id.id,
                            'predefine_plan_id': recs.predefine_plan_id.id,
                            'interval_id': recs.predefine_plan_id.interval_id.id,
                            'total_installment': recs.predefine_plan_id.total_installment,
                            "processing_fee": recs.processing_fee,
                            # 'plan_description': recs.predefine_plan_id.name,
                            'plan_type': rec.batch_id.plan_type,
                            'payment_type': rec.batch_id.payment_type,
                            'sale_amount': recs.unit_price,
                            'ttl_sale_amount': recs.unit_price,
                            'net_sale_amount': recs.unit_price,
                            'initial_payment': initial_payment,
                            'balance_amount': recs.unit_price - initial_payment if rec.batch_id.plan_type == 'custom' else 0.00,
                            'state': 'assignment',
                            'is_assigned': True,
                            'history_ids': [(0, 0, {
                                'state': 'assignment',
                                'print_state': '',
                                'date': fields.Date.today(),
                            })]
                        })
                        record._balloon_payment()
                        record.create_installment_plan()
                        self.create_jv(record)
                else:
                    raise ValidationError(_("No Record Found"))
                recs.is_assignment = True
            rec.is_assignment_created = True
        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Assignment of open file is done",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('prefix', False):
                vals['prefix'] = vals['prefix'].upper()
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('assignment.serial.code') or _('New')
        return super().create(vals_list)

    def file_selection(self):
        return {
            'name': _('Undo Assignment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'file.assignment.selection',
            'type': 'ir.actions.act_window',
            'context': {
                'default_assignment_id': self.id,
                'default_file_assignment_line_ids': [(0, 0, {
                    'open_file_assignment_line_id': rec.id,
                    'sector_id': rec.sector_id.id,
                    'category_id': rec.category_id.id,
                    'unit_category_type_id': rec.unit_category_type_id.id,
                    'batch_id': rec.batch_id.id,
                    'unit_booking_starting_id': rec.unit_booking_starting_id.id,
                    'unit_booking_ending_id': rec.unit_booking_ending_id.id,
                    'predefine_plan_id': rec.predefine_plan_id.id,
                    'unit_price': rec.unit_price,
                    'no_of_units': rec.no_of_units,
                }) for rec in self.open_file_assignment_line_ids.filtered(lambda l: not l.is_undo_assignment)]
            },
            'target': 'new'
        }


class OpenFileAssignmentLine(models.Model):
    _name = 'open.file.assignment.line'
    _description = 'Open File Assignment Line'

    # selection fields
    rate_type = fields.Selection([('per_marla', 'Per Marla'), ('per_unit', 'Per Unit')])
    # relational fields
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    unit_size_id = fields.Many2one('unit.size', 'Size')
    batch_id = fields.Many2one('unit.batch.generation')
    starting_number = fields.Integer(string="Starting Number", related='unit_booking_starting_id.number', store=True)
    ending_number = fields.Integer(string="Ending Number", related='unit_booking_ending_id.number', store=True)
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    open_file_assignment_id = fields.Many2one('open.file.assignment')
    predefine_plan_id = fields.Many2one('predefine.plan')
    processing_fee = fields.Float()
    prefix_id = fields.Many2one('unit.batch.generation.line', related='open_file_assignment_id.prefix_id', store=True)


    # numerical fields
    rate = fields.Float()
    unit_price = fields.Float()
    no_of_units = fields.Integer()
    deal_price = fields.Float()
    # boolean field
    is_undo_assignment = fields.Boolean(default=False)
    undo_date = fields.Date()

    @api.constrains('starting_number', 'ending_number')
    def duplicate_data(self):
        for rec in self:
            data = self.search([('prefix_id', '=', rec.prefix_id.id),
                                ('open_file_assignment_id', '=', rec.open_file_assignment_id.id),
                                ('starting_number', '<=', int(rec.unit_booking_ending_id.number)),
                                ('ending_number', '>=', int(rec.unit_booking_starting_id.number)),
                                ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('Each line must have unique prefix ranges'))

    # @api.onchange('category_id', 'sector_id')
    # def onchange_category_product(self):
    #     return {
    #         'domain': {
    #             'category_id': [('id', 'in',
    #                              self.open_file_assignment_id.batch_id.deal_pack_id.deal_pack_lines_ids.mapped(
    #                                  'category_id').ids)],
    #             'unit_category_type_id': [('id', 'in',
    #                                        self.open_file_assignment_id.batch_id.deal_pack_id.deal_pack_lines_ids.mapped(
    #                                            'unit_category_type_id').ids)],
    #             'sector_id': [('id', 'in',
    #                            self.open_file_assignment_id.batch_id.deal_pack_id.deal_pack_lines_ids.mapped(
    #                                'sector_id').ids)],
    #         }
    #     }

    @api.onchange('unit_category_type_id', 'rate_type', 'rate')
    def calculate_unit_price(self):
        for rec in self:
            if rec.open_file_assignment_id.batch_id.predefine_plan_id:
                rec.predefine_plan_id = rec.open_file_assignment_id.batch_id.predefine_plan_id.id
            if rec.batch_id.predefine_plan_id:
                rec.predefine_plan_id = rec.open_file_assignment_id.batch_id.predefine_plan_id.id
            if rec.rate_type == 'per_marla' and rec.unit_category_type_id:
                rec.unit_price = rec.rate * rec.unit_category_type_id.area_marla
            elif rec.rate_type == 'per_unit':
                rec.unit_price = rec.rate

    @api.onchange('unit_booking_starting_id', 'no_of_units', 'unit_booking_ending_id')
    def onchange_unit_booking_starting_id(self):
        for rec in self:
            # if rec.no_of_units > 0 and not rec.unit_booking_starting_id:
            #     next_number = rec.unit_booking_starting_id.number + rec.no_of_units
            #     return {
            #         'domain': {
            #
            #             'unit_booking_ending_id': [('number', '=', next_number)],
            #         }
            #     }

            if rec.unit_booking_starting_id and rec.no_of_units:
                data1 = self.env['units.booking'].search([
                    ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                    ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                    ('state', '=', 'open')], limit=1)
                if not data1:
                    raise ValidationError(_("Ending Number of the given quantity does not exist!"))
                rec.unit_booking_ending_id = data1.id

            if rec.unit_booking_starting_id and rec.unit_booking_ending_id and not rec.no_of_units:
                rec.no_of_units = (rec.unit_booking_ending_id.number - rec.unit_booking_starting_id.number) + 1

            if rec.unit_booking_starting_id and not rec.no_of_units:
                return {
                    'domain': {
                        'unit_booking_ending_id': [('number', '>', self.unit_booking_starting_id.number),
                                                   ('prefix_id', '=', self.unit_booking_starting_id.prefix_id.id),
                                                   ('state', '=', 'open')]
                    }
                }

    @api.constrains('unit_booking_starting_id', 'unit_booking_ending_id')
    def starting_and_ending_number(self):
        for rec in self:
            if not rec.unit_booking_starting_id:
                raise ValidationError(_('Enter starting number'))
            if not rec.unit_booking_ending_id:
                raise ValidationError(_('Enter ending number'))


class UndoAssignmentHistory(models.Model):
    _name = 'undo.assignment.history'
    _description = 'Undo Assignment History'

    # Char fields
    name = fields.Char('Serial Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    batch_id = fields.Many2one('unit.batch.generation')
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    open_file_assignment_id = fields.Many2one('open.file.assignment')
    undo_date = fields.Date()
    no_of_units = fields.Integer()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('undo.assignment.request.sequence') or _('New')
        return super().create(vals_list)
