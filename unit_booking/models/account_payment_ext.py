from odoo import fields, models, api


class AccountPaymentExt(models.Model):
    _inherit = 'account.payment'

    advance_against = fields.Selection(selection_add=[('dealer', 'Dealer')])
    booking_allotment_id = fields.Many2one('unit.booking.allotment')

    def action_post(self):
        res = super(AccountPaymentExt, self).action_post()

        if self.multi_invoice_ids:
            for rec in self.multi_invoice_ids:
                if rec.invoice_id.open_file_issuance_id and rec.invoice_id.payment_state == 'paid':
                    rec.invoice_id.open_file_issuance_id.invoice_paid = True
        return res

    @api.onchange('file_id', 'investment_id', 'booking_allotment_id')
    def onchange_advance_against(self):
        res = super(AccountPaymentExt, self).onchange_advance_against()
        for rec in self:
            if rec.booking_allotment_id:
                rec.partner_id = rec.booking_allotment_id.partner_id.id

    def multi_line_domain(self):
        res = super(AccountPaymentExt, self).multi_line_domain()
        if self.booking_allotment_id and self.partner_id:
            return self.multi_invoice_ids.search([
                ('partner_id', '=', self.partner_id.id),
                ('invoice_id.booking_allotment_id', '=', self.booking_allotment_id.id),
                ('state', '=', 'posted'),
                ('active', '=', True),
                ('payment_id', '=', False),
                ('payment_state', '!=', 'paid'),
                ('type', 'in',
                 ['out_invoice', 'in_refund'] if self.payment_type == 'inbound' else ['in_invoice', 'out_refund'])
            ])
        else:
            return res

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountPaymentExt, self)._onchange_partner_id()
        if self.booking_allotment_id:
            res['domain']['multi_invoice_ids'].append((['invoice_id.booking_allotment_id', '=', self.booking_allotment_id.id]))

        return res