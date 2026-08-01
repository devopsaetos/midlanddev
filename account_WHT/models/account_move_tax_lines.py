from odoo import fields, models, api


class AccountMoveTaxLines(models.Model):
    _name = 'account.move.tax.lines'
    _description = 'Account Move Tax Lines'

    name = fields.Char(string='Name', help='Description of the tax line')  # Name
    tax_id = fields.Many2one('account.tax', string='Tax', help='Standard tax applied on this line')  # Tax
    wht_tax_id = fields.Many2one('account.wht', string='WHT Tax', help='Withholding tax applied on this line')  # WHT Tax
    account_id = fields.Many2one('account.account', string='Account', help='Account associated with this tax line')  # Account
    amount = fields.Float(string='Amount', help='Tax amount computed')  # Amount
    move_id = fields.Many2one('account.move', string='Move', help='Linked invoice or journal entry')  # Invoice / Move
