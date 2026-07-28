# -*- coding: utf-8 -*-
from odoo import fields, models


class InvestmentPaymentViewExt(models.Model):
    _inherit = 'investment.payment.view'

    midland_payment_id = fields.Many2one('midland.payment', string='Payment')
