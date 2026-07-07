from odoo import models

class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_print_batch_transfer_report(self):
        return self.env.ref('western_custom_reports.picking_list_report_action').report_action(self.picking_ids)