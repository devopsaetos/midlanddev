import re

from odoo import models, api, _

# property_invoice_type -> (printed title, maintenance history charge type)
INVOICE_KINDS = {
    'maintenance_charges': ('Utility Invoice', 'utility'),
    'society_charges': ('Electricity Invoice', 'electricity'),
}


class MaintenanceChargesInvoiceReportModel(models.AbstractModel):
    _name = 'report.maintenance_invoice_report.maintenance_invoice_report'
    _description = 'Global Invoice Report'

    @api.model
    def _get_report_values(self, docids, data):
        records = self.env['account.move'].browse(docids)
        return {
            'data': data,
            'docs': records,
            'info': {move.id: self._invoice_info(move) for move in records},
        }

    def _invoice_info(self, move):
        """Everything the printed invoice shows that is not a plain field of the move.

        Invoices posted from a Monthly Bill take due date, arrears and meter readings from
        that bill, so the invoice prints the same figures as the bill."""
        title, charge_type = INVOICE_KINDS.get(move.property_invoice_type, ('Maintenance Invoice', False))
        file = move.file_ids[:1]
        bill = self.env['maintenance.bill'].search(
            ['|', ('utility_invoice_id', '=', move.id), ('electricity_invoice_id', '=', move.id)], limit=1)
        lines = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        month = move.invoice_date and move.invoice_date.strftime('%B %Y') or ''

        if bill:
            arrears = bill.arrears_electricity if charge_type == 'electricity' else bill.arrears_utility
        elif charge_type and file and move.invoice_date:
            arrears = file._maintenance_arrears(charge_type, move.invoice_date)
        else:
            arrears = 0.0

        electricity = False
        if charge_type == 'electricity':
            if bill:
                electricity = {
                    'previous': '%d' % bill.previous_reading,
                    'current': '%d' % bill.current_reading,
                    'units': '%d' % bill.units,
                    'rate': bill.unit_rate,
                }
            else:  # electricity invoice made outside Monthly Bills: no meter readings
                electricity = {
                    'previous': '-',
                    'current': '-',
                    'units': '%d' % sum(lines.mapped('quantity')),
                    'rate': lines[:1].price_unit,
                }

        member = file.membership_id
        current = move.amount_total
        return {
            'title': title,
            'charge_label': {'utility': _('Utility Charges'), 'electricity': _('Electricity Charges')}.get(charge_type),
            'month': month,
            'due_date': bill.due_date or move.invoice_date_due,
            'lines': lines,
            'current': current,
            'arrears': arrears,
            'total': current + arrears,
            'amount_words': self._amount_in_words(move.currency_id, current + arrears),
            'electricity': electricity,
            'phone': move.partner_id.phone or member.mobile or member.phone or member.secondary_phone or '',
            'house_no': file.unit_number or file.inventory_id.name or '',
            'size': file.size_id.name or file.unit_category_type_id.name or '',
            'address': [p for p in (move.company_id.street, move.company_id.street2, move.company_id.city) if p],
        }

    @api.model
    def _amount_in_words(self, currency, amount):
        """amount_to_text() always uses the singular unit label ("Rupee"): make it plural
        unless the amount is exactly one."""
        if not currency:
            return ''
        text = currency.amount_to_text(amount)
        label = currency.currency_unit_label
        if label and int(round(abs(amount), 2)) != 1 and not label.endswith('s'):
            text = re.sub(r'\b%s\b' % re.escape(label), label + 's', text)
        return text
