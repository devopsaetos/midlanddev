from odoo import models,fields

class AccountAccountExt(models.Model):
    _inherit = 'account.account'

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False,    default=lambda self: self.env.company)
