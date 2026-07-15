from odoo import fields, models, api


class AccountMoveExt(models.Model):
    _inherit = 'account.move'

    maintenance_charges_id = fields.Many2one('maintenance.charges')

    property_invoice_type = fields.Selection(selection_add=[('maintenance_charges', 'Maintenance Charges')])
    is_maintenance_batch = fields.Boolean(default=False)
