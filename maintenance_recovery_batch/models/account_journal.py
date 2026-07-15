from odoo import api, fields, models, _


class AccountJournalExt(models.Model):
    _inherit = "account.journal"

    show_in_maintenance = fields.Boolean(default=False, string="Show in Maintenance", tracking=True)

