# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InvestmentPlatter(models.Model):
    _name = 'investment.platter'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Investment Platter"

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    number = fields.Char('Number', required=True, copy=False, readonly=True, index=True,
                         default=lambda self: _('New'))
    name = fields.Char(tracking=True)
    investment_category_id = fields.Many2one('investment.category', string="Investment Category", required=True)
    society_id = fields.Many2one('society', 'Society', required=True,
                                 domain=[('is_society', '=', True)], tracking=True)
    phase_id = fields.Many2one('society', 'Phase', required=True, tracking=True)
    platter_line_ids = fields.One2many('investment.platter.line', 'investment_platter_id', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('number', _('New')) == _('New'):
                vals['number'] = (
                    self.env['ir.sequence'].next_by_code('investment.platter.sequence') or _('New')
                )
        return super().create(vals_list)


class InvestmentPlatterLines(models.Model):
    _name = 'investment.platter.line'
    _description = "Investment Platter Lines"

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    sector_id = fields.Many2one('sector')
    street_id = fields.Many2one('street')
    size_id = fields.Many2one('unit.size', 'Size', store=True,
                              related="inventory_id.size_id", readonly=False)
    unit_category_type_id = fields.Many2one('unit.category.type', store=True,
                                            related="inventory_id.unit_category_type_id", readonly=False)
    unit_class_id = fields.Many2one('unit.class', store=True,
                                    related="inventory_id.unit_class_id", readonly=False)
    category_id = fields.Many2one('plot.category', 'Category', store=True,
                                  related="inventory_id.category_id", readonly=False)
    inventory_id = fields.Many2one('plot.inventory')
    no_of_units = fields.Integer('No. of Units', default=1)
    list_price = fields.Float(store=True, compute='_sale_amount')
    price_list_id = fields.Many2one('price.list', compute='_price_list', store=True, readonly=False)
    investor_price = fields.Float(store=True, readonly=False)
    deal_price = fields.Float(compute='_compute_deal_price', store=True, readonly=False)
    booking_value = fields.Float(string="Booking")
    confirmation_value = fields.Float(string="Confirmation")
    posession_value = fields.Float(string="Posession")
    balloting_value = fields.Float(string="Balloting")
    final_value = fields.Float(string="Final")
    balloon_value = fields.Float(string="Balloon")
    own_plan = fields.Boolean(default=True, string="Own Plan")
    predefine_plan_id = fields.Many2one('predefine.plan')
    investment_platter_id = fields.Many2one('investment.platter')

    @api.depends('inventory_id')
    def _sale_amount(self):
        for rec in self:
            rec.list_price = rec.inventory_id.list_price if rec.inventory_id else 0.0

    @api.depends('investment_platter_id.society_id', 'investment_platter_id.phase_id')
    def _price_list(self):
        for rec in self:
            if rec.investment_platter_id.society_id and rec.investment_platter_id.phase_id:
                price_list = self.env['price.list'].search([
                    ('society_id', '=', rec.investment_platter_id.society_id.id),
                    ('phase_id', '=', rec.investment_platter_id.phase_id.id),
                ], limit=1)
                rec.price_list_id = price_list.id
            else:
                rec.price_list_id = False

    @api.depends('no_of_units', 'investor_price')
    def _compute_deal_price(self):
        for rec in self:
            rec.deal_price = rec.no_of_units * rec.investor_price

    @api.onchange('own_plan', 'predefine_plan_id', 'deal_price')
    def calculate_amount_and_values(self):
        if self.own_plan and self.predefine_plan_id and self.deal_price > 0:
            for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:
                if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    self.booking_value = round(
                        self.deal_price * (pre_plan.value / 100)
                        if pre_plan.basis == 'percentage'
                        else pre_plan.value * self.no_of_units
                    )
                if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    self.confirmation_value = round(
                        self.deal_price * (pre_plan.value / 100)
                        if pre_plan.basis == 'percentage'
                        else pre_plan.value * self.no_of_units
                    )
                if self.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                    self.balloting_value = round(
                        self.deal_price * (pre_plan.value / 100)
                        if pre_plan.basis == 'percentage'
                        else pre_plan.value * self.no_of_units
                    )
                if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    self.posession_value = round(
                        self.deal_price * (pre_plan.value / 100)
                        if pre_plan.basis == 'percentage'
                        else pre_plan.value * self.no_of_units
                    )
                if self.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                    self.final_value = round(
                        self.deal_price * (pre_plan.value / 100)
                        if pre_plan.basis == 'percentage'
                        else pre_plan.value * self.no_of_units
                    )

    @api.onchange('sector_id', 'street_id', 'category_id', 'unit_category_type_id')
    def _phase_domain(self):
        if self.street_id:
            return {'domain': {
                'inventory_id': [
                    ('street_id', '=', self.street_id.id),
                    ('state', '=', 'avalible_for_sale'),
                ],
            }}
        elif self.category_id and not self.unit_category_type_id:
            return {'domain': {
                'inventory_id': [
                    ('sector_id', '=', self.sector_id.id),
                    ('category_id', '=', self.category_id.id),
                    ('state', '=', 'avalible_for_sale'),
                ],
            }}
        elif self.category_id and self.unit_category_type_id:
            return {'domain': {
                'inventory_id': [
                    ('sector_id', '=', self.sector_id.id),
                    ('category_id', '=', self.category_id.id),
                    ('unit_category_type_id', '=', self.unit_category_type_id.id),
                    ('state', '=', 'avalible_for_sale'),
                ],
            }}
        else:
            return {'domain': {
                'sector_id': [('phase_id', '=', self.investment_platter_id.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'inventory_id': [
                    ('sector_id', '=', self.sector_id.id),
                    ('state', '=', 'avalible_for_sale'),
                ],
            }}
