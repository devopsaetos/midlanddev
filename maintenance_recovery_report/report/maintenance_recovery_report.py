# -*- coding: utf-8 -*-
from datetime import datetime

from odoo.exceptions import UserError
from pytz import timezone

from odoo import models, fields, api, _


class MaintenanceRecoveryReport(models.AbstractModel):
    _name = 'report.maintenance_recovery_report.maintenance_recovery'
    _description = 'Maintenance Recovery Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        # The wizard (maintenance.recovery.wizard) already passes its filter
        # values explicitly via data['form'] when it calls report_action() -
        # read from there instead of context['active_model']/['active_id'],
        # which isn't reliably the wizard when the report is rendered from a
        # different context (e.g. a PDF/document-layout preview).
        form = (data or {}).get('form') or {}

        society_id = form.get('society_id')
        phase_id = form.get('phase_id')
        sector_ids = form.get('sector_ids')
        category_id = form.get('category_id')
        product_id = form.get('product_id')
        agent_ids = form.get('agent_ids')
        date_from = form.get('date_from')
        date_to = form.get('date_to')

        domain = []
        if society_id:
            domain.append(('society_id', '=', society_id[0]))
        if phase_id:
            domain.append(('phase_id', '=', phase_id[0]))
        if sector_ids:
            domain.append(('sector_id', 'in', sector_ids))
        if category_id:
            domain.append(('category_id', '=', category_id[0]))
        if product_id:
            domain.append(('unit_category_type_id', '=', product_id[0]))
        if agent_ids:
            domain.append(('maintenance_recovery_agent_id', 'in', agent_ids))
        date_from = date_from and fields.Date.to_date(date_from)
        date_to = date_to and fields.Date.to_date(date_to)

        # every society the office manages, whatever company is active
        files = self.env['file'].with_context(allowed_company_ids=self.env.user.company_ids.ids).search(domain)
        rows = []
        for file in files:
            history = file.maintenance_history_ids.filtered(
                lambda h: h.date and (not date_from or h.date >= date_from) and (not date_to or h.date <= date_to))
            if not history:
                continue
            amount = sum(history.mapped('amount'))
            paid = sum(history.mapped('amount_paid'))
            # imported Excel rows carry a running balance: only the latest one per charge counts
            due = sum(history.filtered('invoice_id').mapped('residual'))
            for charge in set(history.mapped('charge_type')):
                imported = history.filtered(lambda h: not h.invoice_id and h.charge_type == charge)
                if imported:
                    due += imported.sorted(lambda h: (h.date, h.id))[-1].residual
            rows.append({
                'file': file,
                'amount': amount,
                'paid': paid,
                'due': due,
                'status': _('Paid') if due <= 0 else (_('Partly Paid') if paid else _('Not Paid')),
            })
        rows.sort(key=lambda r: (r['file'].sector_id.name or '', r['file'].unit_number or ''))

        return {
            'rows': rows,
            'total_amount': sum(r['amount'] for r in rows),
            'total_paid': sum(r['paid'] for r in rows),
            'total_due': sum(r['due'] for r in rows),
            'company': files.mapped('maintenance_history_ids.invoice_id.company_id')[:1] or self.env.company,
            'date_from': date_from,
            'date_to': date_to,
            'society': self.env['society'].browse(society_id[0]) if society_id else self.env['society'],
            'sector_ids': self.env['sector'].browse(sector_ids) if sector_ids else self.env['sector'],
            'category_id': self.env['plot.category'].browse(category_id[0]) if category_id else self.env['plot.category'],
            'product': self.env['unit.category.type'].browse(product_id[0]) if product_id else self.env['unit.category.type'],
            'agent_ids': self.env['res.users'].browse(agent_ids) if agent_ids else self.env['res.users'],
        }
