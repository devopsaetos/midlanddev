from odoo import api, fields, models, _


class ResConfigSettingsAccounting(models.TransientModel):
    _inherit = 'res.config.settings'

    unit_booking_journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ['cash', 'bank'])],
                                              readonly=False, related='company_id.unit_booking_journal_id')


class ResCompany(models.Model):
    _inherit = "res.company"

    unit_booking_journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ['cash', 'bank'])],
                                              readonly=False)
