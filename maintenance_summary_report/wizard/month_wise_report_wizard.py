# -*- coding: utf-8 -*-
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import models, fields, _

from .report_filter_mixin import CHARGE_LABELS, SECTOR_DOMAIN, UNIT_DOMAIN


class MonthWiseReportWizard(models.TransientModel):
    _name = 'month.wise.report.wizard'
    _inherit = 'maintenance.report.filter.mixin'
    _description = 'Month Wise Report Wizard'

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
    created_by = fields.Many2one('res.users')
    frequency = fields.Selection(
        string='Frequency',
        selection=[('more_than_three', 'More Than Three'),
                   ('less_than_three', 'Less Than Three')],
        required=False)
    month_wise = fields.Selection(
        string='Month Wise',
        selection=[('yes', 'Yes'),
                   ('no', 'No'), ], default='yes')

    maintenance_summary_xl_report = fields.Binary('Maintenance Summary Report Excel File')

    def generate_xlsx_report(self):
        """One row per unit and charge type: how much of each month's bill was paid."""
        self.ensure_one()
        items = self._report_items(self.from_date, self.to_date, self.created_by)

        months = []
        month = self.from_date.replace(day=1)
        while month <= self.to_date:
            months.append(month.strftime('%b-%Y'))
            month += relativedelta(months=1)

        rows = {}
        for item in items:
            invoice, kind = item['invoice'], item['kind']
            file = invoice.file_ids[:1]
            key = (file.id, kind)
            if key not in rows:
                rows[key] = dict(self._file_info(file), charge=CHARGE_LABELS.get(kind, ''),
                                 paid_count=0, unpaid_count=0, paid=0.0, unpaid=0.0, **{m: 0.0 for m in months})
            row = rows[key]
            row[invoice.invoice_date.strftime('%b-%Y')] += item['paid']
            row['paid'] += item['paid']
            row['unpaid'] += item['due']
            if item['due'] <= 0.005:
                row['paid_count'] += 1
            else:
                row['unpaid_count'] += 1

        columns = [('customer', 'Customer'), ('file', 'File'), ('sector', 'Sector'), ('street', 'Street'),
                   ('house_no', 'House No'), ('product', 'Product'), ('charge', 'Charge Type'),
                   ('paid_count', 'Paid Bills'), ('unpaid_count', 'Unpaid Bills'),
                   ('paid', 'Total Paid Amount'), ('unpaid', 'Total Unpaid Amount')] + [(m, m) for m in months]
        if not any(r['street'] for r in rows.values()):
            columns.remove(('street', 'Street'))
        ordered = sorted(rows.values(), key=lambda r: (r['sector'], r['house_no'], r['charge']))
        return self._xlsx_download('maintenance_summary_xl_report', _('Maintenance Month Wise Summary'), columns,
                                   ordered, money={'paid', 'unpaid', *months})
