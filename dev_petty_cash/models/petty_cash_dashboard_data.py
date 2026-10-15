# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

SPENT_STATES = ('payment', 'done')
PENDING_EXPENSE_STATES = ('draft', 'confirm')


class PettyCashDashboard(models.AbstractModel):
    """Data for the Petty Cash dashboard (client action ``dev_petty_cash.dashboard``).

    Everything is read with the user's rights, so a "User: Own Documents" sees only their
    own requests / expenses and a manager sees all of them."""
    _name = 'petty.cash.dashboard'
    _description = 'Petty Cash Dashboard'

    def _period_start(self, period):
        today = fields.Date.context_today(self)
        if period == 'month':
            return today.replace(day=1)
        if period == 'quarter':
            return date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
        if period == 'year':
            return today.replace(month=1, day=1)
        return False

    @api.model
    def get_dashboard_data(self, period='year', journal_id=False):
        Request = self.env['petty.cash.request']
        Expense = self.env['petty.cash.expense']
        company_ids = self.env.companies.ids
        base = [('company_id', 'in', company_ids + [False])]
        if journal_id:
            base.append(('petty_journal_id', '=', journal_id))
        start = self._period_start(period)
        in_period = base + ([('date', '>=', start)] if start else [])

        def total(model, domain, field):
            amount, count = model._read_group(domain, aggregates=['%s:sum' % field, '__count'])[0]
            return amount or 0.0, count

        funded, funded_count = total(Request, in_period + [('state', '=', 'approve')], 'request_amount')
        spent, spent_count = total(Expense, in_period + [('state', 'in', SPENT_STATES)], 'expense_amount')
        pending_req, pending_req_count = total(Request, base + [('state', '=', 'request')], 'request_amount')
        draft_req_count = Request.search_count(base + [('state', '=', 'draft')])
        pending_exp, pending_exp_count = total(Expense, base + [('state', 'in', PENDING_EXPENSE_STATES)], 'expense_amount')
        # cash in hand is never limited to the period
        all_funded, _count = total(Request, base + [('state', '=', 'approve')], 'request_amount')
        all_spent, _count = total(Expense, base + [('state', 'in', SPENT_STATES)], 'expense_amount')
        committed, _count = total(Expense, base + [('state', '=', 'confirm')], 'expense_amount')

        return {
            'currency_id': self.env.company.currency_id.id,
            'period': period,
            'journal_id': journal_id,
            'is_manager': self.env.user.has_group('dev_petty_cash.group_petty_manager'),
            'kpi': {
                'funded': funded, 'funded_count': funded_count,
                'spent': spent, 'spent_count': spent_count,
                'in_hand': all_funded - all_spent,
                'available': all_funded - all_spent - committed,
                'committed': committed,
                'pending_requests': pending_req, 'pending_request_count': pending_req_count,
                'draft_request_count': draft_req_count,
                'pending_expenses': pending_exp, 'pending_expense_count': pending_exp_count,
                'utilisation': round(100.0 * spent / funded, 1) if funded else 0.0,
            },
            'journals': self._journal_rows(base),
            'employees': self._employee_rows(base),
            'monthly': self._monthly_rows(base),
            'heads': self._expense_heads(in_period),
            'to_approve': self._to_approve(base),
            'recent': self._recent(base),
        }

    def _journal_rows(self, base):
        journals = self.env['account.journal'].search([
            ('is_petty_cash', '=', True), ('company_id', 'in', self.env.companies.ids)])
        domain = [d for d in base if d[0] != 'petty_journal_id']
        funded = dict(self.env['petty.cash.request']._read_group(
            domain + [('state', '=', 'approve')], ['petty_journal_id'], ['request_amount:sum']))
        spent = dict(self.env['petty.cash.expense']._read_group(
            domain + [('state', 'in', SPENT_STATES)], ['petty_journal_id'], ['expense_amount:sum']))
        pending = dict(self.env['petty.cash.expense']._read_group(
            domain + [('state', 'in', PENDING_EXPENSE_STATES)], ['petty_journal_id'], ['__count']))
        # the ledger balance of the journal's cash account is shown to accounting users only
        show_ledger = self.env.user.has_group('account.group_account_readonly')
        ledger = {}
        if show_ledger and journals.default_account_id:
            ledger = dict(self.env['account.move.line']._read_group([
                ('account_id', 'in', journals.default_account_id.ids),
                ('parent_state', '=', 'posted'),
                ('company_id', 'in', self.env.companies.ids),
            ], ['account_id'], ['balance:sum']))
        rows = []
        for journal in journals:
            f, s = funded.get(journal, 0.0), spent.get(journal, 0.0)
            rows.append({
                'id': journal.id,
                'name': journal.name,
                'company': journal.company_id.name,
                'funded': f,
                'spent': s,
                'balance': f - s,
                'pending_count': pending.get(journal, 0),
                'ledger': ledger.get(journal.default_account_id, 0.0) if show_ledger else None,
                'account': journal.default_account_id.display_name,
            })
        return rows

    def _employee_rows(self, base):
        funded = dict(self.env['petty.cash.request']._read_group(
            base + [('state', '=', 'approve')], ['request_by'], ['request_amount:sum']))
        spent = dict(self.env['petty.cash.expense']._read_group(
            base + [('state', 'in', SPENT_STATES)], ['employee_id'], ['expense_amount:sum']))
        rows = []
        for employee in (set(funded) | set(spent)) - {self.env['hr.employee']}:
            f, s = funded.get(employee, 0.0), spent.get(employee, 0.0)
            rows.append({'id': employee.id, 'name': employee.name, 'funded': f, 'spent': s, 'balance': f - s})
        rows.sort(key=lambda r: (-r['funded'], r['name']))
        return rows[:10]

    def _monthly_rows(self, base):
        today = fields.Date.context_today(self)
        first = (today - relativedelta(months=11)).replace(day=1)
        domain = base + [('date', '>=', first)]
        funded = defaultdict(float)
        spent = defaultdict(float)
        for month, amount in self.env['petty.cash.request']._read_group(
                domain + [('state', '=', 'approve')], ['date:month'], ['request_amount:sum']):
            funded[month.strftime('%Y-%m')] += amount
        for month, amount in self.env['petty.cash.expense']._read_group(
                domain + [('state', 'in', SPENT_STATES)], ['date:month'], ['expense_amount:sum']):
            spent[month.strftime('%Y-%m')] += amount
        rows = []
        for i in range(12):
            month = first + relativedelta(months=i)
            key = month.strftime('%Y-%m')
            rows.append({'key': key, 'label': month.strftime('%b %y'),
                         'funded': funded[key], 'spent': spent[key]})
        return rows

    def _expense_heads(self, in_period):
        domain = [('expense_id.%s' % d[0], d[1], d[2]) for d in in_period] + \
                 [('expense_id.state', 'in', SPENT_STATES)]
        groups = self.env['petty.expense.lines']._read_group(domain, ['product_id'], ['amount:sum'])
        rows = [{'id': product.id, 'name': product.display_name or _('Other'), 'amount': amount}
                for product, amount in groups]
        rows.sort(key=lambda r: -r['amount'])
        return rows[:8]

    def _to_approve(self, base):
        requests = self.env['petty.cash.request'].search(base + [('state', '=', 'request')], order='date, id', limit=8)
        return [{
            'id': r.id, 'name': r.name, 'employee': r.request_by.name or '',
            'journal': r.petty_journal_id.name or '', 'date': fields.Date.to_string(r.date),
            'amount': r.request_amount,
        } for r in requests]

    def _recent(self, base):
        req_states = dict(self.env['petty.cash.request']._fields['state']._description_selection(self.env))
        exp_states = dict(self.env['petty.cash.expense']._fields['state']._description_selection(self.env))
        rows = [{
            'model': 'petty.cash.request', 'id': r.id, 'name': r.name, 'type': _('Request'),
            'employee': r.request_by.name or '', 'date': fields.Date.to_string(r.date),
            'amount': r.request_amount, 'state': r.state, 'state_label': req_states.get(r.state),
        } for r in self.env['petty.cash.request'].search(base, order='date desc, id desc', limit=8)]
        rows += [{
            'model': 'petty.cash.expense', 'id': e.id, 'name': e.name, 'type': _('Expense'),
            'employee': e.employee_id.name or '', 'date': fields.Date.to_string(e.date),
            'amount': e.expense_amount, 'state': e.state, 'state_label': exp_states.get(e.state),
        } for e in self.env['petty.cash.expense'].search(base, order='date desc, id desc', limit=8)]
        rows.sort(key=lambda r: (r['date'] or '', r['id']), reverse=True)
        return rows[:10]
