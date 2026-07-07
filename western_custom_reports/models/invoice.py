from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_draft_duplicated_ref_ids = fields.Boolean(string="Is Draft Duplicated", default=False)

    def action_print_custom_invoice(self):
        self.ensure_one()
        return self.env.ref(
            'western_custom_reports.action_report_invoice_report_custom'
        ).report_action(self)

    def action_print_custom_bill(self):
        self.ensure_one()
        return self.env.ref(
            'western_custom_reports.action_report_vendor_bill_custom'
        ).report_action(self)

    def action_delete_duplicates(self):
        return True