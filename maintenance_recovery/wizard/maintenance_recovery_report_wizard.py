from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class MaintenanceRecovery(models.TransientModel):
    _name = 'maintenance.recovery.report'
    _description = "Recovery Report"

    def filter_unit_category_type_ids(self):
        distinct_unit_category_type_ids = self.env['file'].search([]).mapped('unit_category_type_id').ids
        return [('id', 'in', distinct_unit_category_type_ids)]

    product_id = fields.Many2many('unit.category.type', domain=lambda self: self.filter_unit_category_type_ids())
    sector_ids = fields.Many2many('sector')
    size_id = fields.Many2one('unit.size')
    # Odoo 19: 'unit.type' is not, and never was, a model anywhere in this codebase (verified
    # across staging/midlanddev and mindland/real_estate) - this Many2one to a non-existent
    # model would raise on module load. The rest of the codebase uses 'unit.class' for this
    # exact "Type" concept (e.g. real_estate crm_lead_ext.py: unit_class_id = Many2one('unit.class', 'Type', ...)),
    # so this is repointed to 'unit.class' to match. Original line kept below for reference.
    # type_id = fields.Many2one('unit.type')
    type_id = fields.Many2one('unit.class')
    date_from = fields.Date(default=lambda self: (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Date To', default=fields.Date.today())

    def print(self):
        datas = {
            'sector_ids': self.sector_ids.ids,
            'product_id': self.product_id.ids,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'size_id': self.size_id.id,
            'type_id': self.type_id.id,
        }
        return self.env.ref("maintenance_recovery.action_maintenance_recovery_report").report_action(self, data=datas)
