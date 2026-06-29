# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class MultiInvoicePaymentExt(models.Model):
    _inherit = "multi.invoice.payment"
    _description = "Multi Invoice Payment"

    payment_difference_handling = fields.Selection(selection_add=[('investor_adjustment', 'Adjust against Investor'), ('commission_adjustment','Adjust Commission')])
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account",
                                          domain="[('deprecated', '=', False)]", copy=False)

    @api.onchange('payment_difference_handling')
    def onchange_payment_difference_handling(self):
        if not self.payment_difference_handling:
            self.writeoff_account_id = False
        elif self.payment_difference_handling == 'advance_payment':
            self.write({'writeoff_account_id': self.env.company.clearing_account_id.id})
            print(self.writeoff_account_id)
        elif self.payment_difference_handling == 'investor_adjustment':
            self.write({'writeoff_account_id': self.env.company.clearing_account_id.id})
            print(self.writeoff_account_id)
        elif self.payment_difference_handling == 'commission_adjustment':
            self.write({'writeoff_account_id': self.env.company.commission_adjustment_account_id.id})
            print(self.writeoff_account_id)
