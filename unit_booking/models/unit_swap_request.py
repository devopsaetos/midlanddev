# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UnitBookingSwapRequest(models.Model):
    _name = "unit.booking.swap.request"
    _description = "Unit Swap Request"

    # Char fields
    name = fields.Char(copy=False, readonly=True, index=True, tracking=True, default=lambda self: _('New'))
    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    deal_pack_id = fields.Many2one('deal.pack')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment', string='Allotment')
    swap_request_line_ids = fields.One2many('unit.booking.swap.request.line', 'swap_request_id')
    agent_id = fields.Many2one('res.partner', string="Dealer")
    sub_agent_id = fields.Many2one('res.partner', string="Sub Dealer")
    # selection field
    transaction_type = fields.Selection([
        ('open_file', 'File Issuance'),
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('change_amount', 'Change Amount')])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    # Date fields
    request_date = fields.Date()

    def approve_request(self):
        for rec in self:
            if rec.transaction_type == 'swap':
                for recs in rec.swap_request_line_ids:
                    open_file = self.env['unit.booking.allotment.line'].search(
                        [('units_booking_id', '=', recs.units_booking_id.id),
                         ('unit_booking_allotment_id', '=', rec.unit_booking_allotment_id.id)])
                    open_file.units_booking_id.state = 'assignment'
                    open_file.units_booking_id.unit_booking_allotment_id = False
                    open_file.units_booking_id.agent_id = False
                    open_file.units_booking_id.sub_agent_id = False
                    open_file.sector_id = recs.new_units_booking_id.sector_id.id
                    open_file.phase_id = recs.new_units_booking_id.phase_id.id
                    open_file.category_id = recs.new_units_booking_id.category_id.id
                    open_file.society_id = recs.new_units_booking_id.society_id.id
                    open_file.unit_category_type_id = recs.new_units_booking_id.unit_category_type_id.id
                    open_file.batch_id = recs.new_units_booking_id.batch_id.id
                    open_file.price = recs.new_units_booking_id.sale_amount
                    open_file.units_booking_id = recs.new_units_booking_id.id
                    open_file.units_booking_id.unit_booking_allotment_id = rec.unit_booking_allotment_id.id
                    open_file.units_booking_id.agent_id = rec.unit_booking_allotment_id.partner_id.id
                    open_file.units_booking_id.sub_agent_id = rec.unit_booking_allotment_id.partner_subagent_id.id
                    open_file.units_booking_id.state = 'allotment'
                new_amount = sum(rec.unit_booking_allotment_id.unit_booking_allotment_line_ids.mapped('price'))
                plans = rec.unit_booking_allotment_id.booking_plan_ids.filtered(lambda l: not l.invoice_created)
                difference_amount = 0
                if rec.unit_booking_allotment_id.total_amount < new_amount:
                    difference_amount = new_amount - rec.unit_booking_allotment_id.total_amount
                    rec.unit_booking_allotment_id.balance_amount += difference_amount
                    rec.unit_booking_allotment_id.total_amount = (rec.unit_booking_allotment_id.balance_amount +
                                                                  rec.unit_booking_allotment_id.down_payment)
                    installment_amount = difference_amount / len(plans)
                    if installment_amount > 0:
                        for plan in plans:
                            plan.amount += installment_amount
                            plan.residual += installment_amount
                            plan.balance_amount += installment_amount
                elif rec.unit_booking_allotment_id.total_amount > new_amount:
                    difference_amount = rec.unit_booking_allotment_id.total_amount - new_amount
                    rec.unit_booking_allotment_id.balance_amount -= difference_amount
                    rec.unit_booking_allotment_id.total_amount = (rec.unit_booking_allotment_id.balance_amount +
                                                                  rec.unit_booking_allotment_id.down_payment)
                    installment_amount = difference_amount / len(plans)
                    if installment_amount > 0:
                        for plan in plans:
                            plan.amount -= installment_amount
                            plan.residual = plan.amount
                            plan.balance_amount -= installment_amount
            rec.state = 'approve'

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('unit.swap.request.sequence') or _('New')
        result = super().create(vals_list)
        return result


class UnitBookingSwapRequestLine(models.Model):
    _name = "unit.booking.swap.request.line"
    _description = "Unit Booking Swap Request Line"

    new_units_booking_id = fields.Many2one('units.booking')
    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product',
                                            related='units_booking_id.unit_category_type_id')
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id')
    swap_request_id = fields.Many2one('unit.booking.swap.request')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment', string='Allotment')

    # boolean fields
    is_checked = fields.Boolean(default=False)