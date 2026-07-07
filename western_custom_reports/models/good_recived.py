from odoo import fields, models , api
from odoo.exceptions import UserError, ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def open_goods_received_report(self):
        return self.env.ref('western_custom_reports.good_received_report_action').report_action(self)

    def action_print_delivery_note(self):
        return self.env.ref('western_custom_reports.delivery_note_report_action').report_action(self)

    def action_print_pick_list(self):
        return self.env.ref('western_custom_reports.picking_list_report_action').report_action(self)

    def action_print_returns_report(self):
        return self.env.ref('western_custom_reports.returns_report_action').report_action(self)

    def action_print_packing_labels(self):
        return self.env.ref('western_custom_reports.packing_labels_report_action').report_action(self)