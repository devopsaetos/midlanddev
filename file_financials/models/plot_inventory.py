# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree as ET


class PlotInventory(models.Model):
    _inherit = 'plot.inventory'
    _description = 'Plot Inventory'

    investor_file_id = fields.Many2one('investor.file', string='Investor File', tracking=True)
    file_id = fields.Many2one('file', string='File No.', tracking=True)

    # Mirrors investment.line.own_plan/predefine_plan_id (investment_lines.py) -
    # same per-line/per-unit plan-group key, but for deals reserved unit-by-unit
    # (reservation_type == 'unit') instead of in bulk.
    own_plan = fields.Boolean(default=False, string="Own Plan")
    predefine_plan_id = fields.Many2one('predefine.plan')
    booking_value = fields.Float(string="Booking")
    confirmation_value = fields.Float(string="Confirmation")
    posession_value = fields.Float(string="Posession")
    balloting_value = fields.Float(string="Balloting")
    final_value = fields.Float(string="Final")
    balloon_value = fields.Float(string="Balloon")

    @api.onchange('predefine_plan_id')
    def _onchange_predefine_plan_id(self):
        self.own_plan = bool(self.predefine_plan_id)

    @api.onchange('own_plan', 'predefine_plan_id', 'deal_price')
    def calculate_amount_and_values(self):
        # Same product-by-product math as investment.line.calculate_amount_and_values()
        # but without the * no_of_units multiplier - each plot.inventory row is
        # already exactly one unit.
        self.balloon_value = self.booking_value = self.confirmation_value = self.balloting_value = self.posession_value = self.final_value = 0
        if self.predefine_plan_id and self.deal_price > 0:
            for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:
                if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    self.booking_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    self.confirmation_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                if self.env.ref('real_estate.balloting_product').id == pre_plan.product_id.id:
                    self.balloting_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    self.posession_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                if self.env.ref("real_estate.final_product").id == pre_plan.product_id.id:
                    self.final_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                if self.env.ref("real_estate.balloon_payment").id == pre_plan.product_id.id:
                    self.balloon_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
