from odoo import fields, models, api, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    wht_payment_ids = fields.Many2many('account.wht', string="WHT Taxes")
    override_wht = fields.Boolean(string='Override WHT')
    wht_amount = fields.Monetary(string='WHT Amount', compute='_compute_wht_amount')
    after_wh_payment_amount = fields.Monetary(string='Net Payment', compute='_compute_wht_amount')

    @api.onchange('override_wht')
    def _onchange_override_wht(self):
        if self.override_wht:
            self.wht_payment_ids = False

    @api.depends('amount', 'wht_payment_ids')
    def _compute_wht_amount(self):
        for wizard in self:
            wht_total = 0.0
            
            for wht in wizard.wht_payment_ids:
                if wht.amount_type == 'percent':
                    wht_total += (wizard.amount * wht.amount) / 100
                else:
                    wht_total += wht.amount

            wizard.wht_amount = wht_total
            wizard.after_wh_payment_amount = wizard.amount - wht_total

    def _create_payment_vals_from_wizard(self, batch_result):
        res = super()._create_payment_vals_from_wizard(batch_result)
        
        if self.wht_payment_ids:
            res['wht_payment_ids'] = [(6, 0, self.wht_payment_ids.ids)]
            res['override_wht'] = self.override_wht
        
        return res