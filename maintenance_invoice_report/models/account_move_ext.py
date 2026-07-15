from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MaintenanceChargesReport(models.Model):
    _inherit = 'account.move'

    def print_maintenance_charges_invoice(self):
        report = self.env.ref('maintenance_invoice_report.action_maintenance_invoice_report').report_action(self)
        return report
