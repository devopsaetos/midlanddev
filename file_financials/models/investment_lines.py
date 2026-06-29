import json
import base64
import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class InvestmentLineExt(models.Model):
    _inherit = 'investment.line'
    _description = 'Investment Line'

    booking_value = fields.Float(string="Booking")
    confirmation_value = fields.Float(string="Confirmation")
    posession_value = fields.Float(string="Posession")
    balloting_value = fields.Float(string="Balloting")
    final_value = fields.Float(string="Final")
    balloon_value = fields.Float(string="Balloon")
    own_plan = fields.Boolean(default=False, string="Own Plan")
    predefine_plan_id = fields.Many2one('predefine.plan')

    @api.onchange('own_plan', 'predefine_plan_id', 'deal_price')
    def calculate_amount_and_values(self):
        self.balloon_value = self.booking_value = self.confirmation_value = self.balloting_value = self.posession_value = self.final_value = 0
        if self.own_plan and self.predefine_plan_id and self.deal_price > 0:
            for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:
                if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    self.booking_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
                if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    self.confirmation_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
                # Balloting Calculation
                if self.env.ref('real_estate.balloting_product').id == pre_plan.product_id.id:
                    self.balloting_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
                if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    self.posession_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
                # Final Payment Installment Calculation
                if self.env.ref("real_estate.final_product").id == pre_plan.product_id.id:
                    self.final_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
                # Balloon Payment Installment Calculation
                if self.env.ref("real_estate.balloon_payment").id == pre_plan.product_id.id:
                    self.balloon_value = round(self.deal_price * (pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value * self.no_of_units)
