# -*- coding: utf-8 -*-
from odoo import models, fields, _

from .report_filter_mixin import CHARGE_LABELS, SECTOR_DOMAIN, UNIT_DOMAIN


class MaintenancePaymentSummaryWizard(models.TransientModel):
    _name = 'maintenance.payment.summary.wizard'
    _inherit = 'maintenance.report.filter.mixin'
    _description = 'Maintenance Payment Summary Wizard'

    society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('society_id','=',society_id)]")
    sector_ids = fields.Many2many('sector', string='Sector', domain=SECTOR_DOMAIN)
    street_ids = fields.Many2many('street', string='Street', domain="[('sector_id', 'in', sector_ids)]")
    category_ids = fields.Many2many('plot.category', string='Category')
    unit_category_type_ids = fields.Many2many('unit.category.type', string="Product")
    # kept for old saved wizards; the report filters on charge_type
    product_id = fields.Many2one('product.product', string='Charge Product')
    inventory_ids = fields.Many2many('plot.inventory', domain=UNIT_DOMAIN)
    unit_class_id = fields.Many2one('unit.class', help='Empty = every unit class (Plot, House, ...).')
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    created_by = fields.Many2one('res.users', help='User who recorded the payment.')
    maintenance_payment_summary_xl = fields.Binary('Maintenance Summary Report Excel File')

    def generate_xlsx_report(self):
        """One row per payment and invoice it paid, for payments dated in the period."""
        self.ensure_one()
        rows = []
        invoices = self._report_invoices()
        charges = {(it['invoice'].id, it['kind']): it for it in invoices._maintenance_items()}
        for invoice, payment, date, kind, amount in invoices._maintenance_paid_parts():
            if not date or date < self.from_date or date > self.to_date:
                continue
            if self.charge_type and kind != self.charge_type:
                continue
            if self.created_by and (payment.create_uid if payment else False) != self.created_by:
                continue
            file = invoice.file_ids[:1]
            rows.append(dict(
                self._file_info(file),
                charge=CHARGE_LABELS.get(kind, ''),
                invoice=invoice.name,
                invoice_month=invoice.invoice_date and invoice.invoice_date.strftime('%b-%Y') or '',
                bill=invoice.ref or '',
                payment=payment.name if payment else '',
                payment_date=date.strftime('%d-%m-%Y'),
                journal=payment.journal_id.name if payment else '',
                invoice_amount=charges[(invoice.id, kind)]['amount'],
                paid=amount,
                due=charges[(invoice.id, kind)]['due'],
                state=dict(invoice._fields['payment_state']._description_selection(self.env)).get(invoice.payment_state, ''),
                created_by=payment.create_uid.name if payment else '',
                _sort=(date, invoice.name),
            ))
        rows.sort(key=lambda r: r.pop('_sort'))
        columns = [('customer', 'Customer'), ('file', 'File'), ('sector', 'Sector'), ('street', 'Street'),
                   ('house_no', 'House No'), ('product', 'Product'), ('charge', 'Charge Type'),
                   ('invoice', 'Invoice'), ('invoice_month', 'Bill Month'), ('bill', 'Bill No.'),
                   ('payment', 'Payment'), ('payment_date', 'Payment Date'), ('journal', 'Journal'),
                   ('invoice_amount', 'Charge Amount'), ('paid', 'Amount Paid'), ('due', 'Amount Due Now'),
                   ('state', 'Invoice Status'), ('created_by', 'Received By')]
        if not any(r['street'] for r in rows):
            columns.remove(('street', 'Street'))
        return self._xlsx_download('maintenance_payment_summary_xl', _('Maintenance Payments Summary'), columns,
                                   rows, money={'invoice_amount', 'paid', 'due'})
