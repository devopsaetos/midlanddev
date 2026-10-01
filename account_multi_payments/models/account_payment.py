from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    multi_payment_check = fields.Boolean(string="Multi Payment")
    multi_invoice_payment_ids = fields.One2many('multi.invoice.payment', 'payment_id', string="Multi Invoices")

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.multi_payment_check and self.partner_id:
            self._update_multi_invoice_lines()
        elif self.payment_category == 'multi_inv_payment':
            # default_payment's Multi Invoice Payment flow loads the partner's open
            # invoices/bills into multi_invoice_ids - this override used to hide it
            return super()._onchange_partner_id()

    def _update_multi_invoice_lines(self):
        if not self.partner_id:
            self.multi_invoice_payment_ids = [(5, 0, 0)]
            return

        invoice_types = ['out_invoice'] if self.payment_type == 'inbound' else ['in_invoice']
        invoices = self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('move_type', 'in', invoice_types)
        ])

        lines = [(0, 0, {'invoice_id': inv.id, 'payment_amount': inv.amount_residual}) for inv in invoices]
        self.multi_invoice_payment_ids = lines

    @api.onchange('multi_invoice_payment_ids')
    def _onchange_multi_invoice_payment_ids(self):
        if self.multi_payment_check and self.multi_invoice_payment_ids:
            self.amount = sum(self.multi_invoice_payment_ids.mapped('payment_amount'))

    def action_post(self):
        res = super().action_post()
        for payment in self:
            if payment.multi_payment_check and payment.multi_invoice_payment_ids:
                payment._reconcile_multi_invoices()
        return res

    def _reconcile_multi_invoices(self):
        for line in self.multi_invoice_payment_ids.filtered(lambda l: l.payment_amount > 0):
            payment_lines = self.move_id.line_ids.filtered(
                lambda l: l.account_id == self.destination_account_id and not l.reconciled
            )
            invoice_lines = line.invoice_id.line_ids.filtered(
                lambda l: l.account_id == self.destination_account_id and not l.reconciled
            )
            if payment_lines and invoice_lines:
                (payment_lines[0] + invoice_lines[0]).reconcile()

