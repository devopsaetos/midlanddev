from odoo import api, models
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_print_custom_po_pdf(self):
        report_action = self.env.ref('western_custom_reports.action_report_purchase_custom')
        return report_action.report_action(self)