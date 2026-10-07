# -*- coding: utf-8 -*-
from odoo import fields, models

PAYABLE_TYPE = 'liability_payable'
RECEIVABLE_TYPE = 'asset_receivable'


class AccountAccount(models.Model):
    _inherit = 'account.account'

    partner_advance_type = fields.Selection(
        [('payable', 'Supplier advances'), ('receivable', 'Customer advances')],
        string='Advance Account (Partner Reports)',
        help='Advance payments are booked on this account instead of the partner\'s payable / '
             'receivable account. The Partner Ledger and the Aged Payable / Receivable reports read it '
             'with the payable (supplier advances) or receivable (customer advances) accounts, so '
             'unapplied advances show in the partner balances. Set automatically the first time an '
             'advance payment is posted on the account.')
