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

    # Order in which a payment fills the charges of one invoice (a Monthly Bill posts utility
    # and electricity on the same invoice): utility first, then electricity, then the rest.
    MAINTENANCE_PAY_ORDER = ('utility', 'electricity', 'service')

    def _maintenance_parts_map(self):
        """{invoice id: [(kind, amount), ...]} in payment order. kind is 'utility',
        'electricity' or 'service'; a Monthly Bill invoice has one part per charge, read from
        its maintenance history rows. Other invoices are one part of their invoice type."""
        rows = self.env['maintenance.charges.history'].sudo().search([('invoice_id', 'in', self.ids)])
        by_invoice = {}
        for row in rows:
            by_invoice.setdefault(row.invoice_id.id, {}).setdefault(row.charge_type, 0.0)
            by_invoice[row.invoice_id.id][row.charge_type] += row.amount
        result = {}
        for move in self:
            amounts = by_invoice.get(move.id)
            if move.property_invoice_type not in ('maintenance_charges', 'society_charges'):
                result[move.id] = []
            elif amounts and len(amounts) > 1:
                result[move.id] = [(k, amounts[k]) for k in self.MAINTENANCE_PAY_ORDER if k in amounts]
            elif move.property_invoice_type == 'maintenance_charges':
                result[move.id] = [('utility', move.amount_total)]
            else:
                kind = 'electricity' if amounts and 'electricity' in amounts else 'service'
                result[move.id] = [(kind, move.amount_total)]
        return result

    @staticmethod
    def _maintenance_split(parts, start, amount):
        """Spread `amount` paid after `start` was already paid over the parts, in order.
        Returns {kind: amount}."""
        result = {}
        position = 0.0
        remaining = amount
        for kind, part in parts:
            free = max(min(part, position + part - start), 0.0)  # still unpaid in this part
            take = min(free, remaining)
            if take > 0:
                result[kind] = result.get(kind, 0.0) + take
                remaining -= take
            position += part
            if remaining <= 0:
                break
        if remaining > 0.005 and parts:  # overpayment: book it on the last part
            result[parts[-1][0]] = result.get(parts[-1][0], 0.0) + remaining
        return result

    def _maintenance_items(self):
        """One dict per invoice and charge: invoice, kind, amount, paid, due."""
        items = []
        parts_map = self._maintenance_parts_map()
        for move in self:
            parts = parts_map[move.id]
            paid = self._maintenance_split(parts, 0.0, move.amount_total - move.amount_residual)
            for kind, amount in parts:
                items.append({'invoice': move, 'kind': kind, 'amount': amount,
                              'paid': paid.get(kind, 0.0), 'due': amount - paid.get(kind, 0.0)})
        return items

    def _maintenance_paid_parts(self):
        """[(invoice, account.payment or False, date, kind, amount)] for every payment
        reconciled with these invoices, split per charge (utility first). The amounts on
        multi_invoice_ids are often 0, so read the reconciliation instead."""
        result = []
        parts_map = self._maintenance_parts_map()
        for move in self:
            receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            already = 0.0
            for partial in receivable.matched_credit_ids.sorted(lambda p: (p.max_date, p.id)):
                counterpart = partial.credit_move_id
                payment = counterpart.payment_id or counterpart.move_id.origin_payment_id
                date = payment.date if payment else counterpart.date
                for kind, amount in self._maintenance_split(parts_map[move.id], already, partial.amount).items():
                    result.append((move, payment, date, kind, amount))
                already += partial.amount
        return result

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
    MAINTENANCE_KIND_LABELS = {'utility': 'Utility', 'electricity': 'Electricity', 'service': 'Service Charges'}

    def _maintenance_receipt_values(self):
        """Values printed on the maintenance payment receipt."""
        self.ensure_one()
        labels = {k: _(v) for k, v in self.MAINTENANCE_KIND_LABELS.items()}
        # what this payment paid on each invoice and charge (reconciliation); the amounts
        # stored on multi_invoice_ids are often 0
        receivable = self.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        invoices = receivable.matched_debit_ids.debit_move_id.move_id
        paid = {}
        for invoice, payment, _date, kind, amount in invoices._maintenance_paid_parts():
            if payment == self:
                paid[(invoice, kind)] = paid.get((invoice, kind), 0.0) + amount
        if not paid:  # not reconciled (yet): fall back to the invoices recorded on the payment
            lines = self.multi_invoice_ids.filtered('invoice_id')
            parts_map = lines.invoice_id._maintenance_parts_map()
            for line in lines:
                amount = line.payment_amount or (self.amount if len(lines) == 1 else 0.0)
                split = self.env['account.move']._maintenance_split(parts_map[line.invoice_id.id], 0.0, amount)
                for kind, value in split.items():
                    paid[(line.invoice_id, kind)] = paid.get((line.invoice_id, kind), 0.0) + value
        order = {k: i for i, k in enumerate(self.env['account.move'].MAINTENANCE_PAY_ORDER)}
        lines = [{
            'invoice': invoice,
            'kind': labels.get(kind, ''),
            'month': invoice.invoice_date and invoice.invoice_date.strftime('%b-%Y') or '',
            'ref': invoice.ref or '',
            'amount': amount,
        } for (invoice, kind), amount in sorted(
            paid.items(), key=lambda kv: (kv[0][0].invoice_date or kv[0][0].date, kv[0][0].id, order.get(kv[0][1], 9)))]

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
