# -*- coding: utf-8 -*-
from datetime import datetime

from odoo.exceptions import UserError
from pytz import timezone

from odoo import models, api, _


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
            domain.append(
                ('sector_id', '=', society_id[0])
            )
        if phase_id:
            domain.append(
                ('phase_id', '=', phase_id[0])
            )
        if sector_ids:
            domain.append(
                ('sector_id', 'in', sector_ids)
            )
        if category_id:
            domain.append(
                ('category_id', '=', category_id[0])
            )
        if product_id:
            domain.append(
                ('unit_category_type_id', '=', product_id[0])
            )
        if agent_ids:
            domain.append(
                ('maintenance_recovery_agent_id', 'in', agent_ids)
            )
        if date_from:
            domain.append(
                ('maintenance_history_ids.date', '>=', date_from)
            )
        if date_to:
            domain.append(
                ('maintenance_history_ids.date', '<=', date_to)
            )

        record = self.env['file'].search(domain)

        return {
            # 'user_id': self.env['res.users'].browse(self._uid).name, (Used to bring current user who is making printing this report)
            'data': record,
            'date_from': date_from,
            'date_to': date_to,
            'sector_ids': self.env['sector'].browse(sector_ids) if sector_ids else self.env['sector'],
            'category_id': self.env['plot.category'].browse(category_id[0]) if category_id else self.env['plot.category'],
            'agent_ids': self.env['res.users'].browse(agent_ids) if agent_ids else self.env['res.users'],
        }
