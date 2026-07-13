# Copyright 2019 VentorTech OU
# License OPL-1.0 or later.

from odoo import fields, models, api


class CompanyExt(models.Model):
    _inherit = 'res.company'

    maintenance_payment_journal_id = fields.Many2one('account.journal', string='Maintenance Journal')


class SettingsExt(models.TransientModel):
    _inherit = 'res.config.settings'

    maintenance_payment_journal_id = fields.Many2one('account.journal', readonly=False, related='company_id.maintenance_payment_journal_id', string='Maintenance Journal')

    def set_values(self):
        super(SettingsExt, self).set_values()
        if self.maintenance_payment_journal_id:
            self.env.company.sudo().maintenance_payment_journal_id = self.maintenance_payment_journal_id
