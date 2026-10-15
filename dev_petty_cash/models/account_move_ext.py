from odoo import api, fields, models, _


class AccountMoverExt(models.Model):
    _inherit = 'account.move'

    pc_expense_id = fields.Many2one('petty.cash.expense')