# -*- coding: utf-8 -*-
from . import models

from .models.account_account import PAYABLE_TYPE, RECEIVABLE_TYPE


def _flag_existing_advance_accounts(env):
    """Flag the accounts already used for advances: by advance payments, and the companies'
    default advance accounts (incoming = customer advances, outgoing = supplier advances)."""
    payments = env['account.payment'].sudo().search(
        [('is_advance_payment', '=', True), ('advance_payment_account_id', '!=', False),
         ('state', 'in', ('in_process', 'paid'))])
    payments._flag_partner_advance_accounts()
    for company in env['res.company'].sudo().search([]):
        for account, side in ((company.advance_payment_outgoing_account_id, 'payable'),
                              (company.advance_payment_account_id, 'receivable')):
            if account and not account.partner_advance_type \
                    and account.account_type not in (PAYABLE_TYPE, RECEIVABLE_TYPE):
                account.partner_advance_type = side
