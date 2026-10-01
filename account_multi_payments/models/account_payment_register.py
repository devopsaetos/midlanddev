from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payment_vals_from_wizard(self, batch_result):
        res = super()._create_payment_vals_from_wizard(batch_result)
        
        if len(self.line_ids) == 1:
            res['multi_payment_check'] = True
            res['multi_invoice_payment_ids'] = [(0, 0, {
                'invoice_id': self.line_ids[0].move_id.id,
                'payment_amount': self.amount,
            })]
        
        return res
