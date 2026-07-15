# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class UnitSwapping(models.TransientModel):
    _name = 'unit.swapping'
    _description = "Unit Swapping"

    applicable_on = fields.Selection([
        ('investment', 'Investment'),
        ('file', 'File'),
    ])
    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('authorised_person', 'Authorised Person'),
        ('change_amount', 'Change Amount')
    ], default='swap')
    select_all = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    investment_id = fields.Many2one('investment')
    investor_file_id = fields.Many2one('investor.file')
    inventory_id = fields.Many2one('plot.inventory')
    file_id = fields.Many2one('file', 'File Number', domain="[('state','in',['cancel', 'refund'])]")
    membership_id = fields.Many2one('res.member', string='Member No')
    tracking_id = fields.Char('Tracking ID')
    member_id = fields.Char('Member ID')
    cnic = fields.Char('CNIC')
    unit_number = fields.Char('Unit Number')

    unit_swapping_line = fields.One2many('unit.swapping.line', 'unit_swapping_id')
    unit_swapping_investment_lines = fields.One2many('unit.swapping.investment.line', 'unit_swapping_id')
    reservation_type = fields.Selection([
        ('unit', 'Unit Reservation'),
        ('bulk', 'Bulk Reservation')
    ], related='investment_id.reservation_type')

    def search_related_records(self):
        self.unit_swapping_line.unlink()
        self.unit_swapping_investment_lines.unlink()

        if self.applicable_on == 'investment':
            if self.transaction_type == 'open_file':
                domain = []
                if self.investment_id:
                    domain.append(('investment_id', '=', self.investment_id.id))
                if self.investor_file_id and self.select_all == 'no':
                    domain.append(('id', '=', self.investor_file_id.id))
                domain.append(('state', '=', 'open'))
                # open_files = self.env['investor.file'].search([('investment_id', '=', self.investment_id.id), ('state', '=', 'open')])
                open_files = self.env['investor.file'].search(domain)
                for rec in open_files:
                    self.unit_swapping_investment_lines = [(0, 0, {
                        'check': True if self.select_all == 'yes' else False,
                        'transaction_type': self.transaction_type,
                        'investment_id': rec.investment_id.id if rec.investment_id else None,
                        'sector_id': rec.sector_id.id if rec.sector_id else None,
                        'category_id': rec.category_id.id if rec.category_id else None,
                        'unit_category_type_id': rec.unit_category_type_id.id if rec.unit_category_type_id else None,
                        'size_id': rec.size_id.id if rec.size_id else None,
                        'unit_class_id': rec.unit_class_id.id if rec.unit_class_id else None,
                        'inventory_id': rec.inventory_id.id if rec.inventory_id else None,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'unit_swapping_id': self.id
                    })]

        if self.file_id:
            self.unit_swapping_line = [(0, 0, {
                'file_id': self.file_id.id,
                'unit_swapping_id': self.id
            })]

        elif self.investment_id and self.transaction_type != 'open_file':
            # open_file lines are already added above; running this block too
            # would list every unit twice
            if self.reservation_type == 'unit':
                open_files = self.env['investor.file'].search(
                    [('inventory_id', 'in', self.investment_id.inventory_ids.ids), ('state', '=', 'open')])
                for rec in open_files:
                    self.unit_swapping_investment_lines = [(0, 0, {
                        'check': True if self.select_all == 'yes' else False,
                        'transaction_type': self.transaction_type,
                        'investment_id': self.investment_id.id,
                        'sector_id': rec.sector_id.id,
                        'category_id': rec.category_id.id,
                        'unit_category_type_id': rec.unit_category_type_id.id,
                        'size_id': rec.size_id.id,
                        'unit_class_id': rec.unit_class_id.id,
                        'inventory_id': rec.inventory_id.id,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'unit_swapping_id': self.id
                    })]
        # elif self.investor_file_id:
        #     open_files = self.env['investor.file'].search([('id', '=', self.investor_file_id.id)])
        #     for rec in open_files:
        #         self.unit_swapping_investment_lines = [(0, 0, {
        #             'check': True if self.select_all == 'yes' else False,
        #             'transaction_type': self.transaction_type,
        #             'investment_id': rec.investment_id.id,
        #             'sector_id': rec.sector_id.id,
        #             'category_id': rec.category_id.id,
        #             'unit_category_type_id': rec.unit_category_type_id.id,
        #             'size_id': rec.size_id.id,
        #             'unit_class_id': rec.unit_class_id.id,
        #             'inventory_id': rec.inventory_id.id,
        #             'investor_unit_price': rec.net_sale_amount,
        #             'investor_file_id': rec.id,
        #             'unit_swapping_id': self.id
        #         })]

        elif self.inventory_id and self.transaction_type != 'open_file':
            open_files = self.env['investor.file'].search(
                [('inventory_id', '=', self.investor_file_id.inventory_id.id), ('state', '=', 'open')])
            for rec in open_files:
                self.unit_swapping_investment_lines = [(0, 0, {
                    'check': True if self.select_all == 'yes' else False,
                    'transaction_type': self.transaction_type,
                    'investment_id': rec.investment_id.id,
                    'sector_id': rec.sector_id.id,
                    'category_id': rec.category_id.id,
                    'unit_category_type_id': rec.unit_category_type_id.id,
                    'size_id': rec.size_id.id,
                    'unit_class_id': rec.unit_class_id.id,
                    'inventory_id': rec.inventory_id.id,
                    'investor_unit_price': rec.net_sale_amount,
                    'investor_file_id': rec.id,
                    'unit_swapping_id': self.id
                })]

        if self.env.context.get('current_view', '') == 'buildings':
            view = self.env.ref('land_development.unit_swapping_search_form')
        else:
            view = self.env.ref('real_estate.unit_swapping_search_form')

        return {
            'context': self.env.context,
            'view_mode': 'form',
            'view_id': view.id,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def create_investment_request(self):
        if not any(self.unit_swapping_investment_lines.filtered(lambda l: l.check == True)):
            raise ValidationError("Please select the lines to proceed.")
        if self.applicable_on == 'investment':
            record = self.env['unit.swapping.request'].search([('investment_id', '=', self.investment_id.id)])

            # for rec in record:
            #     for line in self.unit_swapping_investment_lines.filtered(lambda l : l.check == True):
            #         if rec.transaction_type == line.transaction_type and rec.state != 'approve':
            #             raise ValidationError(
            #                 _("Request already generated of Investment and is in 'Draft' state : %s" % (record.investment_id.name)))

            swapping_units = self.unit_swapping_investment_lines.filtered(lambda l: l.transaction_type == 'swap' and l.check == True)
            if swapping_units:
                if len(swapping_units) != len(self.unit_swapping_investment_lines.mapped('new_inventory_id')):
                    raise ValidationError("Please select all the new units")
                record.create({
                    'applicable_on': self.applicable_on,
                    'investment_id': self.investment_id.id,
                    'project_type': self.investment_id.project_type,
                    'transaction_type': 'swap',
                    'unit_swapping_request_lines': [(0, 0,
                                                     {'check': True,
                                                      'transaction_type': rec.transaction_type,
                                                      'investment_id': rec.investment_id.id,
                                                      'sector_id': rec.sector_id.id,
                                                      'category_id': rec.category_id.id,
                                                      'unit_category_type_id': rec.unit_category_type_id.id,
                                                      'size_id': rec.size_id.id,
                                                      'unit_class_id': rec.unit_class_id.id,
                                                      'inventory_id': rec.inventory_id.id,
                                                      'investor_file_id': rec.investor_file_id.id,
                                                      'investor_unit_price': rec.investor_unit_price,
                                                      'new_inventory_id': rec.new_inventory_id.id,
                                                      }) for rec in swapping_units]
                })
                for rec in swapping_units:
                    rec.investor_file_id.state = 'in_process'

                return {
                    'name': _('Unit Swapping Request'),
                    'view_type': 'form',
                    'view_mode': 'list,form',
                    'res_model': 'unit.swapping.request',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'context': {
                        'current_view': 'realestate'
                    }
                }

            cancel_units = self.unit_swapping_investment_lines.filtered(lambda l: l.transaction_type == 'cancel' and l.check == True)
            if cancel_units:
                record.create({
                    'applicable_on': self.applicable_on,
                    'investment_id': self.investment_id.id,
                    'project_type': self.investment_id.project_type,
                    'transaction_type': 'cancel',
                    'cancel_all_units': True if all(self.unit_swapping_investment_lines.mapped('check')) else False,
                    'unit_swapping_request_lines': [(0, 0,
                                                     {'check': True,
                                                      'transaction_type': rec.transaction_type,
                                                      'investment_id': rec.investment_id.id,
                                                      'sector_id': rec.sector_id.id,
                                                      'category_id': rec.category_id.id,
                                                      'unit_category_type_id': rec.unit_category_type_id.id,
                                                      'size_id': rec.size_id.id,
                                                      'unit_class_id': rec.unit_class_id.id,
                                                      'inventory_id': rec.inventory_id.id,
                                                      'investor_file_id': rec.investor_file_id.id,
                                                      'investor_unit_price': rec.investor_unit_price,
                                                      'new_inventory_id': False,
                                                      }) for rec in cancel_units]
                })
                for rec in cancel_units:
                    rec.investor_file_id.state = 'in_process'

                return {
                    'name': _('Unit Cancel Request'),
                    'view_type': 'form',
                    'view_mode': 'list,form',
                    'res_model': 'unit.swapping.request',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'context': {
                        'current_view': 'realestate'
                    }
                }

            open_file_units = self.unit_swapping_investment_lines.filtered(lambda l: l.transaction_type == 'open_file' and l.check == True)
            if open_file_units and self.transaction_type == 'open_file':
                # record.create({
                # new_request = self.env['unit.swapping.request'].create({
                #     'applicable_on': self.applicable_on,
                #     'investment_id': self.investment_id.id,
                #     'society_id': self.investment_id.society_id.id,
                #     'phase_id': self.investment_id.phase_id.id,
                #     'project_type': self.investment_id.project_type,
                #     'transaction_type': 'open_file',
                #     'unit_swapping_request_lines': [(0, 0,
                #                                      {'check': True,
                #                                       'transaction_type': rec.transaction_type,
                #                                       'investment_id': rec.investment_id.id if rec.investment_id else None,
                #                                       'sector_id': rec.sector_id.id if rec.sector_id else None,
                #                                       'society_id': rec.investor_file_id.society_id.id if rec.investor_file_id.society_id else None,
                #                                       'category_id': rec.category_id.id if rec.category_id else None,
                #                                       'unit_category_type_id': rec.unit_category_type_id.id if rec.unit_category_type_id else None,
                #                                       'size_id': rec.size_id.id if rec.size_id else None,
                #                                       'unit_class_id': rec.unit_class_id.id if rec.unit_class_id else None,
                #                                       'inventory_id': rec.inventory_id.id if rec.inventory_id else None,
                #                                       'investor_unit_price': rec.investor_unit_price,
                #                                       'investor_file_id': rec.investor_file_id.id if rec.investor_file_id else None,
                #                                       'new_inventory_id': False,
                #                                       }) for rec in open_file_units]
                # })
                new_request_ids = []
                for rec in open_file_units:
                    new_request = self.env['unit.swapping.request'].create({
                        'applicable_on': self.applicable_on,
                        'appointment_date': fields.Date.today(),
                        'investment_id': rec.investment_id.id if rec.investment_id else None,
                        'society_id': rec.investment_id.society_id.id if rec.investment_id.society_id else None,
                        'phase_id': rec.investment_id.phase_id.id if rec.investment_id.phase_id else None,
                        'project_type': rec.investment_id.project_type,
                        'transaction_type': 'open_file',
                        'unit_swapping_request_lines': [(0, 0,
                                                         {'check': True,
                                                          'transaction_type': rec.transaction_type,
                                                          'investment_id': rec.investment_id.id if rec.investment_id else None,
                                                          'sector_id': rec.sector_id.id if rec.sector_id else None,
                                                          'society_id': rec.investor_file_id.society_id.id if rec.investor_file_id.society_id else None,
                                                          'category_id': rec.category_id.id if rec.category_id else None,
                                                          'unit_category_type_id': rec.unit_category_type_id.id if rec.unit_category_type_id else None,
                                                          'size_id': rec.size_id.id if rec.size_id else None,
                                                          'unit_class_id': rec.unit_class_id.id if rec.unit_class_id else None,
                                                          'inventory_id': rec.inventory_id.id if rec.inventory_id else None,
                                                          'investor_unit_price': rec.investor_unit_price,
                                                          'investor_file_id': rec.investor_file_id.id if rec.investor_file_id else None,
                                                          'new_inventory_id': False,
                                                          })]
                    })
                    rec.investor_file_id.state = 'in_process'
                    new_request_ids.append(new_request.id)
                if len(open_file_units) > 1:
                    return {
                        'name': _('File Issuance Requests'),
                        'res_model': 'unit.swapping.request',
                        'type': 'ir.actions.act_window',
                        'context': {
                            'current_view': 'realestate'
                        },
                        'view_type': 'form',
                        'view_mode': 'list,form',
                        # 'res_id': new_request.id,
                        'domain': [('id', 'in', new_request_ids)],
                        'target': 'self',
                    }
                else:
                    return {
                        'name': _('File Issuance Request'),
                        'res_model': 'unit.swapping.request',
                        'type': 'ir.actions.act_window',
                        'context': {
                            'current_view': 'realestate'
                        },
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': new_request_ids[0],
                        'domain': [('id', '=', new_request_ids[0])],
                        'target': 'self',
                    }

            change_amount_units = self.unit_swapping_investment_lines.filtered(
                lambda l: l.transaction_type == 'change_amount' and l.check == True)
            if not all(change_amount_units.mapped('new_price')):
                raise ValidationError("Please enter the new price in selected lines.")
            if change_amount_units:
                record.create({
                    'applicable_on': self.applicable_on,
                    'investment_id': self.investment_id.id,
                    'project_type': self.investment_id.project_type,
                    'transaction_type': 'change_amount',
                    'unit_swapping_request_lines': [(0, 0,
                                                     {'check': True,
                                                      'transaction_type': rec.transaction_type,
                                                      'investment_id': rec.investment_id.id,
                                                      'sector_id': rec.sector_id.id,
                                                      'category_id': rec.category_id.id,
                                                      'unit_category_type_id': rec.unit_category_type_id.id,
                                                      'size_id': rec.size_id.id,
                                                      'unit_class_id': rec.unit_class_id.id,
                                                      'inventory_id': rec.inventory_id.id,
                                                      'investor_unit_price': rec.investor_unit_price,
                                                      'new_price': rec.new_price,
                                                      'investor_file_id': rec.investor_file_id.id,
                                                      'new_inventory_id': False,
                                                      }) for rec in change_amount_units]
                })
                for rec in change_amount_units:
                    rec.investor_file_id.state = 'in_process'
                return {
                    'name': _('Change Amount Request'),
                    'view_type': 'form',
                    'view_mode': 'list,form',
                    'res_model': 'unit.swapping.request',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'context': {
                        'current_view': 'realestate'
                    }
                }


class UnitSwappingLine(models.TransientModel):
    _name = 'unit.swapping.line'
    _description = "Unit Swapping Line"

    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id')
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id')
    street_id = fields.Many2one('street', related='file_id.street_id')
    inventory_id = fields.Many2one('plot.inventory', related='file_id.inventory_id')
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='file_id.unit_category_type_id')
    unit_class_id = fields.Many2one('unit.class', related='file_id.unit_class_id')
    tracking_id = fields.Char(related='file_id.tracking_id')
    booking_date = fields.Date(related='file_id.booking_date')
    member_name = fields.Char(related='file_id.membership_id.name', readonly=True, string="Member Name")
    file_id = fields.Many2one('file', readonly=True)
    investment_id = fields.Many2one('investment', readonly=True)
    unit_swapping_id = fields.Many2one('unit.swapping')

    # New unit details
    new_inventory_id = fields.Many2one('plot.inventory')
    new_society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                     related='new_inventory_id.society_id')
    new_phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                                   related='new_inventory_id.phase_id')
    new_sector_id = fields.Many2one('sector', related='new_inventory_id.sector_id')
    new_category_id = fields.Many2one('plot.category', string='Plot Category', related='new_inventory_id.category_id')
    new_street_id = fields.Many2one('street', related='new_inventory_id.street_id')
    new_size_id = fields.Many2one('unit.size', 'Unit Size', related='new_inventory_id.size_id')
    new_unit_category_type_id = fields.Many2one('unit.category.type', related='new_inventory_id.unit_category_type_id')
    new_unit_class_id = fields.Many2one('unit.class', related='new_inventory_id.unit_class_id')
    new_membership_id = fields.Many2one('res.member', string='New Member No')

    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('member_swap', 'Member Swap')
    ], default='swap')
    appointment_date = fields.Datetime()

    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')

    relation_name = fields.Char()

    # Payment Plan
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    balloting_amount = fields.Float('Balloting Amount', related='file_id.balloting_amount')
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    change_price = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    amount = fields.Float()
    apply_charges = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    charges_amount = fields.Float()
    inventory_ids = fields.Many2many('plot.inventory', related='investment_id.inventory_ids')
    investment_line_ids = fields.One2many('investment.line', 'investment_id',
                                          related='investment_id.investment_line_ids')

    @api.onchange('apply_charges')
    def _calculate_charges(self):
        if not self.new_inventory_id:
            raise ValidationError('Please select new unit first.')

        if self.apply_charges == 'yes' and self.unit_swapping_id.applicable_on == 'file' and self.transaction_type == 'swap':
            charges_schedule = self.env['file.charges.schedule'].search([('applicable_on', '=', 'swap'),
                                                                         ('project_type', '=',
                                                                          self.file_id.project_type),
                                                                         ('society_id', '=', self.society_id.id),
                                                                         ('phase_id', '=', self.phase_id.id),
                                                                         ('date_from', '<=', fields.Date.today()),
                                                                         ('date_to', '>=', fields.Date.today())],
                                                                        limit=1)
            if not charges_schedule:
                raise ValidationError(
                    'No charges schedule found. Please create charges schedule or enter amount manually.')
            if charges_schedule.fee_calculation == 'fix':
                if charges_schedule.calculation_basis == 'marla':
                    self.charges_amount = round(
                        self.new_inventory_id.unit_category_type_id.area_marla * charges_schedule.amount)
                if charges_schedule.calculation_basis == 'sq_feet':
                    self.charges_amount = round(self.new_inventory_id.standard_area * charges_schedule.amount)
            elif charges_schedule.fee_calculation == 'variable':
                if charges_schedule.calculation_basis == 'marla':
                    charges_line = charges_schedule.charges_schedule_line_ids.filtered(lambda
                                                                                           l: self.new_inventory_id.unit_category_type_id.area_marla >= l.area_from and self.new_inventory_id.unit_category_type_id.area_marla <= l.area_to)
                    self.charges_amount = round(
                        self.new_inventory_id.unit_category_type_id.area_marla * charges_line.amount)
                if charges_schedule.calculation_basis == 'sq_feet':
                    charges_line = charges_schedule.charges_schedule_line_ids.filtered(lambda
                                                                                           l: self.new_inventory_id.standard_area >= l.area_from and self.new_inventory_id.standard_area <= l.area_to)
                    self.charges_amount = round(self.new_inventory_id.standard_area * charges_line.amount)

    def create_request(self):
        # if self.unit_swapping_id.applicable_on == 'file' and self.transaction_type == 'swap':
        if self.unit_swapping_id.applicable_on == 'file' and self.transaction_type:
            plans_invoice_created = self.file_id.installment_plan_ids.search(
                [('invoice_created', '=', True), ('file_id', '=', self.file_id.id)])
            # if True in self.installment_plan_ids.mapped('invoice_created'):
            # if 'not_paid' in plans_invoice_created.mapped('payment_status') or 'in_payment' in plans_invoice_created.mapped('payment_status'):
            #     raise ValidationError(
            #         _("Request could not process of this file while invoices are not fully paid."))
            record = self.env['unit.swapping.request'].search(
                [('file_id', '=', self.file_id.id), ('state', '=', 'draft')])
            if record and record.membership_id == self.membership_id:
                raise ValidationError(
                    _("Request already generated of file : %s" % (record.file_id.name)))
            else:
                record.create({
                    'applicable_on': self.unit_swapping_id.applicable_on,
                    'transaction_type': self.transaction_type,
                    'file_id': self.file_id.id,
                    'society_id': self.file_id.society_id.id,
                    'phase_id': self.file_id.phase_id.id,
                    'sector_id': self.file_id.sector_id.id,
                    'category_id': self.file_id.category_id.id,
                    'street_id': self.file_id.street_id.id,
                    'inventory_id': self.file_id.inventory_id.id,
                    'unit_number': self.file_id.inventory_id.name,
                    'size_id': self.file_id.size_id.id,
                    'unit_category_type_id': self.file_id.unit_category_type_id.id,
                    'unit_class_id': self.file_id.unit_class_id.id,
                    'project_type': self.file_id.project_type,
                    'appointment_date': self.appointment_date,
                    'new_inventory_id': self.new_inventory_id.id,
                    'change_price': self.change_price,
                    'amount': self.amount,
                    'apply_charges': self.apply_charges,
                    'charges_amount': self.charges_amount,
                    'membership_id': self.membership_id.id,
                    'new_membership_id': self.new_membership_id.id
                })
                self.file_id.state = 'inprocess'

                if self.file_id.project_type == 'skyscraper':
                    view = self.env.ref('land_development.unit_swapping_request_form')
                    domain = [('project_type', '=', 'skyscraper')]
                else:
                    view = self.env.ref('real_estate.unit_swapping_request_form')
                    domain = [('project_type', '=', 'housing_society')]

                return {
                    'name': _('Unit Swapping Request'),
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'unit.swapping.request',
                    'view_id': view.id,
                    'domain': domain,
                    'res_id': self.env['unit.swapping.request'].search(
                        [('file_id', '=', self.file_id.id), ('state', '=', 'draft')]).id,
                    'type': 'ir.actions.act_window',
                    'context': {
                        'current_view': 'realestate'
                    }
                }


class UnitSwappingInvestmentLines(models.TransientModel):
    _name = 'unit.swapping.investment.line'
    _description = 'Unit Swapping Investment Line'

    investment_id = fields.Many2one('investment')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Plot Category')
    inventory_id = fields.Many2one('plot.inventory', default=False)
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size')
    unit_category_type_id = fields.Many2one('unit.category.type')
    unit_class_id = fields.Many2one('unit.class')
    unit_swapping_id = fields.Many2one('unit.swapping')

    new_inventory_id = fields.Many2one('plot.inventory')
    check = fields.Boolean()
    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('change_amount', 'Change Amount')
    ], default='swap')
    investor_unit_price = fields.Float()
    new_price = fields.Float()
    investor_file_id = fields.Many2one('investor.file')
