# -*- coding: utf-8 -*-
import base64
import calendar
import re
from datetime import date
from io import BytesIO
from urllib.parse import quote

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MONTHS = [(str(m), calendar.month_name[m]) for m in range(1, 13)]


class ProjectReceivablesWizard(models.TransientModel):
    _name = 'project.receivables.wizard'
    _description = 'Project Receivables Report'

    society_id = fields.Many2one(
        'society', string='Project', required=True, domain="[('is_society', '=', True)]")
    month = fields.Selection(
        MONTHS, string='Till Month', required=True,
        default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Integer(
        required=True, default=lambda self: fields.Date.context_today(self).year)
    report_file = fields.Binary(readonly=True, attachment=False)

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not 2000 <= rec.year <= 2100:
                raise UserError(_('Please enter a valid year.'))

    def _report_title(self):
        self.ensure_one()
        return '%s (Receivables)' % self.society_id.name

    @api.model
    def _remove_per_project_menus(self):
        """Drop the per-project "<Project> (Receivables)" menus/actions an
        earlier version generated - everything opening this wizard except
        the module's own Member (Receivables) action."""
        keep = self.env.ref('project_receivables_report.project_receivables_action', raise_if_not_found=False)
        actions = self.env['ir.actions.act_window'].sudo().search([
            ('res_model', '=', self._name), ('id', '!=', keep.id if keep else 0)])
        if actions:
            self.env['ir.ui.menu'].sudo().with_context(active_test=False).search([
                ('action', 'in', ['ir.actions.act_window,%d' % a.id for a in actions])]).unlink()
            actions.unlink()

    # ── Data ──────────────────────────────────────────────────────────────────

    def _month_bounds(self):
        year, month = self.year, int(self.month)
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])

    def _files(self):
        """The project's live member files that have an installment plan.

        sudo(): the menu already scopes this to one explicit project, and
        file/installment.plan carry multi-company rules on the project's own
        company - a user invoicing across the group (their active company
        being the parent) would otherwise get an empty report.
        """
        return self.env['file'].sudo().search([
            ('society_id', '=', self.society_id.id),
            ('membership_id', '!=', False),
            ('installment_plan_ids', '!=', False),
            ('file_status', 'not in', ('cancel', 'merged_and_cancel')),
            ('state', 'not in', ('cancel', 'refund', 'merged')),
        ])

    def _rows(self):
        """One dict per file. Paid/due figures are the installment plan's
        current Amount Paid / Amount Due; "Till Month" decides which lines
        are the current month's installment and which count as overdue.

        Current Month Installment = plan lines dated in the selected month
        Installment Paid          = what's been paid against those lines
        Overdue Amount            = unpaid balance of lines dated before it
        Due Amount                = current month's unpaid part + overdue
        Amount Due                = Total Amount - Amount Paid (whole plan)
        """
        month_start, month_end = self._month_bounds()
        rows = []
        for f in self._files():
            lines = f.installment_plan_ids
            current = lines.filtered(lambda l: l.date and month_start <= l.date <= month_end)
            earlier = lines.filtered(lambda l: l.date and l.date < month_start)
            total = sum(lines.mapped('amount'))
            paid = sum(lines.mapped('amount_paid'))
            current_amount = sum(current.mapped('amount'))
            current_paid = sum(current.mapped('amount_paid'))
            overdue = sum(earlier.mapped('residual'))
            rows.append({
                'plot': f.unit_number or '',
                'member': f.membership_id.name or '',
                'mobile': f.membership_id.mobile or '',
                'size': f.unit_category_type_id.name or '',
                'category': f.category_id.name or '',
                'total': total,
                'paid': paid,
                'amount_due': total - paid,
                'current_amount': current_amount,
                'current_paid': current_paid,
                'overdue': overdue,
                'due_amount': (current_amount - current_paid) + overdue,
                'due_date': min(current.mapped('date')) if current else False,
            })
        rows.sort(key=lambda r: (self._natural_key(r['plot']), r['member']))
        return rows

    @staticmethod
    def _natural_key(value):
        """'9' before '10' - plot numbers are text."""
        return [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', value or '')]

    # ── Excel ─────────────────────────────────────────────────────────────────

    COLUMNS = [
        # (header, key, width, kind)
        ('S.No.', 'serial', 6, 'int'),
        ('Plot Number', 'plot', 11, 'text'),
        ('Member Name', 'member', 26, 'text'),
        ('Mobile Num.', 'mobile', 15, 'text'),
        ('Size', 'size', 10, 'text'),
        ('Category', 'category', 13, 'text'),
        ('Total Amount', 'total', 15, 'money'),
        ('Amount Paid', 'paid', 15, 'money'),
        ('Amount Due', 'amount_due', 15, 'money'),
        ('Current Month Installment', 'current_amount', 15, 'money'),
        ('Installment Paid', 'current_paid', 13, 'money'),
        ('Overdue Amount', 'overdue', 14, 'money'),
        ('Due Amount', 'due_amount', 14, 'money'),
        ('Due Date', 'due_date', 12, 'date'),
    ]

    def _build_xlsx(self, rows):
        buf = BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        ws = wb.add_worksheet('Receivables')
        blue = '#BDD7EE'
        f_title = wb.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        f_month = wb.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter',
                                 'bg_color': blue, 'border': 1})
        f_head = wb.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter',
                                'text_wrap': True, 'bg_color': blue, 'border': 1})
        f_text = wb.add_format({'border': 1, 'align': 'center'})
        f_left = wb.add_format({'border': 1})
        f_money = wb.add_format({'border': 1, 'num_format': '#,##0'})
        f_date = wb.add_format({'border': 1, 'align': 'center', 'num_format': 'dd/mm/yyyy'})
        f_total_lbl = wb.add_format({'bold': True, 'border': 1, 'bg_color': blue})
        f_total = wb.add_format({'bold': True, 'border': 1, 'bg_color': blue, 'num_format': '#,##0'})

        last_col = len(self.COLUMNS) - 1
        month_label = '%s %s' % (calendar.month_name[int(self.month)], self.year)
        ws.merge_range(0, 0, 0, last_col, self._report_title(), f_title)
        ws.merge_range(1, 0, 1, last_col, 'Till Month: %s' % month_label, f_month)
        ws.set_row(2, 32)
        for col, (header, _key, width, _kind) in enumerate(self.COLUMNS):
            ws.set_column(col, col, width)
            ws.write(2, col, header, f_head)

        row = 3
        for serial, data in enumerate(rows, start=1):
            data = dict(data, serial=serial)
            for col, (_h, key, _w, kind) in enumerate(self.COLUMNS):
                value = data[key]
                if kind == 'money':
                    ws.write_number(row, col, value or 0.0, f_money)
                elif kind == 'date':
                    if value:
                        ws.write_datetime(row, col, fields.Datetime.to_datetime(value), f_date)
                    else:
                        ws.write_blank(row, col, None, f_date)
                elif kind == 'int':
                    ws.write_number(row, col, value, f_text)
                else:
                    ws.write_string(row, col, str(value), f_left if key == 'member' else f_text)
            row += 1

        # Totals under every money column.
        money_cols = [i for i, c in enumerate(self.COLUMNS) if c[3] == 'money']
        # "Total" under Member Name, like the PDF.
        member_col = [c[1] for c in self.COLUMNS].index('member')
        for col in range(money_cols[0]):
            ws.write(row, col, 'Total' if col == member_col else '', f_total_lbl)
        for col in range(money_cols[0], last_col + 1):
            key, kind = self.COLUMNS[col][1], self.COLUMNS[col][3]
            if kind == 'money':
                ws.write_number(row, col, sum(r[key] or 0.0 for r in rows), f_total)
            else:
                ws.write_blank(row, col, None, f_total)

        ws.freeze_panes(3, 0)
        wb.close()
        return buf.getvalue()

    def action_generate_xlsx(self):
        self.ensure_one()
        rows = self._rows()
        if not rows:
            raise UserError(_('No member files with an installment plan were found for %s.')
                            % self.society_id.name)
        self.report_file = base64.b64encode(self._build_xlsx(rows))
        filename = '%s - %s %s.xlsx' % (
            self._report_title(), calendar.month_name[int(self.month)], self.year)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=report_file&download=true&filename=%s' % (
                self._name, self.id, quote(filename)),
            'target': 'self',
        }

    def action_print_pdf(self):
        self.ensure_one()
        if not self._rows():
            raise UserError(_('No member files with an installment plan were found for %s.')
                            % self.society_id.name)
        # config=False: this report doesn't use the company's external
        # layout, so skip Odoo's "configure your document layout" prompt.
        return self.env.ref('project_receivables_report.action_report_project_receivables').report_action(
            self, config=False)
