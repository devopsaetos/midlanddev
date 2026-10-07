import re

from odoo import models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _get_payment_report_lines(self):
        """Bills/invoices settled by this payment with the amount it paid on each, for the
        Vendor Payment / Customer Receipt print: [{'move': account.move, 'paid': float}]."""
        self.ensure_one()
        paid = {}
        # Posted + reconciled: exact amount allocated to each bill.
        if self.move_id:
            partials, _exchange_moves = self.move_id._get_reconciled_invoices_partials()
            for _partial, amount, counterpart_line in partials:
                move = counterpart_line.move_id
                if move.is_invoice(include_receipts=True):
                    paid[move] = paid.get(move, 0.0) + amount
        # Not reconciled yet: fall back to the bills selected on the payment form.
        if not paid and 'multi_invoice_ids' in self._fields:
            for line in self.multi_invoice_ids.filtered('invoice_id'):
                paid[line.invoice_id] = paid.get(line.invoice_id, 0.0) + line.payment_amount
        if not paid:
            for move in self.invoice_ids | self.reconciled_bill_ids | self.reconciled_invoice_ids:
                paid.setdefault(move, 0.0)
        lines = [{'move': move, 'paid': amount} for move, amount in paid.items()]
        return sorted(lines, key=lambda l: (l['move'].invoice_date or l['move'].date, l['move'].id))

    def _get_payment_report_mode(self):
        """Mode of payment label (default_payment's field when installed)."""
        self.ensure_one()
        if 'mode_of_payments' in self._fields and self.mode_of_payments:
            return dict(self._fields['mode_of_payments']._description_selection(self.env)).get(self.mode_of_payments)
        return self.payment_method_line_id.name or ''

    def _get_payment_report_amount_words(self):
        """amount_to_text() always uses the singular unit label ("Rupee")."""
        self.ensure_one()
        text = self.currency_id.amount_to_text(self.amount)
        label = self.currency_id.currency_unit_label
        if label and int(round(abs(self.amount), 2)) != 1 and not label.endswith('s'):
            text = re.sub(r'\b%s\b' % re.escape(label), label + 's', text)
        return text
