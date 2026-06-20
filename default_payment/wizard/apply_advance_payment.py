# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
# MAP_INVOICE_TYPE_PARTNER_TYPE was removed in Odoo 14+; define it inline
MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}
from odoo.exceptions import UserError, ValidationError


class ApplyAdvancePayments(models.TransientModel):
    _name = 'apply.advance.payment'
    _description = 'Apply Advance Payments'
    _rec_name = 'partner_id'

    journal_id = fields.Many2one('account.journal', string='Application Journal', required=True)
    date = fields.Date(string='Application Date', required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')])
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    invoice_residual = fields.Monetary(
        string='Total Invoice Balances',
        currency_field='currency_id',
        readonly=True)
    advance_payment_total = fields.Monetary(
        compute='_get_advance_payment_total',
        string='Amount To Pay',
        currency_field='currency_id')

    adjust_amount_total = fields.Monetary(
        compute='_get_advance_payment_total',
        string='Total Advance Payments',
        currency_field='currency_id')

    advance_payment_residual = fields.Monetary(
        compute='_get_advance_payment_total',
        string='Remaining Advance Payments',
        currency_field='currency_id')
    advance_payment_ids = fields.Many2many(
        'account.payment', 'account_advance_payment_invoice_rel',
        'advance_payment_invoice_id', 'payment_id',
        'Advance Payments', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
         default=lambda self: self.env.company)

    @api.depends('advance_payment_ids')
    def _get_advance_payment_total(self):
        for record in self:
            payment_residual = 0.0
            amount_to_adjust = 0.0
            for payment in record.advance_payment_ids:
                if payment.amount_to_adjust > 0 and payment.amount_to_adjust > payment.amount_residual:
                    raise ValidationError("You cannot adjust more than remaining amount.")
                payment_currency = payment.currency_id
                payment_date = payment.date
                if record.currency_id != payment_currency:
                    payment_residual += payment_currency._convert(
                        payment.amount_residual, record.currency_id,
                        record.company_id, payment_date)
                    amount_to_adjust += payment.amount_to_adjust

                else:
                    payment_residual += payment.amount_residual
                    amount_to_adjust += payment.amount_to_adjust

            record.advance_payment_total = payment_residual
            record.adjust_amount_total = amount_to_adjust
            record.advance_payment_residual = (payment_residual > amount_to_adjust
                                               and payment_residual - amount_to_adjust
                                               or 0.0)

    @api.onchange('company_id')
    def _onchange_company(self):
        self.journal_id = self.company_id.advance_payment_journal_id.id

    @api.model
    def default_get(self, fields):
        rec = super(ApplyAdvancePayments, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')

        # Checks on context parameters
        if not active_model or not active_ids:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_ids in context."))
        if active_model != 'account.move':
            raise UserError(
                _("Programmation error: the expected model for this action is 'account.move'. The provided one is '%d'.") % active_model)

        # Checks on received invoice records
        invoices = self.env[active_model].browse(active_ids)
        if any(inv.partner_id != invoices[0].partner_id for inv in invoices):
            raise UserError(
                _("In order to pay multiple invoices at once, invoices should have the same partner."))

        if any(MAP_INVOICE_TYPE_PARTNER_TYPE.get(inv.move_type) != MAP_INVOICE_TYPE_PARTNER_TYPE.get(invoices[0].move_type) for inv in invoices):
            raise UserError(
                _("You cannot mix customer invoices and vendor bills in a single payment."))
        if any(inv.currency_id != invoices[0].currency_id for inv in invoices):
            raise UserError(
                _("In order to pay multiple invoices at once, they must use the same currency."))

        rec.update({
            'company_id': invoices[0].company_id.id,
            'currency_id': invoices[0].currency_id.id,
            'invoice_residual': sum(inv.amount_residual for inv in invoices),
            'partner_id': invoices[0].partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE.get(invoices[0].move_type, 'customer')
        })
        return rec

    def apply_advance_payment(self):
        for record in self:
            if (record.advance_payment_total > record.invoice_residual
                    and len(record.advance_payment_ids) > 1):
                error = ('Multiple application of advance payments that '
                         'exceed the invoice balance is not yet supported')
                raise ValidationError(_(error))

            if record.advance_payment_ids.amount_to_adjust > record.invoice_residual:
                raise ValidationError(_('You cannot adjust more than invoice remaining amount %s.' %(record.invoice_residual)))

            partner_id = self.env['res.partner']._find_accounting_partner(record.partner_id).id
            invoices = self.env['account.move'].browse(self._context.get('active_ids'))
            invoice_move_lines = invoices.mapped('line_ids')
            invoice_move_lines = invoice_move_lines.filtered(
                lambda r: not r.reconciled and r.account_id.account_type in ('asset_receivable', 'liability_payable'))

            advance_payment_accounts = self.env['account.account']
            payment_move_line = {}
            for payment in record.advance_payment_ids:
                payment.amount_to_adjust = 0
                payment_account = payment.advance_payment_account_id
                advance_payment_accounts |= payment_account
                if payment.id not in payment_move_line:
                    payment_move_line[payment.id] = self.env['account.move.line']
                payment_move_line[payment.id] |= payment.move_id.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id == payment_account)
                payment.write({'invoice_ids': [(4, x.id, None) for x in invoices]})

            advance_payment_move_lines = []
            advance_payment_residual = record.advance_payment_total - record.advance_payment_residual
            counterpart_balance = currency_exchange_diff = 0.0
            currency_company = record.company_id.currency_id
            payment_move_lines = self.env['account.move.line']
            payment_id = False
            for lines in payment_move_line.values():
                payment_move_lines |= lines
                for line in lines:
                    payment_id = line.payment_id
                    balance = abs(line.balance)
                    currency = line.currency_id or currency_company
                    currency_invoice = record.currency_id
                    payment_date = line.payment_id.date

                    if currency_company != currency_invoice:
                        advance_payment_residual = currency_invoice._convert(
                            advance_payment_residual, currency_company,
                            record.company_id, payment_date)

                    balance_now = balance_used = min(
                        balance, advance_payment_residual)
                    if currency != currency_company and balance:
                        if line.amount_currency:
                            amount_currency = abs(
                                line.amount_currency * (balance_used / balance))
                        else:
                            amount_currency = balance_used
                        balance_now = currency._convert(
                            amount_currency, currency_company, record.company_id, payment_date)

                    if currency != currency_invoice:
                        balance_now = currency._convert(
                            balance_now, currency_invoice, record.company_id, payment_date)
                        balance_now = currency_invoice._convert(
                            balance_now, currency, record.company_id, payment_date)

                    counterpart_balance += balance_now
                    currency_exchange_diff += balance_now - balance_used

                    if record.partner_type == 'customer':
                        credit = 0.0
                        debit = balance_used
                        advance_payment_residual -= debit
                    else:
                        debit = 0.0
                        credit = balance_used
                        advance_payment_residual -= credit

                    if currency_company != currency_invoice:
                        advance_payment_residual = currency_company._convert(
                            advance_payment_residual, currency_invoice, record.company_id, payment_date)

                    if credit or debit:
                        advance_payment_move_lines.append((0, 0, {
                            'name': 'Advance Payment: %s' % ', '.join(lines.mapped('move_id').mapped('name')),
                            'account_id': line.account_id.id,
                            'partner_id': partner_id,
                            'debit': debit,
                            'credit': credit,
                            'payment_id': payment_id.id,
                            'is_advance_payment_account': True,
                        }))

            if counterpart_balance:
                if record.partner_type == 'customer':
                    account_id = record.partner_id.property_account_receivable_id
                elif record.partner_type == 'supplier':
                    account_id = record.partner_id.property_account_payable_id
                else:
                    raise ValidationError(_("Partner type is neither customer nor supplier"))
                advance_payment_move_lines.append((0, 0, {
                    'name': 'Advance Payment: %s' % ', '.join(invoices.mapped('name')),
                    'account_id': account_id.id,
                    'partner_id': partner_id,
                    'debit': record.partner_type == 'supplier' and counterpart_balance or 0.0,
                    'credit': record.partner_type == 'customer' and counterpart_balance or 0.0,
                    'payment_id': payment_id.id,
                    'is_advance_payment_account': False,
                }))

            if currency_exchange_diff:
                currency_exchange_journal = record.company_id.currency_exchange_journal_id
                if currency_exchange_diff < 0:
                    # default_debit_account_id / default_credit_account_id were removed in Odoo 14+;
                    # use default_account_id for both debit and credit exchange difference accounts.
                    currency_exchange_account = currency_exchange_journal.default_account_id
                    if record.partner_type == 'supplier':
                        credit = 0.0
                        debit = abs(currency_exchange_diff)
                    else:
                        credit = abs(currency_exchange_diff)
                        debit = 0.0
                else:
                    currency_exchange_account = currency_exchange_journal.default_account_id
                    if record.partner_type == 'supplier':
                        credit = currency_exchange_diff
                        debit = 0.0
                    else:
                        credit = 0.0
                        debit = currency_exchange_diff

                advance_payment_move_lines.append((0, 0, {
                    'name': 'Currency Exchange Difference',
                    'account_id': currency_exchange_account.id,
                    'partner_id': partner_id,
                    'debit': debit,
                    'credit': credit,
                    'payment_id': payment_id.id,
                    'is_advance_payment_account': False,
                }))

            if advance_payment_move_lines:
                name = record.journal_id.with_context(
                    ir_sequence_date=record.date).sequence_id.next_by_id()
                move = self.env['account.move'].with_context(skip_validation=True).create({
                    'name': name,
                    'date': record.date,
                    'company_id': record.company_id.id,
                    'journal_id': record.journal_id.id,
                    'line_ids': advance_payment_move_lines,
                })
                move.action_post()

                invoice_payment_move_lines = move.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id.account_type in ('asset_receivable', 'liability_payable'))
                advance_payment_move_lines = move.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id in
                    advance_payment_accounts)

                (invoice_payment_move_lines + invoice_move_lines).reconcile()
                (advance_payment_move_lines + payment_move_lines).reconcile()
                if invoices:
                    for rec in invoices:
                        if rec.property_invoice_type == 'investment':
                            rec.investment_id.update_investment_related_payment_data()

                return {
                    'type': "ir.actions.act_window",
                    'res_model': 'account.move',
                    'res_id': self._context.get('active_id'),
                    'context': self._context,
                    'view_mode': 'form',
                    'target': "target",
                }


