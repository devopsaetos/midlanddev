# -*- coding: utf-8 -*-
import base64
import io
from collections import defaultdict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

FUNDED_STATES = ('approve',)
SPENT_STATES = ('payment', 'done')

GROUP_LABELS = {
    'product': 'Expense Head',
    'employee': 'Employee',
    'account': 'Account',
    'fund': 'Petty Cash Fund',
}


class PettyCashReport(models.TransientModel):
    """Petty Cash Report: Summary, Cash Book (statement with running balance) and Expense
    Detail, as PDF or Excel. Both outputs come from ``_get_report_data`` and read with the
    user's rights, so a "User: Own Documents" only gets their own figures."""
    _name = 'petty.cash.report'
    _description = 'Petty Cash Report'

    def _default_date_from(self):
        return fields.Date.context_today(self).replace(day=1)

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date('From', required=True, default=_default_date_from)
    date_to = fields.Date('To', required=True, default=fields.Date.context_today)
    journal_ids = fields.Many2many(
        'account.journal', string='Petty Cash Funds',
        domain="[('is_petty_cash', '=', True), ('company_id', '=', company_id)]",
        help='Leave empty for all funds.')
    # the public profile, so users without HR rights can filter too (same ids as hr.employee)
    employee_ids = fields.Many2many('hr.employee.public', string='Employees', help='Leave empty for all employees.')
    report_type = fields.Selection([
        ('full', 'Full Report (Summary + Cash Book + Expense Detail)'),
        ('summary', 'Summary'),
        ('cashbook', 'Cash Book'),
        ('detail', 'Expense Detail'),
    ], string='Report', required=True, default='full')
    group_by = fields.Selection([
        ('product', 'Expense Head'),
        ('employee', 'Employee'),
        ('account', 'Account'),
        ('fund', 'Petty Cash Fund'),
    ], string='Group Expense Detail By', required=True, default='product')
    include_confirmed = fields.Boolean(
        'Include Confirmed Expenses',
        help='Also count expenses that are confirmed but not posted yet. By default only posted '
             '(Done) expenses count as spent, like the dashboard.')
    xlsx_file = fields.Binary('Excel File', readonly=True, attachment=False)
    xlsx_name = fields.Char('Excel File Name', readonly=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise UserError(_('"From" must be before "To".'))

    # ── data ──────────────────────────────────────────────────────────────────

    def _spent_states(self):
        return SPENT_STATES + (('confirm',) if self.include_confirmed else ())

    def _base_domain(self, employee_field):
        domain = [('company_id', 'in', [self.company_id.id, False])]
        if self.journal_ids:
            domain.append(('petty_journal_id', 'in', self.journal_ids.ids))
        if self.employee_ids:
            domain.append((employee_field, 'in', self.employee_ids.ids))
        return domain

    def _get_report_data(self):
        self.ensure_one()
        Request = self.env['petty.cash.request']
        Expense = self.env['petty.cash.expense']
        req_base = self._base_domain('request_by') + [('state', 'in', FUNDED_STATES)]
        exp_base = self._base_domain('employee_id') + [('state', 'in', self._spent_states())]

        # opening = everything before the period; the period's own documents feed the rest
        before = [('date', '<', self.date_from)]
        period = [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        open_req = Request._read_group(req_base + before, ['petty_journal_id', 'request_by'], ['request_amount:sum'])
        open_exp = Expense._read_group(exp_base + before, ['petty_journal_id', 'employee_id'], ['expense_amount:sum'])
        requests = Request.search(req_base + period, order='date, name, id')
        expenses = Expense.search(exp_base + period, order='date, name, id')

        opening_fund = defaultdict(float)
        opening_emp = defaultdict(float)
        for journal, employee, amount in open_req:
            opening_fund[journal] += amount
            opening_emp[employee] += amount
        for journal, employee, amount in open_exp:
            opening_fund[journal] -= amount
            opening_emp[employee] -= amount

        # ── cash book: one statement per fund, running balance ──
        moves = defaultdict(list)
        for r in requests:
            moves[r.petty_journal_id].append({
                'date': r.date, 'ref': r.name, 'type': _('Funding'),
                'employee': r.request_by.name or '',
                'description': r.note or _('Cash from %s', r.payment_journal_id.name or ''),
                'received': r.request_amount, 'paid': 0.0, 'sort': 0,
            })
        for e in expenses:
            moves[e.petty_journal_id].append({
                'date': e.date, 'ref': e.name, 'type': _('Expense'),
                'employee': e.employee_id.name or '',
                'description': ', '.join(filter(None, (l.name or l.product_id.name for l in e.expense_lines))) or e.note or '',
                'received': 0.0, 'paid': e.expense_amount, 'sort': 1,
            })
        Journal = self.env['account.journal']
        funds = self.journal_ids or Journal.search([('is_petty_cash', '=', True), ('company_id', '=', self.company_id.id)])
        funds = (funds | Journal.concat(*moves, *opening_fund)).sorted('name')
        # documents without a fund (the field isn't required) get their own statement, last
        fund_list = list(funds) + ([Journal] if Journal in moves or opening_fund.get(Journal) else [])
        cashbook = []
        for fund in fund_list:
            opening = opening_fund.get(fund, 0.0)
            rows = sorted(moves.get(fund, []), key=lambda m: (m['date'], m['sort'], m['ref']))
            if not rows and not opening:
                continue
            balance = opening
            for row in rows:
                balance += row['received'] - row['paid']
                row['balance'] = balance
            received = sum(r['received'] for r in rows)
            paid = sum(r['paid'] for r in rows)
            cashbook.append({
                'fund': fund.name or _('No Fund'), 'account': fund.default_account_id.display_name or '',
                'opening': opening, 'received': received, 'paid': paid,
                'closing': opening + received - paid, 'rows': rows,
            })

        # ── summary per employee ──
        emp_funded, emp_spent = defaultdict(float), defaultdict(float)
        for r in requests:
            emp_funded[r.request_by] += r.request_amount
        for e in expenses:
            emp_spent[e.employee_id] += e.expense_amount
        employees = []
        for employee in set(opening_emp) | set(emp_funded) | set(emp_spent):
            opening = opening_emp.get(employee, 0.0)
            f, s = emp_funded.get(employee, 0.0), emp_spent.get(employee, 0.0)
            if not (opening or f or s):
                continue
            employees.append({'name': employee.name or _('No Employee'), 'opening': opening,
                              'funded': f, 'spent': s, 'closing': opening + f - s,
                              'count': len(expenses.filtered(lambda e: e.employee_id == employee))})
        employees.sort(key=lambda r: r['name'])

        # ── expense lines: detail and the head / account summaries ──
        lines = expenses.expense_lines.sorted(lambda l: (l.expense_id.date, l.expense_id.name, l.id))
        detail_rows = [{
            'date': l.expense_id.date, 'ref': l.expense_id.name,
            'employee': l.expense_id.employee_id.name or '',
            'fund': l.expense_id.petty_journal_id.name or '',
            'product': l.product_id.display_name or _('Other'),
            'description': l.name or '',
            'account': l.account_id.display_name or '',
            'analytic': l.analytic_account_id.display_name or '',
            'state': dict(l.expense_id._fields['state']._description_selection(self.env)).get(l.expense_id.state),
            'amount': l.amount,
        } for l in lines]
        total_spent = sum(r['amount'] for r in detail_rows)

        undefined = _('Undefined')

        def totals_by(key):
            amounts, counts = defaultdict(float), defaultdict(int)
            for row in detail_rows:
                amounts[row[key] or undefined] += row['amount']
                counts[row[key] or undefined] += 1
            return [{'name': name, 'count': counts[name], 'amount': amount,
                     'pct': 100.0 * amount / total_spent if total_spent else 0.0}
                    for name, amount in sorted(amounts.items(), key=lambda i: -i[1])]

        groups = defaultdict(list)
        for row in detail_rows:
            groups[row[self.group_by] or _('Undefined')].append(row)
        detail = [{'name': name, 'rows': rows, 'amount': sum(r['amount'] for r in rows)}
                  for name, rows in sorted(groups.items())]

        opening_total = sum(f['opening'] for f in cashbook)
        funded_total = sum(f['received'] for f in cashbook)
        spent_total = sum(f['paid'] for f in cashbook)
        return {
            'company': self.company_id,
            'currency': self.company_id.currency_id,
            'date_from': format_date(self.env, self.date_from),
            'date_to': format_date(self.env, self.date_to),
            'printed_on': format_date(self.env, fields.Date.context_today(self)),
            'printed_by': self.env.user.name,
            'printed_at': format_datetime(self.env, fields.Datetime.now(), dt_format='short'),
            'company_address': ', '.join(filter(None, ((part or '').strip(' ,') for part in (
                self.company_id.street, self.company_id.street2, self.company_id.city,
                self.company_id.state_id.name, self.company_id.zip, self.company_id.country_id.name)))),
            'company_contact': '  |  '.join(filter(None, (
                self.company_id.phone and _('Tel: %s', self.company_id.phone),
                self.company_id.email, self.company_id.website))),
            'funds_label': ', '.join(self.journal_ids.mapped('name')) or _('All funds'),
            'employees_label': ', '.join(self.employee_ids.mapped('name')) or _('All employees'),
            'spent_label': _('Confirmed + posted expenses') if self.include_confirmed else _('Posted expenses'),
            'report_type': self.report_type,
            'group_label': _(GROUP_LABELS[self.group_by]),
            'show': {
                'summary': self.report_type in ('full', 'summary'),
                'cashbook': self.report_type in ('full', 'cashbook'),
                'detail': self.report_type in ('full', 'detail'),
            },
            'kpi': {
                'opening': opening_total, 'funded': funded_total, 'spent': spent_total,
                'closing': opening_total + funded_total - spent_total,
                'request_count': len(requests), 'expense_count': len(expenses),
            },
            'cashbook': cashbook,
            'employees': employees,
            'heads': totals_by('product'),
            'accounts': totals_by('account'),
            'detail': detail,
            'detail_total': total_spent,
        }

    # ── actions ───────────────────────────────────────────────────────────────

    def _file_name(self, ext):
        return '%s %s - %s.%s' % (_('Petty Cash Report'), self.date_from, self.date_to, ext)

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('dev_petty_cash.action_report_petty_cash_summary').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        self.write({'xlsx_file': base64.b64encode(self._render_xlsx()), 'xlsx_name': self._file_name('xlsx')})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=xlsx_file&filename_field=xlsx_name&download=true'
                   % (self._name, self.id),
            'target': 'download',
        }

    # ── Excel ─────────────────────────────────────────────────────────────────

    def _xlsx_logo(self, company):
        """(png bytes, scale) for the company logo at ~55 px high, or None."""
        if not company.logo:
            return None
        try:
            from PIL import Image
            raw = base64.b64decode(company.logo)
            with Image.open(io.BytesIO(raw)) as img:
                width, height = img.size
                if img.format != 'PNG':
                    buf = io.BytesIO()
                    img.convert('RGBA').save(buf, format='PNG')
                    raw = buf.getvalue()
        except Exception:  # SVG or unreadable logo: no image, the text letterhead stays
            return None
        scale = min(55.0 / height, 80.0 / width)
        return raw, scale

    def _render_xlsx(self):
        data = self._get_report_data()
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True})
        cur = data['currency']
        money_fmt = '#,##0.%s' % ('0' * cur.decimal_places) if cur.decimal_places else '#,##0'
        money_fmt = '%s;[Red]-%s' % (money_fmt, money_fmt)
        f = {
            'sub': book.add_format({'italic': True, 'font_color': '#595959'}),
            'section': book.add_format({'bold': True, 'font_size': 12, 'font_color': '#1F4E79', 'bottom': 2, 'bottom_color': '#1F4E79'}),
            'head': book.add_format({'bold': True, 'bg_color': '#1F4E79', 'font_color': 'white', 'border': 1, 'valign': 'vcenter', 'text_wrap': True}),
            'head_r': book.add_format({'bold': True, 'bg_color': '#1F4E79', 'font_color': 'white', 'border': 1, 'align': 'right', 'valign': 'vcenter', 'text_wrap': True}),
            'cell': book.add_format({'border': 1, 'border_color': '#BFBFBF'}),
            'wrap': book.add_format({'border': 1, 'border_color': '#BFBFBF', 'text_wrap': True, 'valign': 'top'}),
            'date': book.add_format({'border': 1, 'border_color': '#BFBFBF', 'num_format': 'dd/mm/yyyy', 'align': 'left'}),
            'money': book.add_format({'border': 1, 'border_color': '#BFBFBF', 'num_format': money_fmt}),
            'pct': book.add_format({'border': 1, 'border_color': '#BFBFBF', 'num_format': '0.0"%"'}),
            'int': book.add_format({'border': 1, 'border_color': '#BFBFBF', 'num_format': '0'}),
            'group': book.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'border_color': '#BFBFBF'}),
            'group_money': book.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'border_color': '#BFBFBF', 'num_format': money_fmt}),
            'total': book.add_format({'bold': True, 'bg_color': '#F2F2F2', 'top': 2, 'border': 1, 'border_color': '#808080'}),
            'total_money': book.add_format({'bold': True, 'bg_color': '#F2F2F2', 'top': 2, 'border': 1, 'border_color': '#808080', 'num_format': money_fmt}),
            'opening': book.add_format({'italic': True, 'bg_color': '#FFF2CC', 'border': 1, 'border_color': '#BFBFBF'}),
            'opening_money': book.add_format({'italic': True, 'bg_color': '#FFF2CC', 'border': 1, 'border_color': '#BFBFBF', 'num_format': money_fmt}),
            'kpi_label': book.add_format({'bold': True, 'font_color': '#595959', 'border': 1, 'border_color': '#BFBFBF', 'bg_color': '#F2F2F2'}),
            'kpi_money': book.add_format({'bold': True, 'font_size': 12, 'border': 1, 'border_color': '#BFBFBF', 'num_format': money_fmt}),
        }

        # letterhead: logo, company, address, report title, filters (rows 0-3); the logo sits
        # over column A, so the text is indented past it
        logo = self._xlsx_logo(data['company'])
        indent = {'indent': 7} if logo else {}
        lh = {
            'company': book.add_format(dict(indent, bold=True, font_size=15, font_color='#1F4E79', valign='vcenter')),
            'address': book.add_format(dict(indent, font_size=9, font_color='#595959', valign='top')),
            'title': book.add_format(dict(indent, bold=True, font_size=12, font_color='#1F4E79', valign='vcenter', bottom=2, bottom_color='#1F4E79')),
            'filters': book.add_format({'italic': True, 'font_size': 9, 'font_color': '#595959'}),
        }

        def header(sheet, title, width):
            sheet.merge_range(0, 0, 0, width - 1, data['company'].name, lh['company'])
            sheet.merge_range(1, 0, 1, width - 1, ' | '.join(filter(None, (data['company_address'], data['company_contact']))), lh['address'])
            sheet.merge_range(2, 0, 2, width - 1, '%s   (%s - %s)' % (title, data['date_from'], data['date_to']), lh['title'])
            sheet.merge_range(3, 0, 3, width - 1, self.env._('Funds: %(funds)s   |   Employees: %(emps)s   |   Spent = %(spent)s   |   Currency: %(cur)s   |   Printed by %(user)s on %(at)s',
                                                   funds=data['funds_label'], emps=data['employees_label'], spent=data['spent_label'],
                                                   cur=cur.name, user=data['printed_by'], at=data['printed_at']), lh['filters'])
            sheet.set_row(0, 24)
            sheet.set_row(1, 15)
            sheet.set_row(2, 22)
            if logo:
                sheet.insert_image(0, 0, 'logo.png', {'image_data': io.BytesIO(logo[0]), 'x_scale': logo[1], 'y_scale': logo[1],
                                                      'x_offset': 4, 'y_offset': 4, 'object_position': 3})
            # printed page letterhead / footer
            sheet.set_header('&L&"Arial,Bold"%s&C&"Arial,Bold"%s&R%s - %s' % (
                data['company'].name.replace('&', '&&'), title.replace('&', '&&'), data['date_from'], data['date_to']))
            sheet.set_footer('&L%s&C%s&RPage &P of &N' % (
                self.env._('Printed by %(user)s on %(at)s', user=data['printed_by'], at=data['printed_at']).replace('&', '&&'),
                data['company_contact'].replace('&', '&&')))
            return 5

        def table_head(sheet, row, columns):
            for col, (label, _width, right) in enumerate(columns):
                sheet.write(row, col, label, f['head_r'] if right else f['head'])
                sheet.set_column(col, col, _width)
            sheet.set_row(row, 20)
            return row + 1

        if data['show']['summary']:
            sheet = book.add_worksheet(_('Summary'))
            sheet.hide_gridlines(2)
            row = header(sheet, _('Petty Cash Summary'), 6)
            kpis = [(_('Opening Balance'), data['kpi']['opening']), (_('Funded'), data['kpi']['funded']),
                    (_('Spent'), data['kpi']['spent']), (_('Closing Balance'), data['kpi']['closing'])]
            for i, (label, value) in enumerate(kpis):
                sheet.write(row, i, label, f['kpi_label'])
                sheet.write_number(row + 1, i, value, f['kpi_money'])
            row += 3

            sheet.write(row, 0, _('By Petty Cash Fund'), f['section'])
            row = table_head(sheet, row + 1, [(_('Fund'), 34, False), (_('Opening'), 16, True), (_('Funded'), 16, True),
                                              (_('Spent'), 16, True), (_('Closing'), 16, True), (_('Account'), 34, False)])
            for fund in data['cashbook']:
                sheet.write(row, 0, fund['fund'], f['cell'])
                for col, key in enumerate(('opening', 'received', 'paid', 'closing'), 1):
                    sheet.write_number(row, col, fund[key], f['money'])
                sheet.write(row, 5, fund['account'], f['cell'])
                row += 1
            sheet.write(row, 0, _('Total'), f['total'])
            for col, key in enumerate(('opening', 'funded', 'spent', 'closing'), 1):
                sheet.write_number(row, col, data['kpi'][key], f['total_money'])
            sheet.write(row, 5, '', f['total'])
            row += 3

            sheet.write(row, 0, _('By Employee'), f['section'])
            row = table_head(sheet, row + 1, [(_('Employee'), 34, False), (_('Opening'), 16, True), (_('Funded'), 16, True),
                                              (_('Spent'), 16, True), (_('Closing'), 16, True), (_('Expenses'), 34, True)])
            for emp in data['employees']:
                sheet.write(row, 0, emp['name'], f['cell'])
                for col, key in enumerate(('opening', 'funded', 'spent', 'closing'), 1):
                    sheet.write_number(row, col, emp[key], f['money'])
                sheet.write_number(row, 5, emp['count'], f['int'])
                row += 1
            sheet.write(row, 0, _('Total'), f['total'])
            for col, key in enumerate(('opening', 'funded', 'spent', 'closing'), 1):
                sheet.write_number(row, col, sum(e[key] for e in data['employees']), f['total_money'])
            sheet.write_number(row, 5, sum(e['count'] for e in data['employees']), f['total'])
            row += 3

            for title, label, rows in ((_('By Expense Head'), _('Expense Head'), data['heads']),
                                       (_('By Account'), _('Account'), data['accounts'])):
                sheet.write(row, 0, title, f['section'])
                row = table_head(sheet, row + 1, [(label, 34, False), (_('Lines'), 16, True),
                                                  (_('Amount'), 16, True), (_('% of Spent'), 16, True)])
                first = row
                for item in rows:
                    sheet.write(row, 0, item['name'], f['cell'])
                    sheet.write_number(row, 1, item['count'], f['int'])
                    sheet.write_number(row, 2, item['amount'], f['money'])
                    sheet.write_number(row, 3, item['pct'], f['pct'])
                    row += 1
                if rows:
                    sheet.conditional_format(first, 3, row - 1, 3, {'type': 'data_bar', 'bar_color': '#9BC2E6', 'bar_solid': True})
                sheet.write(row, 0, _('Total'), f['total'])
                sheet.write_number(row, 1, sum(i['count'] for i in rows), f['total'])
                sheet.write_number(row, 2, data['detail_total'], f['total_money'])
                sheet.write(row, 3, '', f['total'])
                row += 3

        if data['show']['cashbook']:
            sheet = book.add_worksheet(_('Cash Book'))
            sheet.hide_gridlines(2)
            row = header(sheet, _('Petty Cash Book'), 8)
            columns = [(_('Date'), 12, False), (_('Reference'), 16, False), (_('Type'), 10, False), (_('Employee'), 24, False),
                       (_('Description'), 44, False), (_('Received'), 15, True), (_('Paid'), 15, True), (_('Balance'), 16, True)]
            sheet.freeze_panes(5, 0)
            for fund in data['cashbook']:
                sheet.merge_range(row, 0, row, 7, '%s   (%s)' % (fund['fund'], fund['account']), f['section'])
                row = table_head(sheet, row + 1, columns)
                sheet.merge_range(row, 0, row, 4, _('Opening Balance'), f['opening'])
                sheet.write(row, 5, '', f['opening'])
                sheet.write(row, 6, '', f['opening'])
                sheet.write_number(row, 7, fund['opening'], f['opening_money'])
                row += 1
                for m in fund['rows']:
                    sheet.write_datetime(row, 0, m['date'], f['date'])
                    sheet.write(row, 1, m['ref'], f['cell'])
                    sheet.write(row, 2, m['type'], f['cell'])
                    sheet.write(row, 3, m['employee'], f['cell'])
                    sheet.write(row, 4, m['description'], f['wrap'])
                    for col, key in ((5, 'received'), (6, 'paid')):
                        if m[key]:
                            sheet.write_number(row, col, m[key], f['money'])
                        else:
                            sheet.write(row, col, '', f['cell'])
                    sheet.write_number(row, 7, m['balance'], f['money'])
                    row += 1
                sheet.merge_range(row, 0, row, 4, _('Closing Balance'), f['total'])
                sheet.write_number(row, 5, fund['received'], f['total_money'])
                sheet.write_number(row, 6, fund['paid'], f['total_money'])
                sheet.write_number(row, 7, fund['closing'], f['total_money'])
                row += 3
            if not data['cashbook']:
                sheet.write(row, 0, _('No petty cash movements for these filters.'), f['sub'])

        if data['show']['detail']:
            sheet = book.add_worksheet(_('Expense Detail'))
            sheet.hide_gridlines(2)
            row = header(sheet, _('Petty Cash Expense Detail (grouped by %s)', data['group_label']), 10)
            row = table_head(sheet, row, [
                (_('Date'), 12, False), (_('Expense'), 16, False), (_('Employee'), 22, False), (_('Fund'), 24, False),
                (_('Expense Head'), 22, False), (_('Description'), 34, False), (_('Account'), 30, False),
                (_('Analytic'), 22, False), (_('Status'), 10, False), (_('Amount'), 15, True)])
            sheet.freeze_panes(row, 0)
            sheet.autofilter(row - 1, 0, row - 1 + sum(len(g['rows']) + 1 for g in data['detail']), 9)
            for group in data['detail']:
                sheet.merge_range(row, 0, row, 8, '%s: %s  (%s)' % (data['group_label'], group['name'], len(group['rows'])), f['group'])
                sheet.write_number(row, 9, group['amount'], f['group_money'])
                row += 1
                for d in group['rows']:
                    sheet.write_datetime(row, 0, d['date'], f['date'])
                    for col, key in enumerate(('ref', 'employee', 'fund', 'product', 'description', 'account', 'analytic', 'state'), 1):
                        sheet.write(row, col, d[key], f['cell'])
                    sheet.write_number(row, 9, d['amount'], f['money'])
                    row += 1
            sheet.merge_range(row, 0, row, 8, _('Total'), f['total'])
            sheet.write_number(row, 9, data['detail_total'], f['total_money'])

        for sheet in book.worksheets():
            sheet.set_landscape()
            sheet.set_paper(9)  # A4
            sheet.fit_to_pages(1, 0)
        book.close()
        return output.getvalue()
