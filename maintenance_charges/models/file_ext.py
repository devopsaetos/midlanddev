from odoo import fields, models, api


class FileExt(models.Model):
    _inherit = 'file'

    maintenance_history_ids = fields.One2many('maintenance.charges.history', 'file_id')
    maintenance_recovery_agent_id = fields.Many2one('res.users', domain="[('maintenance_recovery_agent', '=', True)]")
    service_charge = fields.Boolean(string='Service charge', default=False)
    assumption = fields.Boolean(string='Assumption', default=False)
    exemption = fields.Boolean(string='Exemption', default=False)

    def _maintenance_arrears(self, charge_type, before_date):
        """Outstanding amount of one charge type ('utility' / 'electricity') before a date.

        Imported Excel history stores a running balance (each row already includes the
        arrears before it), so only the latest imported row's residual counts. Rows that
        come from real invoices count with the invoice's live residual."""
        self.ensure_one()
        history = self.maintenance_history_ids.filtered(
            lambda h: h.charge_type == charge_type and h.date and h.date < before_date)
        imported = history.filtered(lambda h: not h.invoice_id).sorted(lambda h: (h.date, h.id))
        opening = imported[-1].residual if imported else 0.0
        # each invoice row carries its own share of the invoice (one invoice can hold
        # utility and electricity)
        billed = history.filtered(lambda h: h.invoice_id and h.invoice_id.state == 'posted')
        return opening + sum(billed.mapped('residual'))
