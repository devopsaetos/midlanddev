from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    maintenance_recovery_agent = fields.Boolean()