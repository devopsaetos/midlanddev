# -*- coding: utf-8 -*-
import base64
from io import BytesIO
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MaintenanceChargesWizard(models.TransientModel):
    _name = 'maintenance.charges.wizard'
    _description = 'Wizard to generate maintenance charges report'

    society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('society_id','=',society_id)]")
    sector_id = fields.Many2one('sector', string='Sector',
                                domain="phase_id and [('phase_id', '=', phase_id)] or (society_id and [('society_id', '=', society_id)] or [])")
    street_id = fields.Many2many('street', string='Street', domain="[('sector_id', '=', sector_id)]")
    category_ids = fields.Many2many('plot.category', string='Category')
    unit_category_type_ids = fields.Many2many('unit.category.type', string="Product")
    inventory_ids = fields.Many2many('plot.inventory', domain="street_id and [('street_id', 'in', street_id)] or (sector_id and [('sector_id', '=', sector_id)] or (society_id and [('society_id', '=', society_id)] or []))")
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    maintenance_xl_file = fields.Binary('EOBI Excel Report')
    file_name = fields.Char('File Name')

    def _invoice_domain(self):
        """Unpaid maintenance invoices of the filtered units in the period."""
        domain = [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
                  ('property_invoice_type', 'in', ('maintenance_charges', 'society_charges')),
                  ('payment_state', 'not in', ('paid', 'in_payment', 'reversed')),
                  ('invoice_date', '>=', self.from_date), ('invoice_date', '<=', self.to_date)]
        if self.society_id:
            domain.append(('file_ids.society_id', '=', self.society_id.id))
        if self.phase_id:
            domain.append(('file_ids.phase_id', '=', self.phase_id.id))
        if self.sector_id:
            domain.append(('file_ids.sector_id', '=', self.sector_id.id))
        if self.street_id:
            domain.append(('file_ids.street_id', 'in', self.street_id.ids))
        if self.category_ids:
            domain.append(('file_ids.category_id', 'in', self.category_ids.ids))
        if self.unit_category_type_ids:
            domain.append(('file_ids.unit_category_type_id', 'in', self.unit_category_type_ids.ids))
        if self.inventory_ids:
            # imported files are often not linked to their plot: match the plot number too
            domain += ['|', ('file_ids.inventory_id', 'in', self.inventory_ids.ids),
                       ('file_ids.unit_number', 'in', self.inventory_ids.mapped('name'))]
        return domain

    def process_pdf_report(self):
        """Print the unpaid invoices of the selected units with the invoice format
        (one page per invoice: Bank / Account / Customer copies)."""
        invoices = self.env['account.move'].with_context(
            allowed_company_ids=self.env.user.company_ids.ids).search(self._invoice_domain(), order='invoice_date, name')
        if not invoices:
            raise UserError(_('No unpaid maintenance invoices for the selected filters and dates.'))
        return self.env.ref('maintenance_invoice_report.action_maintenance_invoice_report').report_action(invoices)

    def process_excel_report(self):
        """One row per unit and charge: this period's bills, arrears before the period
        (imported Excel balances included) and the total to collect."""
        import xlsxwriter
        env = self.with_context(allowed_company_ids=self.env.user.company_ids.ids).env
        domain = [d for d in self._invoice_domain() if not (isinstance(d, tuple) and d[0] == 'payment_state')]
        invoices = env['account.move'].search(domain, order='invoice_date, name')
        labels = {'utility': _('Utility / Maintenance'), 'electricity': _('Electricity'), 'service': _('Service Charges')}
        rows = {}
        # one item per invoice and charge: a Monthly Bill invoice holds utility and electricity
        for item in invoices._maintenance_items():
            invoice, kind = item['invoice'], item['kind']
            file = invoice.file_ids[:1]
            if (file.id, kind) not in rows:
                plot = file.inventory_id or env['plot.inventory'].search(
                    [('name', '=', file.unit_number), ('society_id', '=', file.society_id.id)], limit=1)
                arrears = file._maintenance_arrears(kind, self.from_date) if kind in ('utility', 'electricity') else 0.0
                rows[(file.id, kind)] = {
                    'customer': file.membership_id.name or invoice.partner_id.name, 'society': file.society_id.name,
                    'phase': file.phase_id.name, 'sector': file.sector_id.name or plot.sector_id.name,
                    'street': file.street_id.name or plot.street_id.name, 'size': file.size_id.name or plot.size_id.name,
                    'house': file.unit_number or plot.name, 'charge': labels.get(kind, ''),
                    'bill': 0.0, 'arrears': arrears}
            rows[(file.id, kind)]['bill'] += item['due']
        if not rows:
            raise UserError(_('No maintenance invoices for the selected filters and dates.'))

        columns = [('customer', 'Customer'), ('society', 'Society'), ('phase', 'Phase'), ('sector', 'Sector'),
                   ('street', 'Street'), ('size', 'Size'), ('house', 'House No'), ('charge', 'Charge Type'),
                   ('bill', 'Current Bill (unpaid)'), ('arrears', 'Arrears'), ('total', 'Total Payable')]
        if not any(r['street'] for r in rows.values()):
            columns.remove(('street', 'Street'))
        fp = BytesIO()
        book = xlsxwriter.Workbook(fp, {'in_memory': True})
        sheet = book.add_worksheet('Maintenance Charges')
        title = book.add_format({'bold': True, 'font_size': 14, 'font_color': '#2B4C7E'})
        head = book.add_format({'bold': True, 'bg_color': '#E8EEF8', 'font_color': '#1F2A44', 'border': 1,
                                'border_color': '#C5CEE0', 'text_wrap': True})
        text = book.add_format({'border': 1, 'border_color': '#D9DEE8'})
        num = book.add_format({'border': 1, 'border_color': '#D9DEE8', 'num_format': '#,##0.00'})
        total = book.add_format({'bold': True, 'bg_color': '#F3F5F9', 'border': 1, 'border_color': '#C5CEE0',
                                 'num_format': '#,##0.00'})
        sheet.write(0, 0, _('Maintenance Invoices Summary'), title)
        sheet.write(1, 0, _('From %s to %s') % (self.from_date.strftime('%d-%m-%Y'), self.to_date.strftime('%d-%m-%Y')))
        sheet.write(3, 0, _('Sr#'), head)
        for col, (_key, label) in enumerate(columns, start=1):
            sheet.write(3, col, label, head)
            sheet.set_column(col, col, 22)
        ordered = sorted(rows.values(), key=lambda r: (r['sector'] or '', r['house'] or '', r['charge']))
        for idx, r in enumerate(ordered, start=1):
            r['total'] = r['bill'] + r['arrears']
            sheet.write(3 + idx, 0, idx, text)
            for col, (key, _label) in enumerate(columns, start=1):
                if key in ('bill', 'arrears', 'total'):
                    sheet.write_number(3 + idx, col, r[key], num)
                else:
                    sheet.write(3 + idx, col, r[key] or '', text)
        last = 4 + len(ordered)
        sheet.write(last, 0, _('Total'), total)
        for col, (key, _label) in enumerate(columns, start=1):
            if key in ('bill', 'arrears', 'total'):
                sheet.write_number(last, col, sum(r[key] for r in ordered), total)
            else:
                sheet.write(last, col, '', total)
        book.close()
        self.maintenance_xl_file = base64.b64encode(fp.getvalue())
        self.file_name = 'Maintenance Charges Report.xlsx'
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=maintenance.charges.wizard&field=maintenance_xl_file&download=true&id=%s&filename=%s' % (
                self.id, self.file_name),
        }
