# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    wht_payment_ids = fields.Many2many('account.wht', string='WHT Taxes')
    wht_ids_domain_ids = fields.Many2many('account.wht', 'account_payment_wht_rel', 'payment_id', 'wht_id')
    override_wht = fields.Boolean('Override WHT')
    payment_amount = fields.Monetary(related='move_id.amount_total', string='Total Amount')
    wht_amount = fields.Monetary(compute='_compute_wht_amount')
    after_wh_payment_amount = fields.Monetary(string='Net Payment', compute='_compute_wht_amount')



    @api.onchange('override_wht')
    def _onchange_override_wht(self):
        if self.override_wht:
            self.wht_payment_ids = False

    @api.depends('amount', 'wht_payment_ids')
    def _compute_wht_amount(self):
        for payment in self:
            wht_total = 0.0
            
            for wht in payment.wht_payment_ids:
                if wht.amount_type == 'percent':
                    wht_total += (payment.amount * wht.amount) / 100
                else:
                    wht_total += wht.amount

            payment.wht_amount = wht_total
            payment.after_wh_payment_amount = payment.amount - wht_total

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """Override to add WHT lines and ensure balanced entries."""
        line_vals_list = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance)
        
        if self.wht_payment_ids and len(line_vals_list) >= 2:
            total_wht = 0.0
            
            for wht in self.wht_payment_ids:
                if wht.amount_type == 'percent':
                    wht_amount = (self.amount * wht.amount) / 100
                else:
                    wht_amount = wht.amount
                total_wht += wht_amount
                
                if self.payment_type == 'outbound':
                    wht_debit = 0.0
                    wht_credit = wht_amount
                    wht_amount_currency = -wht_amount
                else:
                    wht_debit = wht_amount
                    wht_credit = 0.0
                    wht_amount_currency = wht_amount
                
                line_vals_list.append({
                    'name': f'WHT: {wht.name}',
                    'account_id': wht.account_id.id,
                    'debit': wht_debit,
                    'credit': wht_credit,
                    'amount_currency': wht_amount_currency,
                    'currency_id': self.currency_id.id,
                    'partner_id': self.partner_id.id,
                })
            
            if total_wht > 0:
                liquidity_line = line_vals_list[0]
                liquidity_line['amount_currency'] += total_wht if self.payment_type == 'outbound' else -total_wht
                liquidity_line['debit'] = liquidity_line['amount_currency'] if liquidity_line['amount_currency'] > 0 else 0.0
                liquidity_line['credit'] = -liquidity_line['amount_currency'] if liquidity_line['amount_currency'] < 0 else 0.0
        
        return line_vals_list
