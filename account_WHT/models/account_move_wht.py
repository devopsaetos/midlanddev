# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)


class AccountMoveWHT(models.Model):
    _name = 'account.move.wht'
    _description = "Account Move WHT"

    name = fields.Char(string='Name', help='Name of the WHT line')  # Name
    account_id = fields.Many2one('account.account', string='WHT Account', help='Account used for Withholding Tax')  # WHT Account
    amount = fields.Monetary(string='Amount Deducted', help='Amount of Withholding Tax deducted')  # Amount Deducted
    move_id = fields.Many2one('account.move', string='Invoice', ondelete='cascade', help='Linked invoice for this WHT entry')  # Invoice
    currency_id = fields.Many2one('res.currency', related='move_id.currency_id', store=True, readonly=True, help='Currency of the invoice')  # Currency (related)
