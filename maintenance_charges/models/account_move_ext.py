import re

from odoo import fields, models, api, _


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

    # ------------------------------------------------------------------ payment receipt
    def _maintenance_invoice_kind(self, invoice):
        if invoice.property_invoice_type == 'maintenance_charges':
            return _('Utility')
        if invoice.property_invoice_type == 'society_charges':
            electricity = self.env['maintenance.charges.history'].sudo().search_count(
                [('invoice_id', '=', invoice.id), ('charge_type', '=', 'electricity')], limit=1)
            return _('Electricity') if electricity else _('Service Charges')
        return invoice.invoice_line_ids[:1].product_id.name or ''

    def _maintenance_receipt_values(self):
        """Values printed on the maintenance payment receipt."""
        self.ensure_one()
        # what this payment paid on each invoice (reconciliation); the amounts stored on
        # multi_invoice_ids are often 0
        paid = {}
        receivable = self.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        for partial in receivable.matched_debit_ids:
            invoice = partial.debit_move_id.move_id
            paid[invoice] = paid.get(invoice, 0.0) + partial.amount
        if not paid:
            for line in self.multi_invoice_ids.filtered('invoice_id'):
                paid[line.invoice_id] = paid.get(line.invoice_id, 0.0) + line.payment_amount
            if len(paid) == 1 and not sum(paid.values()):
                paid = {next(iter(paid)): self.amount}
        lines = [{
            'invoice': invoice,
            'kind': self._maintenance_invoice_kind(invoice),
            'month': invoice.invoice_date and invoice.invoice_date.strftime('%b-%Y') or '',
            'ref': invoice.ref or '',
            'amount': amount,
        } for invoice, amount in sorted(paid.items(), key=lambda kv: (kv[0].invoice_date or kv[0].date, kv[0].id))]

        file = self.file_id
        # everything still due on the file (imported Excel arrears included)
        far_future = fields.Date.to_date('9999-12-31')
        balance = sum(file.sudo()._maintenance_arrears(t, far_future) for t in ('utility', 'electricity')) if file else 0.0
        office = self.env['maintenance.charges.payment'].sudo().search([('payment_id', '=', self.id)], limit=1)
        modes = dict(office._fields['mode_of_payments']._description_selection(self.env))
        plot = file.inventory_id
        return {
            'lines': lines,
            'total': sum(l['amount'] for l in lines) or self.amount,
            'balance': balance,
            'file': file,
            'house_no': file.unit_number or plot.name or '',
            'size': file.size_id.name or plot.size_id.name or file.unit_category_type_id.name or '',
            'mode': modes.get(office.mode_of_payments) or self.journal_id.name,
            'reference': office.name if office else '',
            'remarks': office.remarks or self.memo or '',
            'amount_words': self._maintenance_amount_in_words(sum(l['amount'] for l in lines) or self.amount),
        }

    def _maintenance_amount_in_words(self, amount):
        """amount_to_text() always uses the singular unit label ("Rupee")."""
        text = self.currency_id.amount_to_text(amount)
        label = self.currency_id.currency_unit_label
        if label and int(round(abs(amount), 2)) != 1 and not label.endswith('s'):
            text = re.sub(r'\b%s\b' % re.escape(label), label + 's', text)
        return text
