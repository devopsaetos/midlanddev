# Copyright 2019 VentorTech OU
# License OPL-1.0 or later.

from odoo import fields, models, api


class CompanyExt(models.Model):
    _inherit = 'res.company'

    maintenance_payment_journal_id = fields.Many2one('account.journal', string='Maintenance Journal')


class SettingsExt(models.TransientModel):
    _inherit = 'res.config.settings'

    maintenance_payment_journal_id = fields.Many2one(
        'account.journal', readonly=False, related='company_id.maintenance_payment_journal_id',
        string='Maintenance Journal', domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', company_id)]")
    # Everything the maintenance invoice / payment flow needs, on one settings page.
    # The two products are read by maintenance.charges._get_*_product_id() from these system parameters.
    maintenance_product_id = fields.Many2one(
        'product.product', string='Maintenance Charges Product',
        config_parameter='maintenance_charges.maintenance_product_id')
    society_product_id = fields.Many2one(
        'product.product', string='Service Charges Product',
        config_parameter='maintenance_charges.society_product_id')
    maintenance_invoice_journal_id = fields.Many2one(
        'account.journal', readonly=False, related='company_id.account_journal_id',
        string='Maintenance Invoice Journal', domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]")

    def set_values(self):
        super(SettingsExt, self).set_values()
        if self.maintenance_payment_journal_id:
            self.env.company.sudo().maintenance_payment_journal_id = self.maintenance_payment_journal_id
            # payment screens only offer journals flagged "Show in Maintenance"
            self.maintenance_payment_journal_id.sudo().show_in_maintenance = True


class MaintenanceChargesPaymentExt(models.Model):
    _inherit = 'maintenance.charges.payment'

    def _default_maintenance_journal(self):
        # the journal chosen in Maintenance Charges > Configuration > Settings wins
        journal = self.env.company.maintenance_payment_journal_id
        if journal and journal.type in ('cash', 'bank'):
            return journal
        return super()._default_maintenance_journal()
