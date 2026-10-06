# -*- coding: utf-8 -*-
import base64
from datetime import datetime
from io import BytesIO

import xlsxwriter

from odoo import models, fields, _
from odoo.exceptions import UserError

CHARGE_TYPES = [
    ('utility', 'Utility / Maintenance'),
    ('electricity', 'Electricity'),
    ('service', 'Service Charges'),
]
CHARGE_LABELS = dict(CHARGE_TYPES)

# Every level is optional: Canal Valley has no streets and no unit is linked to every level.
SECTOR_DOMAIN = "phase_id and [('phase_id', '=', phase_id)] or (society_id and [('society_id', '=', society_id)] or [])"
UNIT_DOMAIN = ("street_ids and [('street_id', 'in', street_ids)] or (sector_ids and [('sector_id', 'in', sector_ids)]"
               " or (society_id and [('society_id', '=', society_id)] or []))")


class MaintenanceReportFilterMixin(models.AbstractModel):
    """Filters shared by the maintenance XLSX reports and the data they all start from:
    the files that match, their maintenance invoices and what was paid on them."""
    _name = 'maintenance.report.filter.mixin'
    _description = 'Maintenance Report Filters'

    charge_type = fields.Selection(CHARGE_TYPES, string='Charge Type', help='Empty = all charges.')

    # ------------------------------------------------------------------ data
    def _report_env(self):
        # The office reports on every society it manages, whatever company is active.
        return self.with_context(allowed_company_ids=self.env.user.company_ids.ids).env

    def _report_files(self):
        domain = []
        if 'society_id' in self and self.society_id:
            domain.append(('society_id', '=', self.society_id.id))
        if 'phase_id' in self and self.phase_id:
            domain.append(('phase_id', '=', self.phase_id.id))
        if 'sector_ids' in self and self.sector_ids:
            domain.append(('sector_id', 'in', self.sector_ids.ids))
        if 'street_ids' in self and self.street_ids:
            domain.append(('street_id', 'in', self.street_ids.ids))
        if 'category_ids' in self and self.category_ids:
            domain.append(('category_id', 'in', self.category_ids.ids))
        if 'unit_category_type_ids' in self and self.unit_category_type_ids:
            domain.append(('unit_category_type_id', 'in', self.unit_category_type_ids.ids))
        if self.unit_class_id:
            domain.append(('unit_class_id', '=', self.unit_class_id.id))
        if 'inventory_ids' in self and self.inventory_ids:
            # imported files are often not linked to their plot: match the plot number too
            domain += ['|', ('inventory_id', 'in', self.inventory_ids.ids),
                       ('unit_number', 'in', self.inventory_ids.mapped('name'))]
        return self._report_env()['file'].search(domain) if domain else False

    def _report_invoices(self, date_from=None, date_to=None, created_by=None):
        """Posted maintenance invoices of the filtered files."""
        files = self._report_files()
        domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                  ('property_invoice_type', 'in', ('maintenance_charges', 'society_charges'))]
        if files is not False:
            domain.append(('file_ids', 'in', files.ids))
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))
        if created_by:
            domain.append(('create_uid', '=', created_by.id))
        return self._report_env()['account.move'].search(domain, order='invoice_date, id')

    def _report_items(self, date_from=None, date_to=None, created_by=None):
        """One dict per invoice and charge (invoice, kind, amount, paid, due): a Monthly Bill
        invoice holds utility and electricity, so it gives two items."""
        items = self._report_invoices(date_from, date_to, created_by)._maintenance_items()
        return [it for it in items if not self.charge_type or it['kind'] == self.charge_type]

    @staticmethod
    def _file_info(file):
        plot = file.inventory_id or file.env['plot.inventory'].search(
            [('name', '=', file.unit_number), ('society_id', '=', file.society_id.id)], limit=1)
        return {
            'customer': file.membership_id.name or '',
            'file': file.display_name or '',
            'society': file.society_id.name or '',
            'sector': file.sector_id.name or plot.sector_id.name or '',
            'street': file.street_id.name or plot.street_id.name or '',
            'house_no': file.unit_number or plot.name or '',
            'category': file.category_id.name or '',
            'product': file.unit_category_type_id.name or '',
            'size': file.size_id.name or plot.size_id.name or '',
            'type': file.unit_class_id.name or '',
        }

    # ------------------------------------------------------------------ xlsx
    def _xlsx_download(self, field_name, title, columns, rows, money=()):
        """Write rows (list of dicts) to an XLSX stored in field_name and download it."""
        if not rows:
            raise UserError(_('No records found for the selected filters. Please widen your date range or filters and try again.'))
        buffer = BytesIO()
        book = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = book.add_worksheet(title[:31])
        head = book.add_format({'bold': True, 'bg_color': '#E8EEF8', 'font_color': '#1F2A44', 'border': 1,
                                'border_color': '#C5CEE0', 'text_wrap': True, 'valign': 'vcenter'})
        text = book.add_format({'border': 1, 'border_color': '#D9DEE8'})
        num = book.add_format({'border': 1, 'border_color': '#D9DEE8', 'num_format': '#,##0.00'})
        total = book.add_format({'bold': True, 'bg_color': '#F3F5F9', 'border': 1, 'border_color': '#C5CEE0',
                                 'num_format': '#,##0.00'})
        for col, (key, label) in enumerate(columns):
            sheet.write(0, col, label, head)
            width = max([len(str(label))] + [len('{:,.2f}'.format(r.get(key) or 0)) if key in money
                                             else len(str(r.get(key) or '')) for r in rows])
            sheet.set_column(col, col, min(max(width + 2, 8), 45))
        for row_idx, row in enumerate(rows, start=1):
            for col, (key, _label) in enumerate(columns):
                value = row.get(key)
                if key in money:
                    sheet.write_number(row_idx, col, value or 0.0, num)
                else:
                    sheet.write(row_idx, col, '' if value is None or value is False else value, text)
        last = len(rows) + 1
        sheet.write(last, 0, _('Total'), total)
        for col, (key, _label) in enumerate(columns):
            if key in money:
                sheet.write_number(last, col, sum(r.get(key) or 0.0 for r in rows), total)
            elif col:
                sheet.write(last, col, '', total)
        sheet.freeze_panes(1, 0)
        book.close()
        self[field_name] = base64.b64encode(buffer.getvalue())
        file_name = '%s - [%s].xlsx' % (title, datetime.now().strftime('%d-%m-%Y %I:%M:%S %p'))
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=%s&field=%s&download=true&id=%s&filename=%s' % (
                self._name, field_name, self.id, file_name),
        }
