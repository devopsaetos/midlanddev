# -*- coding: utf-8 -*-
from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    advance_payment_account_id = fields.Many2one(
        'account.account',
        'Incoming Advance Payment Account')
    advance_payment_outgoing_account_id = fields.Many2one(
        'account.account',
        'Outgoing Advance Payment Account')
    advance_payment_journal_id = fields.Many2one(
        'account.journal',
        'Default Advance Payment Journal')

    clearing_account_id = fields.Many2one(
        'account.account',
        'The clearing account for advance payment')

    discount_allowed_account_id = fields.Many2one(
        'account.account',
        string='Discount Allowed Account',
        help="The discount allowed account for advance payment")

    discount_earned_account_id = fields.Many2one(
        'account.account',
        string='Discount Earned Account',
        help="The discount earned account for advance payment")

    send_payment_sms = fields.Boolean(string="Send Payment SMS ?", default=False)
