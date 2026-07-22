# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompanyMidlandInvoicing(models.Model):
    _inherit = 'res.company'

    rebate_expense_account_id = fields.Many2one(
        'account.account', string='Rebate Expense Account',
        help='Debited with the dealer rebate amount when a Booking payment '
             'is settled through the Investor/Dealer rebate flow.',
    )
    advance_from_dealer_account_id = fields.Many2one(
        'account.account', string='Advance from Dealer Account',
        help='Credited with cash collected + rebate (instead of Revenue) when '
             'a Booking invoice is settled through the Investor/Dealer rebate flow.',
    )
    dealer_clearance_advance_account_id = fields.Many2one(
        'account.account', string='Dealer Clearance Advance Account',
        help='Credited with the dealer rebate amount when a Dealer Confirmation '
             'is posted — the Confirmation-stage counterpart of the Booking '
             '"Advance from Dealer" account.',
    )
