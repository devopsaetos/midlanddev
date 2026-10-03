from odoo import fields, models, api


class AccountMoveExt(models.Model):
    _inherit = 'account.move'

    maintenance_charges_id = fields.Many2one('maintenance.charges')

    property_invoice_type = fields.Selection(selection_add=[
        ('maintenance_charges', 'Maintenance Charges'),
        ('society_charges', 'Society/Service Charges'),
    ])
    is_maintenance_batch = fields.Boolean(default=False)


class AccountPaymentMaintenance(models.Model):
    _inherit = 'account.payment'

    def _maintenance_reconcile_invoices(self, invoices=None):
        """Match a posted maintenance payment with its invoices (oldest first).

        default_payment's multi-invoice payment only records the invoices in
        multi_invoice_ids; on Odoo 19 nothing reconciles them, so the invoices stayed
        unpaid although the payment was posted."""
        for payment in self.filtered(lambda p: p.move_id and p.move_id.state == 'posted'):
            invoices = invoices if invoices is not None else payment.multi_invoice_ids.mapped('invoice_id')
            for invoice in invoices.filtered(lambda m: m.state == 'posted').sorted(lambda m: (m.invoice_date or m.date, m.id)):
                pay_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
                if not pay_lines:
                    break
                inv_lines = invoice.line_ids.filtered(
                    lambda l: l.account_id in pay_lines.account_id and not l.reconciled)
                if inv_lines:
                    (pay_lines.filtered(lambda l: l.account_id in inv_lines.account_id) + inv_lines).reconcile()
