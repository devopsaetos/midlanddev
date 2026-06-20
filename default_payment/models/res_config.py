# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _get_default_advance_payment_account_id(self):
        return self.env.company.advance_payment_account_id

    @api.model
    def _get_default_advance_payment_outgoing_account_id(self):
        return self.env.company.advance_payment_outgoing_account_id

    @api.model
    def _get_default_advance_payment_journal_id(self):
        return self.env.company.advance_payment_journal_id

    @api.model
    def _get_default_clearing_account_id(self):
        return self.env.company.clearing_account_id

    @api.model
    def _get_default_discount_allowed_account_id(self):
        return self.env.company.discount_allowed_account_id

    @api.model
    def _get_default_discount_earned_account_id(self):
        return self.env.company.discount_earned_account_id

    advance_payment_account_id = fields.Many2one(
        'account.account',
        string='Incoming Advance Payment Account',
        default=_get_default_advance_payment_account_id,
        help="The account must be reconcilable")

    advance_payment_outgoing_account_id = fields.Many2one(
        'account.account',
        string='Outgoing Advance Payment Account',
        default=_get_default_advance_payment_outgoing_account_id,
        help="The account must be reconcilable")

    advance_payment_journal_id = fields.Many2one(
        'account.journal', 'Advance Payment Journal',
        default=_get_default_advance_payment_journal_id,
        help="""Default advance payment journal 
        for the current user's company.""")

    clearing_account_id = fields.Many2one(
        'account.account',
        string='Clearing Advance Payment Account',
        default=_get_default_clearing_account_id,
        help="The clearing account for advance payment")

    discount_allowed_account_id = fields.Many2one(
        'account.account',
        string='Discount Allowed Account',
        default=_get_default_discount_allowed_account_id,
        help="The discount allowed account for advance payment")

    discount_earned_account_id = fields.Many2one(
        'account.account',
        string='Discount Earned Account',
        default=_get_default_discount_earned_account_id,
        help="The discount earned account for advance payment")

    send_payment_sms = fields.Boolean(string="Send Payment SMS ?", related="company_id.send_payment_sms", readonly=False)

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        if self.advance_payment_account_id:
            self.env.company.sudo().advance_payment_account_id = self.advance_payment_account_id
        if self.advance_payment_outgoing_account_id:
            self.env.company.sudo().advance_payment_outgoing_account_id = self.advance_payment_outgoing_account_id
        if self.advance_payment_journal_id:
            self.env.company.sudo().advance_payment_journal_id = self.advance_payment_journal_id
        if self.clearing_account_id:
            self.env.company.sudo().clearing_account_id = self.clearing_account_id
        if self.discount_allowed_account_id:
            self.env.company.sudo().discount_allowed_account_id = self.discount_allowed_account_id
        if self.discount_earned_account_id:
            self.env.company.sudo().discount_earned_account_id = self.discount_earned_account_id
