from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    invoice_ref_id = fields.Many2one('account.move')
