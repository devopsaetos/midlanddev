from odoo import fields, models, api


class FileExt(models.Model):
    _inherit = 'file'

    maintenance_history_ids = fields.One2many('maintenance.charges.history', 'file_id')
    maintenance_recovery_agent_id = fields.Many2one('res.users', domain="[('maintenance_recovery_agent', '=', True)]")
    service_charge = fields.Boolean(string='Service charge', default=False)
    assumption = fields.Boolean(string='Assumption', default=False)
    exemption = fields.Boolean(string='Exemption', default=False)
