# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UnitBatchGeneration(models.Model):
    _name = "unit.batch.generation"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'batch_name'
    _description = "Unit Batch Generation"

    # selection fields
    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    state = fields.Selection([
        ('draft', 'Draft'), ('in_progress', 'In Progress'),
        ('close', 'Close')], default='draft',  tracking=True)
    launch_type = fields.Selection([
        ('pre_launch', 'Pre Launch'),
        ('on_launch', 'On Launch'),
        ('post_launch', 'Post Launch'),
    ],  tracking=True)

    # Char fields

    name = fields.Char('Serial Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))

    batch_name = fields.Char('Batch Name', tracking=True)

    # relational fields

    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]",
                                 tracking=True)
    phase_id = fields.Many2one('society', 'Phase',  tracking=True)
    deal_pack_id = fields.Many2one('deal.pack', domain="[('state','=','approve')]")
    batch_line_ids = fields.One2many('unit.batch.generation.line', 'batch_id', tracking=True)
    assignment_line_ids = fields.One2many('open.file.assignment', 'batch_id',  tracking=True)

    # date fields
    date = fields.Date(default=fields.Date.today(), tracking=True)
    open_date = fields.Date(default=fields.Date.today(),  tracking=True)
    close_date = fields.Date(default=fields.Date.today(),  tracking=True)

    #installment and payment details
    booking_date = fields.Date('Booking Date', default=fields.Date.today(), tracking=True)
    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')
    ], default='installments', string='Payment Type', tracking=True)
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ], default='custom',  tracking=True)
    predefine_plan_id = fields.Many2one('predefine.plan',  tracking=True)
    installment_created = fields.Boolean(default=False,  tracking=True)
    plan_description = fields.Char('Plan Description', store=True, readonly=False,  tracking=True)
    interval_id = fields.Many2one(
        'payment.interval',
        'Payment Interval', tracking=True)
    total_installment = fields.Integer('No of Installment',  tracking=True)
    initial_payment_basis =fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage'),
    ], default='percentage',  tracking=True)
    installment_starting_date = fields.Date('Installment Start Date', tracking=True)
    value = fields.Float(tracking=True)
    installment_start_date = fields.Date('Installments Start Date')

    def close_batch(self):
        for rec in self:
            rec.state = 'close'

    @api.constrains('open_date', 'close_date', 'total_installment')
    def check_validation(self):
        for rec in self:
            if rec.close_date < rec.open_date:
                raise ValidationError(
                    _("Close date can't be in past"))
            if rec.total_installment == 0:
                raise ValidationError(_("Number of installments can't be 0"))

    @api.onchange('deal_pack_id')
    def onchange_deal_pack(self):
        for rec in self:
            if rec.deal_pack_id:
                rec.launch_type = rec.deal_pack_id.launch_type

    @api.onchange('plan_type', 'predefine_plan_id')
    def onchange_plan_type(self):
        for rec in self:
            if rec.plan_type == 'predefine' and rec.predefine_plan_id:
                rec.plan_description = rec.predefine_plan_id.name
                rec.interval_id = rec.predefine_plan_id.interval_id.id
                rec.total_installment = rec.predefine_plan_id.total_installment

    @api.onchange('society_id', 'phase_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)]
            }
        }

    @api.constrains('name')
    def duplicate_data(self):
        for rec in self:
            data = self.search([('name', '=', rec.name), ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('Batch Number is already present.It must be unique.'))

    def view_open_file(self):
        tree_view = (self.env.ref('unit_booking.units_booking_view_tree').id, 'list')
        form_view = (self.env.ref('unit_booking.units_booking_view_form').id, 'form')
        return {
            'name': _('Unit'),
            'res_model': 'units.booking',
            'type': 'ir.actions.act_window',
            'context': {},
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'target': 'self'
        }

    def open_file_assignment(self):
        tree_view = (self.env.ref('unit_booking.open_file_assignment_view_tree').id, 'list')
        form_view = (self.env.ref('unit_booking.open_file_assignment_view_form1').id, 'form')
        return {
            'name': _('Batch Assignment'),
            'res_model': 'open.file.assignment',
            'type': 'ir.actions.act_window',
            'context': {'default_batch_id': self.id},
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'target': 'self'
        }

    def create_batch(self):
        file_booking = self.env["units.booking"]
        for recs in self:
            if not recs.batch_line_ids:
                raise ValidationError(
                    _("Add at least one line before creating open file"))

            line_record = recs.batch_line_ids.filtered(lambda attribute: attribute.selected_line and not attribute.line_created)
            if not line_record:
                raise ValidationError(_("Please Select any line before creating open file"))

            for line in line_record:
                for rec in range(int(line.starting_number), int(line.ending_number) + 1):
                    file_booking.create({
                        "name": line.prefix + '{:07d}'.format(rec),
                        "batch_id": recs.id,
                        "prefix": line.prefix,
                        "prefix_id": line.id,
                        "number": rec,
                        "state": 'open',
                        "society_id": recs.society_id.id,
                        "phase_id": recs.phase_id.id,
                        "sector_id": line.sector_id.id,
                        "category_id": line.category_id.id,
                        "unit_category_type_id": line.unit_category_type_id.id,
                        "project_type": recs.project_type,
                        "history_ids": [(0, 0, {
                            'state': 'open',
                            'print_state':
                                '',
                            'date': fields.Date.today(),
                            'batch_id': recs.id
                        })]
                    })
                line.line_created = True
            recs.state = 'in_progress'

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Batch of open file booking is created",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    def unlink(self):
        for rec in self:
            if rec.state in ['in_progress', 'close']:
                raise ValidationError("You can't delete a batch because state is not in draft.")
        return super(UnitBatchGeneration, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('batch.serial.code') or _('New')
        return super().create(vals_list)

    @api.depends('name', 'batch_name')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.name and record.name != 'New':
                name = "%s / %s" % (record.batch_name, record.name)
            result.append((record.id, name))
        return result


class UnitBatchGenerationLine(models.Model):
    _name = "unit.batch.generation.line"
    _description = "Unit Batch Generation Line"
    _rec_name = 'prefix'

    # relational fields

    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', 'Category')
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product')
    batch_id = fields.Many2one('unit.batch.generation')

    # char fields
    prefix = fields.Char(string='Prefix')

    # numerical fields
    starting_number = fields.Char()
    ending_number = fields.Char()
    total = fields.Integer(compute='_calculate_total')
    with_out_assignment = fields.Integer(compute='_compute_with_out_assignment')

    # boolean fields
    selected_line = fields.Boolean(default=False)
    line_created = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('prefix', False):
                vals['prefix'] = vals['prefix'].upper()
            if vals.get('starting_number', False):
                starting_number = vals['starting_number']
                vals['starting_number'] = '{:07d}'.format(int(starting_number))
            if vals.get('ending_number', False):
                ending_number = vals['ending_number']
                vals['ending_number'] = '{:07d}'.format(int(ending_number))
        return super().create(vals_list)

    @api.depends('starting_number', 'ending_number')
    def _calculate_total(self):
        for rec in self:
            starting_number = int(rec.starting_number)
            ending_number = int(rec.ending_number)
            if starting_number and ending_number:
                rec.total = (ending_number - starting_number) + 1
            else:
                rec.total = 0

    @api.depends('prefix')
    def _compute_with_out_assignment(self):
        for rec in self:
            rec.with_out_assignment = self.env['units.booking'].search_count([('batch_id', '=', rec.batch_id.id),
                                                                              ('is_assigned', '=', False),
                                                                              ('prefix_id', '=', rec.id),
                                                                              ('number', '<=', int(rec.ending_number)),
                                                                              ('number', '>=', int(rec.starting_number))
                                                                              ])

    @api.constrains('starting_number', 'ending_number')
    def check_starting_and_ending(self):
        for recs in self:
            if int(recs.ending_number) < int(recs.starting_number):
                raise ValidationError(
                    _("Ending Number Can't be less than starting number."))
            if int(recs.starting_number) < 0:
                raise ValidationError(
                    _("Starting number can't be less than 0"))

    @api.constrains('prefix')
    def duplicate_data(self):
        for rec in self:
            data = self.search([('prefix', '=', rec.prefix),
                                ('starting_number', '<=', rec.ending_number),
                                ('ending_number', '>=', rec.starting_number),
                                ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('Sequence with this prefix is already exist'))

    def unlink(self):
        for rec in self:
            if rec.line_created:
                raise ValidationError("You can't delete a line because open file created against this.")
        return super(UnitBatchGenerationLine, self).unlink()
