from odoo import api, fields, models, _  # <--- Yahan '_' add kar diya hai

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_print_custom_pdf(self):
        return self.env.ref('western_custom_reports.action_report_sale_order_custom').report_action(self)
