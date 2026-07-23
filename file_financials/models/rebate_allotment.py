import json
import base64
import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class RebateOnAllotmentExt(models.Model):
    _inherit = 'rebate.on.allotment'
    _description = 'Rebate On Allotment'

    # relational fields
    investment_id = fields.Many2one('investment')
    partner_id = fields.Many2one('res.partner')
    agent_type = fields.Selection([('dealer', 'Dealer'), ('marketing_company', 'Marketing Company')], default="dealer", string="Agent Type", required=True,
                                  tracking=True)
    transaction_type = fields.Selection([('booking', 'Booking'), ('confirmation', 'Confirmation')], default="booking", string="Transaction Type", required=True,
                                        tracking=True)
    calculation_basis = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')], default="percentage", tracking=True)
    # Numerical fields
    marketing_rebate_percentage = fields.Float(tracking=True)
    dealer_rebate_percentage = fields.Float(tracking=True)
    rebate_amount = fields.Float(string='Rebate Amount', compute='compute_rebate_amount', store=True)
    rebate_given = fields.Float(string='Rebate Given')
    move_id = fields.Many2one('account.move', string="Entry #")

    def compute_rebate_amount(self):
        for rec in self:
            if rec.investment_id and rec.total_rebate > 0:
                if rec.calculation_basis == 'fix':
                    rec.rebate_amount = rec.total_rebate
                else:
                    # Percentage rebates apply against THIS line's own stage
                    # amount (Booking or Confirmation) — not the deal's whole
                    # total_amount, which inflated every line by the full
                    # unit count.
                    base_amount = (rec.investment_id.down_payment if rec.transaction_type == 'booking'
                                   else rec.investment_id.confirmation_amount)
                    rec.rebate_amount = base_amount * (rec.total_rebate / 100)
            else:
                rec.rebate_amount = 0
