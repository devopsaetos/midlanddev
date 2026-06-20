from odoo import models, fields


class AccountCostCenter(models.Model):
    _name = "account.cost.center"
    _description = "Account Cost Center"

    name = fields.Char(string="Title", required=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)