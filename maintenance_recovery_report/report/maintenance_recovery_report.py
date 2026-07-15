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
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))

        # 'society_id': self.society_id.id,
        #         'phase_id': self.phase_id.id,
        #         'sector_ids': self.sector_ids.ids,
        #         'category_id': self.category_id.id,
        #         'product_id': self.product_id.id,

        domain = []
        society_id = None
        phase_id = None
        sector_ids = None
        category_id = None
        product_id = None
        agent_ids = None
        date_from = None
        date_to = None

        if docs.society_id:
            society_id = docs.society_id

        if docs.phase_id:
            phase_id = docs.phase_id

        if docs.sector_ids:
            sector_ids = docs.sector_ids

        if docs.category_id:
            category_id = docs.category_id

        if docs.product_id:
            product_id = docs.product_id

        if docs.agent_ids:
            agent_ids = docs.agent_ids

        if docs.date_from:
            date_from = docs.date_from

        if docs.date_to:
            date_to = docs.date_to

        #################################################

        if society_id:
            domain.append(
                ('sector_id', '=', society_id.id)
            )
        if phase_id:
            domain.append(
                ('phase_id', '=', phase_id.id)
            )
        if sector_ids:
            domain.append(
                ('sector_id', 'in', sector_ids.ids)
            )
        if category_id:
            domain.append(
                ('category_id', '=', category_id.id)
            )
        if product_id:
            domain.append(
                ('unit_category_type_id', '=', product_id.id)
            )
        if agent_ids:
            domain.append(
                ('maintenance_recovery_agent_id', 'in', agent_ids.ids)
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
            'sector_ids': sector_ids,
            'category_id': category_id,
            'agent_ids': agent_ids

        }
