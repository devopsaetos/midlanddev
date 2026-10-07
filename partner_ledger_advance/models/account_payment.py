# -*- coding: utf-8 -*-
from odoo import models

from .account_account import PAYABLE_TYPE, RECEIVABLE_TYPE


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _flag_partner_advance_accounts(self):
        """Flag the advance accounts of these advance payments for the partner reports
        (supplier advance -> payable side, customer advance -> receivable side)."""
        for payment in self.filtered(lambda p: p.is_advance_payment and p.advance_payment_account_id
                                     and p.state in ('in_process', 'paid')):
            account = payment.advance_payment_account_id.sudo()
            if account.partner_advance_type or account.account_type in (PAYABLE_TYPE, RECEIVABLE_TYPE):
                continue  # already read by the partner reports
            account.partner_advance_type = 'payable' if payment.partner_type == 'supplier' else 'receivable'

    def action_post(self):
        res = super().action_post()
        self._flag_partner_advance_accounts()
        return res
