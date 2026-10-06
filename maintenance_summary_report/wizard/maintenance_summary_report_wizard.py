# -*- coding: utf-8 -*-
from odoo import models, fields, _

from .report_filter_mixin import CHARGE_LABELS


class MaintenanceSummaryReportWizard(models.TransientModel):
    _name = 'maintenance.summary.report.wizard'
    _inherit = 'maintenance.report.filter.mixin'
    _description = 'Maintenance Summary Report Wizard'

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date")
    society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    # kept for old saved wizards; the report filters on charge_type
    product_id = fields.Many2one('product.product', string='Charge Product')
    unit_class_id = fields.Many2one('unit.class', string="Type", help='Empty = every unit class (Plot, House, ...).')
    maintenance_summary_xl_report = fields.Binary('Maintenance Summary Report Excel File')

    def generate_report(self):
        """One row per unit and charge type: billed, paid and due in the period, plus the
        arrears brought forward from before it (imported Excel balances included)."""
        self.ensure_one()
        rows = {}
        for item in self._report_items(self.start_date, self.end_date):
            invoice, kind = item['invoice'], item['kind']
            file = invoice.file_ids[:1]
            key = (file.id, kind)
            if key not in rows:
                if kind in ('utility', 'electricity'):
                    arrears = file._maintenance_arrears(kind, self.start_date)
                else:
                    older = self._report_env()['account.move'].search([
                        ('file_ids', '=', file.id), ('state', '=', 'posted'), ('move_type', '=', 'out_invoice'),
                        ('property_invoice_type', '=', 'society_charges'), ('invoice_date', '<', self.start_date)])
                    arrears = sum(it['due'] for it in older._maintenance_items() if it['kind'] == 'service')
                rows[key] = dict(self._file_info(file), charge=CHARGE_LABELS.get(kind, ''),
                                 total=0.0, paid=0.0, due=0.0, arrears=arrears)
            row = rows[key]
            row['total'] += item['amount']
            row['paid'] += item['paid']
            row['due'] += item['due']
        for row in rows.values():
            row['total_due'] = row['due'] + row['arrears']

        columns = [('customer', 'Customer'), ('society', 'Society'), ('sector', 'Sector'), ('street', 'Street No'),
                   ('house_no', 'House No'), ('category', 'Category'), ('product', 'Product'), ('size', 'Size'),
                   ('type', 'Type'), ('charge', 'Charge Type'), ('total', 'Billed in Period'),
                   ('paid', 'Paid'), ('due', 'Due (Period)'), ('arrears', 'Arrears Before Period'),
                   ('total_due', 'Total Due')]
        if not any(r['street'] for r in rows.values()):
            columns.remove(('street', 'Street No'))
        ordered = sorted(rows.values(), key=lambda r: (r['society'], r['sector'], r['house_no'], r['charge']))
        return self._xlsx_download('maintenance_summary_xl_report', _('Maintenance Summary'), columns, ordered,
                                   money={'total', 'paid', 'due', 'arrears', 'total_due'})
