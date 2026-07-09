# your_module/models/stock_picking.py
from odoo import models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_print_custom_delivery(self):
        self.ensure_one()

        if self.state == 'draft':
            raise UserError(_("Cannot print packing/delivery note for draft transfers. Please validate first."))

        return self.env.ref('western_custom_reports.action_report_packing_custom').report_action(self)