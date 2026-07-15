# -*- coding: utf-8 -*-
import base64
from io import BytesIO
import xlwt  # Odoo 19: xlwt is imported directly (odoo.tools.misc no longer re-exports it,
             # it is patched at import time via odoo/_monkeypatches/xlwt.py)
from odoo import api, fields, models, _


class MaintenanceChargesWizard(models.TransientModel):
    _name = 'maintenance.charges.wizard'
    _description = 'Wizard to generate maintenance charges report'

    society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('society_id','=',society_id)]")
    sector_id = fields.Many2one('sector', string='Sector', domain="[('phase_id','=',phase_id)]")
    street_id = fields.Many2many('street', string='Street', domain="[('sector_id', '=', sector_id)]")
    category_ids = fields.Many2many('plot.category', string='Category')
    unit_category_type_ids = fields.Many2many('unit.category.type', string="Product")
    inventory_ids = fields.Many2many('plot.inventory', domain="[('street_id','in',street_id)]")
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    maintenance_xl_file = fields.Binary('EOBI Excel Report')
    file_name = fields.Char('File Name')

    def process_pdf_report(self):
        data = {
            'society_id': self.society_id,
            'phase_id': self.phase_id,
            'sector_id': self.sector_id,
            'street_id': self.street_id,
            'category_ids': self.category_ids,
            'unit_category_type_ids': self.unit_category_type_ids,
            'inventory_ids': self.inventory_ids,
        }
        return self.env.ref("maintenance_invoice_report.action_society_maintenance_charges_report").report_action(self,
                                                                                                                  data=data)

    def process_excel_report(self):
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Maintenance Charges Excel Report', cell_overwrite_ok=True)
        heading_style = xlwt.easyxf(
            'font: bold on,height 300;align: wrap on,vert centre, horiz center; align: wrap yes,vert centre, horiz center;pattern: pattern solid, fore-colour aqua;')
        table_heading_style = xlwt.easyxf(
            'font: bold on,height 220;align: wrap on,vert centre, horiz center; align: wrap yes,vert centre, horiz center;pattern: pattern solid, fore-colour gray25;border: left thin,right thin,top thin,bottom thin')
        columns_right_bold_style = xlwt.easyxf(
            'font: height 200;align: wrap on,vert centre, horiz right; align: wrap yes,vert centre;')

        '''set the Columns Width '''

        zero_col = worksheet.col(0)
        zero_col.width = 256 * 25
        first_col = worksheet.col(1)
        first_col.width = 256 * 30
        second_col = worksheet.col(2)
        second_col.width = 256 * 25
        third_col = worksheet.col(3)
        third_col.width = 256 * 20
        fourth_col = worksheet.col(4)
        fourth_col.width = 256 * 25
        fifth_col = worksheet.col(5)
        fifth_col.width = 256 * 20
        sixth_col = worksheet.col(6)
        sixth_col.width = 256 * 20
        seven_col = worksheet.col(7)
        seven_col.width = 256 * 25
        eighth_col = worksheet.col(8)
        eighth_col.width = 256 * 25
        ninth_col = worksheet.col(9)
        ninth_col.width = 256 * 25
        tenth_col = worksheet.col(10)
        tenth_col.width = 256 * 25

        sr = 1
        for wizard in self:
            pass

        '''This is the Table Headings'''
        worksheet.write_merge(1, 2, 2, 7, _('Maintenance Invoices Summary').upper(), heading_style)
        worksheet.write_merge(4, 4, 0, 0, _('Date From').upper(), table_heading_style)
        worksheet.write_merge(4, 4, 8, 8, _('Date To').upper(), table_heading_style)
        worksheet.write_merge(4, 4, 1, 1, _(self.from_date), table_heading_style)
        worksheet.write_merge(4, 4, 9, 9, _(self.to_date), table_heading_style)
        worksheet.write_merge(6, 6, 0, 0, _('Sr#').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 1, 1, _('Customer').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 2, 2, _('Society').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 3, 3, _('Phase').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 4, 4, _('Sector').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 5, 5, _('Street').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 6, 6, _('Size').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 7, 7, _('House No').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 8, 8, _('Current Month Bill').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 9, 9, _('Arrears').upper(), table_heading_style)
        worksheet.write_merge(6, 6, 10, 10, _('Total Bill Amount').upper(), table_heading_style)

        set_date = '2023-11-01'
        domain = [
            ('state', '=', 'posted'),
            ('property_invoice_type', '=', 'maintenance_charges'),
            ('invoice_line_ids.product_id.id', '=', 103),
            ('payment_state', '!=', 'paid')
        ]

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
            domain.append(('file_ids.inventory_id', 'in', self.inventory_ids.ids))

        if self.from_date:
            domain.append(('invoice_date', '>=', self.from_date))

        if self.to_date:
            domain.append(('invoice_date', '<=', self.to_date))

        records = self.env['account.move'].search(domain)
        rule_group = records.read_group(domain, ['file_ids'], ['file_ids'])

        row = 7
        for group in rule_group:
            group_date = records.search(group['__domain'])
            current_date = fields.Date.today()
            current_month_invoice = group_date.filtered(
                lambda l: l.invoice_date.month == self.from_date.month and l.invoice_date.year == self.from_date.year)
            current_month_bill = 0.0
            if current_month_invoice:
                current_month_bill = current_month_invoice.amount_total
            previous_invoices = self.env['account.move'].search([
                    ('payment_state', '=', 'not_paid'),
                    ('state', '=', 'posted'),
                    ('property_invoice_type', '=', 'maintenance_charges'),
                    ('partner_id', '=', group_date[0].partner_id.id),
                    ('file_ids', 'in', group_date[0].file_ids.ids),
                    ('invoice_date', '>=', set_date),
                    ('invoice_date', '<', max(rec.invoice_date for rec in group_date)),
                    ('payment_state', '!=', 'paid')
                ])
            previous_unpaid_amount = 0.0
            if previous_invoices:
                previous_unpaid_amount = sum(previous_invoices.mapped('amount_residual_signed'))
            worksheet.write_merge(row, row, 0, 0, _(sr), columns_right_bold_style)
            worksheet.write_merge(row, row, 1, 1, _(group_date[0].partner_id.name))
            worksheet.write_merge(row, row, 2, 2, _(group_date[0].file_ids.society_id.name))
            worksheet.write_merge(row, row, 3, 3, _(group_date[0].file_ids.phase_id.name))
            worksheet.write_merge(row, row, 4, 4, _(group_date[0].file_ids.sector_id.name))
            worksheet.write_merge(row, row, 5, 5, _(group_date[0].file_ids.street_id.name))
            worksheet.write_merge(row, row, 6, 6, _(group_date[0].file_ids.size_id.name))
            worksheet.write_merge(row, row, 7, 7, _(group_date[0].file_ids.inventory_id.name))
            worksheet.write_merge(row, row, 8, 8, _('{0:,.2f}'.format(current_month_bill)), columns_right_bold_style)
            worksheet.write_merge(row, row, 9, 9, _('{0:,.2f}'.format(previous_unpaid_amount)),
                                  columns_right_bold_style)
            worksheet.write_merge(row, row, 10, 10, _('{0:,.2f}'.format(current_month_bill + previous_unpaid_amount)),
                                  columns_right_bold_style)

            sr = sr + 1
            row = row + 1

        fp = BytesIO()
        workbook.save(fp)
        # base64.encodestring() was removed in Python 3.9+; use encodebytes() instead.
        excel_file = base64.encodebytes(fp.getvalue())
        wizard.maintenance_xl_file = excel_file
        wizard.file_name = 'Maintenance Charges Report.xls'
        fp.close()

        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=maintenance.charges.wizard&field=maintenance_xl_file&download=true&id=%s&filename=%s' % (
                self.id, 'Maintenance Charges Report.xls'),
        }
