# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # read by maintenance.bill.generate._cron_generate_utility_bills (Generate Monthly Utility Bills)
    auto_utility_bills = fields.Boolean(
        string='Automatic Utility Bills', config_parameter='maintenance_monthly_bill.auto_utility_bills')
    auto_utility_day = fields.Integer(
        string='Generate On Day', default=1, config_parameter='maintenance_monthly_bill.auto_utility_day')
    auto_utility_due_day = fields.Integer(
        string='Due On Day', default=10, config_parameter='maintenance_monthly_bill.auto_utility_due_day')

    def action_generate_utility_bills_now(self):
        """Settings button: make this month's draft utility bills now, whatever the day."""
        self.execute()
        report = self.env['maintenance.bill.generate']._cron_generate_utility_bills(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Utility bills generated'),
                'message': '\n'.join(report),
                'sticky': True,
                'next': self.env.ref('maintenance_monthly_bill.action_maintenance_bill_utility').read()[0],
            },
        }
