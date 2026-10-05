from collections import defaultdict
from datetime import timedelta

from odoo import models, api

# collection kind -> label (keys are the wizard's invoice_type values)
KINDS = {
    'maintenance_charges': 'Utility / Maintenance',
    'electricity': 'Electricity',
    'society_charges': 'Society / Service Charges',
}


class MaintenanceCollectionReport(models.AbstractModel):
    _name = 'report.maintenance_collection_report.maintenance_report_custom'
    _description = 'Maintenance Collection Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['maintenance.collection.report'].browse(docids or self.env.context.get('active_id'))

        # Collections of every company the user can see: the office collects for all
        # societies, whatever company is active in the switcher.
        Payment = self.env['account.payment'].with_context(allowed_company_ids=self.env.user.company_ids.ids)
        domain = [('state', 'in', ('in_process', 'paid')), ('file_id', '!=', False)]
        if docs.sector_id:
            domain.append(('file_id.sector_id', 'in', docs.sector_id.ids))
        if docs.category_ids:
            domain.append(('file_id.category_id', 'in', docs.category_ids.ids))
        if docs.unit_category_type_ids:
            domain.append(('file_id.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
        if docs.date_from:
            domain.append(('date', '>=', docs.date_from))
        if docs.date_to:
            domain.append(('date', '<=', docs.date_to))
        payments = Payment.search(domain, order='date, id')

        rows = []
        for payment in payments:
            for kind, amount in self._payment_allocations(payment).items():
                if docs.invoice_type and kind != docs.invoice_type:
                    continue
                rows.append({'payment': payment, 'file': payment.file_id, 'kind': KINDS[kind], 'amount': amount})

        months_list = []
        current_date = docs.date_from
        while current_date and docs.date_to and current_date <= docs.date_to:
            months_list.append(current_date.strftime('%b %Y'))
            current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        month_totals = defaultdict(float)
        for row in rows:
            month_totals[row['payment'].date.strftime('%b %Y')] += row['amount']

        # (id, name) rows / columns; files without a sector or product get their own line,
        # so the table always adds up to the grand total
        def axis(selected, records):
            if selected:
                return [(r.id, r.name) for r in selected.sorted('name')]
            keys = {(r.id, r.name) for r in records}
            return sorted(keys, key=lambda k: (not k[0], k[1] or ''))
        sectors = axis(docs.sector_id, [r['file'].sector_id for r in rows])
        sectors = [(k, n or 'No Sector') for k, n in sectors]
        products = axis(docs.unit_category_type_ids, [r['file'].unit_category_type_id for r in rows])
        products = [(k, n or 'No Product') for k, n in products]
        sector_product = defaultdict(float)
        for row in rows:
            sector_product[(row['file'].sector_id.id, row['file'].unit_category_type_id.id)] += row['amount']

        return {
            'docs': docs,
            'company': payments.company_id[:1] if len(payments.company_id) == 1 else docs.company_id or self.env.company,
            'rows': rows,
            'total': sum(r['amount'] for r in rows),
            'show_street': any(r['file'].street_id for r in rows),
            'invoice_type_label': KINDS.get(docs.invoice_type),
            'category_ids': docs.category_ids,
            'unit_category_type_ids': docs.unit_category_type_ids,
            'sector_id': docs.sector_id,
            'date_from': docs.date_from,
            'date_to': docs.date_to,
            'months_list': months_list,
            'month_totals': month_totals,
            'sectors': sectors,
            'products': products,
            'sector_product': sector_product,
        }

    @api.model
    def _invoice_kind(self, invoice):
        if invoice.property_invoice_type == 'maintenance_charges':
            return 'maintenance_charges'
        if invoice.property_invoice_type == 'society_charges':
            # Monthly Bills and the electricity invoice wizard book electricity as society
            # charges; their maintenance history row tells it apart from service charges.
            electricity = self.env['maintenance.charges.history'].sudo().search_count(
                [('invoice_id', '=', invoice.id), ('charge_type', '=', 'electricity')], limit=1)
            return 'electricity' if electricity else 'society_charges'
        return False

    @api.model
    def _payment_allocations(self, payment):
        """{kind: amount} of one payment, from what it actually paid on each invoice
        (reconciliation). The amounts stored on multi_invoice_ids are often 0."""
        result = defaultdict(float)
        receivable = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        for partial in receivable.matched_debit_ids:
            kind = self._invoice_kind(partial.debit_move_id.move_id)
            if kind:
                result[kind] += partial.amount
        if not receivable.matched_debit_ids:
            # not reconciled (yet): fall back to the invoices recorded on the payment
            lines = payment.multi_invoice_ids.filtered(lambda l: self._invoice_kind(l.invoice_id))
            if len(lines) == 1 and not lines.payment_amount:
                result[self._invoice_kind(lines.invoice_id)] += payment.amount
            else:
                for line in lines:
                    result[self._invoice_kind(line.invoice_id)] += line.payment_amount
        return {kind: amount for kind, amount in result.items() if amount}
