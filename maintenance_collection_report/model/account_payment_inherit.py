from odoo import models, fields, api, _


class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    payment_amount_cal = fields.Float(compute='_compute_payment_amount_cal', string='Payment Amount Calculation')

    @api.depends('multi_invoice_ids')
    def _compute_payment_amount_cal(self):
        for payment in self:
            total_payment_amount = 0.0
            for invoice in payment.multi_invoice_ids:
                if invoice.invoice_id.property_invoice_type in ['maintenance_charges', 'society_charges']:
                    for line in invoice.invoice_id.invoice_line_ids:
                        if line.product_id.id == 103:
                            total_payment_amount += invoice.payment_amount
                            break
            payment.payment_amount_cal = total_payment_amount
