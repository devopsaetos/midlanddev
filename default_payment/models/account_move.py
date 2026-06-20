# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_name(self):
        # domain="[('supplier_rank','>', 0)]"
        # domain="[('customer_rank','>', 0)]"
        domain = False
        if self.env.context.get('default_type', 'entry') in ('out_invoice', 'out_refund', 'out_receipt'):
            domain = [('customer_rank','>', 0)]
        elif self.env.context.get('default_type', 'entry') in ('in_invoice', 'in_refund', 'in_receipt'):
            domain = [('supplier_rank','>', 0)]
        if domain:
            return domain + ['|',('company_id','=',False),('company_id','=',self.env.company.id)]

    # payment_state selection_add removed — it is a computed stored field in Odoo 14+ and cannot be extended this way
    partner_id = fields.Many2one('res.partner', readonly=True, tracking=True,
                                 domain=lambda l:l._compute_name(),
                                 string='Partner', change_default=True)

    advance_payment_ids = fields.Many2many(
        'account.payment',
        'account_move__account_payment',
        'invoice_id',
        'payment_id',
        string='Advance Payments',
        domain=[('is_advance_payment', '=', True)],
        copy=False, readonly=True)

    adv_should_visible = fields.Boolean(compute='_adv_should_visible')

    has_advance_payment = fields.Boolean(
        compute='_has_advance_payment',
        string='Has advance payment?')

    adv_payment_move_line_ids = fields.Many2many(
        'account.move.line',
        'adv_payment_move_line_rel',
        'move_id',
        'line_id',
        string='Advance Payment Move Lines',
        compute='_compute_payments',
        store=True)

    def _adv_should_visible(self):
        for invoice in self:
            if invoice.state == 'posted' \
                    and invoice.has_advance_payment == True \
                    and invoice.payment_state != 'paid':
                invoice.adv_should_visible = True
            else:
                invoice.adv_should_visible = False

    @api.depends('line_ids.matched_credit_ids', 'line_ids.matched_debit_ids')
    def _compute_payments(self):
        for move in self:
            payment_lines = set()
            for line in move.line_ids:
                payment_lines.update(line.mapped('matched_credit_ids.credit_move_id.id'))
                payment_lines.update(line.mapped('matched_debit_ids.debit_move_id.id'))
            move.adv_payment_move_line_ids = self.env['account.move.line'].browse(list(payment_lines))

    def _get_advance_payment_amount(self):
        self.ensure_one()
        advance_payment_amount = 0.0

        for payment in self.adv_payment_move_line_ids:
            if not payment.move_id.line_ids.filtered('is_advance_payment_account'):
                continue

            payment_currency_id = False
            if self.move_type in ('out_invoice', 'in_refund'):
                amount = sum([p.amount for p in payment.matched_debit_ids if p.debit_move_id in payment.move_id.line_ids])
                amount_currency = sum(
                    [p.amount_currency for p in payment.matched_debit_ids if p.debit_move_id in payment.move_id.line_ids])
                if payment.matched_debit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_debit_ids[0].currency_id for p in
                                               payment.matched_debit_ids]) and payment.matched_debit_ids[
                                              0].currency_id or False
            elif self.move_type in ('in_invoice', 'out_refund'):
                amount = sum(
                    [p.amount for p in payment.matched_credit_ids if p.credit_move_id in self.move_id.line_ids])
                amount_currency = sum([p.amount_currency for p in payment.matched_credit_ids if
                                       p.credit_move_id in self.move_id.line_ids])
                if payment.matched_credit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_credit_ids[0].currency_id for p in
                                               payment.matched_credit_ids]) and payment.matched_credit_ids[
                                              0].currency_id or False

            # get the payment value in invoice currency
            if payment_currency_id and payment_currency_id == self.currency_id:
                amount_to_show = amount_currency

            else:
                amount_to_show = payment.company_id.currency_id.with_context(date=payment.date).compute(amount,
                                                                                                        self.currency_id)
            if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                continue

            advance_payment_amount += amount_to_show
        return advance_payment_amount

    @api.depends('partner_id', 'company_id', 'line_ids')
    def _has_advance_payment(self):
        for invoice in self:
            advance_payment_args = [
                ('company_id', '=', invoice.company_id.id),
                ('is_advance_payment', '=', True),
                ('partner_id', '=', invoice.partner_id.id),
                ('amount_residual', '!=', 0.0),
                ('state', '=', 'posted'),
            ]
            if self.env['account.payment'].search(advance_payment_args):
                invoice.has_advance_payment = True
            else:
                invoice.has_advance_payment = False

    # button_cancel override removed — account.move.button_cancel() was removed in Odoo 14+
    # and adding lines to a posted move is not allowed. Standard cancel behaviour is sufficient.


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_advance_payment_account = fields.Boolean(string='Is advance payment?', default=False)

    reconcile_invoice_id = fields.Many2one('account.move')

    def remove_move_reconcile(self):
        """Overridden - this method was removed in Odoo 14+. Kept as stub for compatibility."""
        return super(AccountMoveLine, self).remove_move_reconcile() if hasattr(super(), 'remove_move_reconcile') else True
