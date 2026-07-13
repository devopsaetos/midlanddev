# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date
import isoweek
import json
import io
from pytz import timezone

from odoo import _, api, fields, models
from odoo.fields import Date
from odoo.tools import date_utils
from odoo.exceptions import UserError


class MaintenanceRecoveryWizard(models.TransientModel):
    _name = 'maintenance.recovery.wizard'
    _description = 'Wizard to generate custom maintenance recovery reports'

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('society_id.id','=',society_id)]")
    sector_ids = fields.Many2many('sector')
    category_id = fields.Many2one('plot.category', 'Category')
    product_id = fields.Many2one('unit.category.type', 'Product')
    date_from = fields.Date('Start Date')
    date_to = fields.Date(string='End Date')
    agent_ids = fields.Many2many('res.users', string="Recovery Agent")

    def process_report(self):
        data = {}
        data['form'] = self.read(
            ['society_id', 'phase_id', 'sector_ids', 'category_id', 'product_id', 'date_from', 'date_to', 'agent_ids'])[
            0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(
            ['society_id', 'phase_id', 'sector_ids', 'category_id', 'product_id', 'date_from', 'date_to', 'agent_ids'])[
                                0])
        return self.env.ref('maintenance_recovery_report.action_report_maintenance_recovery_report').report_action(
            self, data=data)
