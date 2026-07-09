# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class AccountPaymentExt(models.Model):
    _inherit = "account.payment"

    multi_invoice_ids = fields.Many2many('multi.invoice.payment', 'multi_account_invoice_payment_rel', 'payment_id', 'invoice_id', string="Invoices",
                                         copy=False,
                                         readonly=False,
                                         help="""Technical field containing the invoices for which the payment has been generated.
                                               This does not especially correspond to the invoices reconciled with the payment,
                                               as it can have been generated first, and reconciled later""")
    file_id = fields.Many2one('file')
    payment_nature = fields.Selection([('normal', 'Normal Payment'), ('on_account', 'On Account')], default="normal", string="Payment Nature", tracking=True)
    advance_payment_id = fields.Many2one('account.payment', tracking=True)
    category_id = fields.Many2one('plot.category', string="Category", tracking=True)
    invoice_creation_quantity = fields.Integer(string="No. of Invoice to Generate",
                                               default=0,
                                               copy=False,
                                               help="""This field will have the Number of Invoices to be generated on the File Installment Plan for their 
                                               settlement in the Current Payment.""", tracking=True)
    apply_discount = fields.Boolean(string="Apply Discount ?", copy=False, default=False, tracking=True)

    discount_policy_id = fields.Many2one('discount.policy', string="Discount Policy", domain=[('state', '=', 'active')], copy=False, tracking=True)
    is_sub_investor_payment = fields.Boolean(string="Sub Dealer Payment", copy=False, default=False, tracking=True)
    sub_investor_id = fields.Many2one('res.investor', string="Sub Investor", tracking=True)

    @api.onchange('payment_nature', 'file_id')
    def change_advance_payment_domain(self):
        if self.file_id:
            self.category_id = self.file_id.category_id.id
            return {'domain': {
                'advance_payment_id': [('is_advance_payment', '=', True), ('partner_id', '=', self.file_id.investor_id.partner_id.id), ('amount_residual', '>', 0)]
            }
            }

    @api.onchange('advance_payment_id')
    def change_lines_account_id(self):
        if self.file_id and self.payment_nature == 'on_account':
            self.journal_id = self.env.company.confirmation_adjustment_journal_id.id

    def send_sms(self):
        # pass
        # message = f"Your Five digit otp number is : {otp.auth_otp}"
        # number = otp.partner_id.mobile
        if self.payment_type in ('outbound', 'inbound'):
        # if self.company_id.id != 1 and self.payment_type in ('outbound', 'inbound'):
            message_body = ""
            received_against = " "
            if self.payment_type == 'inbound':  # Received
                if not self.is_advance_payment:
                    if self.file_id:
                        received_against = "  against File - " + self.file_id.name
                    if self.investment_id:
                        received_against = " against Investment - " + self.investment_id.sequence_no
                else:
                    if self.advance_against in ('dealer', 'other'):
                        received_against = " "
                    else:
                        if self.file_id:
                            received_against = "  against Advance of File - " + self.file_id.name
                        if self.investment_id:
                            received_against = " against Advance of Investment - " + self.investment_id.sequence_no
                message_body = f"Payment of amount RS {self.amount}  has been received from {self.partner_id.name}{received_against}"
            if self.payment_type == 'outbound':  # Paid
                received_against = "  against - " + self.communication if self.communication else " "
                message_body = f"Payment of amount RS {self.amount}  has been paid to {self.partner_id.name}{received_against}"
            # number = self.company_id.owner_mobile
            if self.company_id.mobile_numbers:
                for mobile in self.company_id.mobile_numbers:
                    message = f"Dear {mobile.name},\n {message_body}"
                    #self.env['tools.mixin'].sudo().simple_send(message, mobile.number)

    # def post(self):
    #     self.check_advance()
    #     # self.check_amount_residuals()
    #     new_data = []
    #     AccountMove = self.env['account.move'].with_context(default_type='entry')
    #     for rec in self:
    #         rec.send_sms()
    #         # if type is transfer then it will auto post the payment of receiving bank
    #         if rec.payment_type not in ('inbound', 'outbound') or self.payment_category == 'transfer':
    #             res = super(AccountPaymentExt, self).post()
    #             for record in rec.move_line_ids.move_id:
    #                 if record:
    #                     if record.state == 'draft':
    #                         new_data.append(record.id)
    #                     AccountMove.browse(new_data).action_post()
    #             return res
    #         elif rec.payment_type not in ('inbound', 'outbound') or self.payment_category != 'multi_inv_payment':
    #             return super(AccountPaymentExt, self).post()
    #         if rec.state != 'draft':
    #             raise UserError(_("Only a draft payment can be posted."))
    #
    #         if any(inv.state != 'posted' for inv in rec.multi_invoice_ids):
    #             raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))
    #
    #         if rec.multi_invoice_ids:
    #             rec.validate_lines()
    #         # keep the name in case of a payment reset to draft
    #         if not rec.name:
    #             sequence_code = ''
    #             if rec.partner_type == 'customer':
    #                 if rec.payment_type == 'inbound':
    #                     sequence_code = 'account.payment.customer.invoice'
    #                 if rec.payment_type == 'outbound':
    #                     sequence_code = 'account.payment.customer.refund'
    #             if rec.partner_type == 'supplier':
    #                 if rec.payment_type == 'inbound':
    #                     sequence_code = 'account.payment.supplier.refund'
    #                 if rec.payment_type == 'outbound':
    #                     sequence_code = 'account.payment.supplier.invoice'
    #             rec.name = self.env['ir.sequence'].next_by_code(sequence_code, sequence_date=rec.payment_date)
    #             if not rec.name and rec.payment_type != 'transfer':
    #                 raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))
    #
    #         moves = AccountMove.create(rec._prepare_payment_moves())
    #         moves.filtered(lambda move: move.journal_id.post_at != 'bank_rec').post()
    #
    #         # Update the state / move before performing any reconciliation.
    #         move_name = self._get_move_name_transfer_separator().join(moves.mapped('name'))
    #         rec.write({'state': 'posted', 'move_name': move_name})
    #         # ==== 'inbound' / 'outbound' ====
    #         if rec.multi_invoice_ids:
    #             rec.update_open_files_payments()
    #             for acc in rec.multi_invoice_ids:
    #                 # Working For File Payments
    #                 if acc.invoice_id.investment_id:
    #                     investment_history = acc.invoice_id.investment_id.investment_history_ids[0]
    #                     investment_history.payment_received = investment_history.payment_received + acc.payment_amount
    #                     investment_history.payment_date = self.payment_date
    #                     if acc.invoice_id.investment_id.options == 'full':
    #                         acc.invoice_id.investment_id.amount_paid = acc.invoice_id.investment_id.amount_paid + acc.payment_amount
    #                 if acc.invoice_id.token_id and acc.invoice_id.payment_state == 'paid':
    #                     acc.invoice_id.token_id.token_paid = True
    #                     acc.invoice_id.token_id.state = 'adjusted' if acc.invoice_id.token_id.create_open_file == True else 'paid'
    #                     acc.invoice_id.token_id.open_file_amount_received = True
    #                 if acc.invoice_id.file_ids.payment_type == 'installments':
    #                     acc.invoice_id.file_ids.payment_states = 'open'
    #                 if acc.invoice_id.file_ids.payment_type == 'lump_sum':
    #                     acc.invoice_id.file_ids.overall_status = 'close'
    #                 if acc.invoice_id.transfer_application_id and acc.invoice_id.invoice_line_ids.product_id == self.env.ref('real_estate.file_transfer'):
    #                     acc.invoice_id.transfer_application_id.payment_received = True
    #                 if acc.invoice_id.unit_swap_request_id and acc.invoice_id.amount_residual == 0.00:
    #                     acc.invoice_id.unit_swap_request_id.invoice_paid = True
    #                 # Working For File Payments Ends Here
    #                 (moves[0].line_ids.filtered(lambda line: line.reconcile_invoice_id.id == acc.invoice_id.id) + acc.invoice_id.line_ids).filtered(
    #                     lambda line: not line.reconciled and line.account_id == rec.destination_account_id and not (
    #                             line.account_id == acc.writeoff_account_id and line.name.startswith('Write-Off'))).reconcile()
    #
    #                 if acc.payment_difference_handling == 'advance_payment':
    #                     adv_pay = self.create({
    #                         'payment_method_id': self.payment_method_id.id,
    #                         'payment_category': 'advance_payment',
    #                         'base_payment_id': rec.id,
    #                         'partner_id': rec.partner_id.id,
    #                         'payment_type': rec.payment_type,
    #                         'partner_type': rec.partner_type,
    #                         'payment_date': rec.payment_date,
    #                         'currency_id': rec.currency_id.id,
    #                         'cheque_name': rec.cheque_name,
    #                         'cheque_no': rec.cheque_no,
    #                         'bank_ref': rec.bank_ref,
    #                         'mode_of_payments': rec.mode_of_payments,
    #                         'amount': acc.payment_difference * -1,
    #                         'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
    #                         'journal_id': self.env.company.advance_payment_journal_id.id
    #                     })
    #                     adv_pay.post()
    #                 if acc.payment_difference_handling == 'investor_adjustment':
    #                     investor_invoice = self.env['account.move'].search(
    #                         [('investment_id', '=', self.file_id.investment_id.id),
    #                          ('property_invoice_type', '=', 'investment'),
    #                          ('state', '=', 'posted'),
    #                          ('move_type', '=', 'out_invoice')
    #                          ])
    #                     if investor_invoice and investor_invoice.amount_residual > 0:
    #                         total_amount = abs(acc.payment_difference)
    #                         balance = total_amount
    #                         if balance >= investor_invoice.amount_residual or balance <= investor_invoice.amount_residual:
    #                             balance = balance - investor_invoice.amount_residual
    #                             payment = self.env['account.payment'].create({
    #                                 # 'multi_invoice_ids': [(4, multi_invoice_pay)],
    #                                 'amount': investor_invoice.amount_residual if total_amount >= investor_invoice.amount_residual else total_amount,
    #                                 'investment_id': self.file_id.investment_id.id,
    #                                 'partner_id': investor_invoice.partner_id.id,
    #                                 'journal_id': self.env.company.advance_payment_journal_id.id,
    #                                 'mode_of_payments': self.mode_of_payments,
    #                             })
    #                             # multi_invoice_pay = (0, 0, {
    #                             multi_invoice_pay = self.env['multi.invoice.payment'].create({
    #                                 'invoice_id': investor_invoice.id,
    #                                 'payment_due': investor_invoice.amount_residual,
    #                                 'payment_amount': investor_invoice.amount_residual if total_amount >= investor_invoice.amount_residual else total_amount,
    #                                 'payment_id': payment.id
    #                             })
    #                             payment.multi_invoice_ids = [(4, multi_invoice_pay.id)]
    #                             payment.post()
    #                         if balance > 0:
    #                             adv_pay = self.create({
    #                                 'payment_method_id': self.payment_method_id.id,
    #                                 'payment_category': 'advance_payment',
    #                                 'base_payment_id': rec.id,
    #                                 'partner_id': rec.file_id.investment_id.partner_id.id,
    #                                 'payment_type': rec.payment_type,
    #                                 'partner_type': rec.partner_type,
    #                                 'payment_date': rec.payment_date,
    #                                 'currency_id': rec.currency_id.id,
    #                                 'cheque_name': rec.cheque_name,
    #                                 'cheque_no': rec.cheque_no,
    #                                 'bank_ref': rec.bank_ref,
    #                                 'mode_of_payments': rec.mode_of_payments,
    #                                 'amount': balance,
    #                                 'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
    #                                 'journal_id': self.env.company.advance_payment_journal_id.id
    #                             })
    #                             adv_pay.post()
    #                     else:
    #                         adv_pay = self.create({
    #                             'payment_method_id': self.payment_method_id.id,
    #                             'payment_category': 'advance_payment',
    #                             'base_payment_id': rec.id,
    #                             'partner_id': rec.file_id.investment_id.partner_id.id,
    #                             'payment_type': rec.payment_type,
    #                             'partner_type': rec.partner_type,
    #                             'payment_date': rec.payment_date,
    #                             'currency_id': rec.currency_id.id,
    #                             'cheque_name': rec.cheque_name,
    #                             'cheque_no': rec.cheque_no,
    #                             'bank_ref': rec.bank_ref,
    #                             'mode_of_payments': rec.mode_of_payments,
    #                             'amount': abs(acc.payment_difference),
    #                             'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
    #                             'journal_id': self.env.company.advance_payment_journal_id.id
    #                         })
    #                         adv_pay.post()
    #         # rec.check_for_investor_adjustment()
    #         rec.check_for_on_account_entry()
    #         if rec.investment_id and rec.multi_invoice_ids and rec.multi_invoice_ids.filtered(lambda l: l.invoice_id.property_invoice_type == 'investment'):
    #             investment_booking_payment_line = rec.multi_invoice_ids.filtered(lambda l: l.invoice_id.property_invoice_type == 'investment')
    #             payment_amount = investment_booking_payment_line.payment_due if investment_booking_payment_line.payment_amount > investment_booking_payment_line.payment_due else \
    #                 investment_booking_payment_line.payment_amount
    #             # rec.investment_id.update_investment_related_payment_data(payment_amount)
    #             rec.investment_id.update_investment_related_payment_data()
    #
    #     return True

    # ################################################
    # ################################################
    # ################################################
    # ################################################
    # ################################################
    def action_post(self):
        res = super(AccountPaymentExt, self).action_post()
        for rec in self:
            if rec.payment_type == 'inbound' and rec.file_id or rec.investment_id:
                if rec.multi_invoice_ids:
                    # For Difference Account Fetch against different type of action
                    rec.validate_lines()
                    for lines in rec.multi_invoice_ids:
                        # #############################
                        # Create Investor Advance Payment or Adjust Additional Amount in Already Due Investment Invoice
                        if lines.payment_difference_handling == 'investor_adjustment':
                            investor_invoice = self.env['account.move'].search(
                                [('investment_id', '=', rec.file_id.investment_id.id),
                                 ('property_invoice_type', '=', 'investment'),
                                 ('state', '=', 'posted'),
                                 ('move_type', '=', 'out_invoice')
                                 ])
                            if investor_invoice and investor_invoice.amount_residual > 0:
                                total_amount = abs(lines.payment_difference)
                                balance = total_amount
                                if balance >= investor_invoice.amount_residual or balance <= investor_invoice.amount_residual:
                                    balance = balance - investor_invoice.amount_residual
                                    payment = self.env['account.payment'].create({
                                        # 'multi_invoice_ids': [(4, multi_invoice_pay)],
                                        'amount': investor_invoice.amount_residual if total_amount >= investor_invoice.amount_residual else total_amount,
                                        'investment_id': rec.file_id.investment_id.id,
                                        'partner_id': investor_invoice.partner_id.id,
                                        'journal_id': self.env.company.advance_payment_journal_id.id,
                                        'mode_of_payments': self.mode_of_payments,
                                    })
                                    # multi_invoice_pay = (0, 0, {
                                    multi_invoice_pay = self.env['multi.invoice.payment'].create({
                                        'invoice_id': investor_invoice.id,
                                        'payment_due': investor_invoice.amount_residual,
                                        'payment_amount': investor_invoice.amount_residual if total_amount >= investor_invoice.amount_residual else total_amount,
                                        'payment_id': payment.id
                                    })
                                    payment.multi_invoice_ids = [(4, multi_invoice_pay.id)]
                                    payment.action_post()
                                if balance > 0:
                                    adv_pay = self.create({
                                        'payment_method_id': rec.payment_method_id.id,
                                        'payment_category': 'advance_payment',
                                        'base_payment_id': rec.id,
                                        'partner_id': rec.file_id.investment_id.partner_id.id,
                                        'payment_type': rec.payment_type,
                                        'partner_type': rec.partner_type,
                                        'payment_date': rec.payment_date,
                                        'currency_id': rec.currency_id.id,
                                        'cheque_name': rec.cheque_name,
                                        'cheque_no': rec.cheque_no,
                                        'bank_ref': rec.bank_ref,
                                        'mode_of_payments': rec.mode_of_payments,
                                        'amount': balance,
                                        'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
                                        'journal_id': self.env.company.advance_payment_journal_id.id
                                    })
                                    adv_pay.action_post()
                            else:
                                adv_pay = self.create({
                                    'payment_method_id': self.payment_method_id.id,
                                    'payment_category': 'advance_payment',
                                    'base_payment_id': rec.id,
                                    'partner_id': rec.file_id.investment_id.partner_id.id,
                                    'payment_type': rec.payment_type,
                                    'partner_type': rec.partner_type,
                                    'payment_date': rec.payment_date,
                                    'currency_id': rec.currency_id.id,
                                    'cheque_name': rec.cheque_name,
                                    'cheque_no': rec.cheque_no,
                                    'bank_ref': rec.bank_ref,
                                    'mode_of_payments': rec.mode_of_payments,
                                    'amount': abs(lines.payment_difference),
                                    'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
                                    'journal_id': self.env.company.advance_payment_journal_id.id
                                })
                                adv_pay.action_post()
                        # Create Investor Additional Amount Case Ends Here
                        # #############################
                        if lines.invoice_id.investment_id:
                            investment_history = lines.invoice_id.investment_id.investment_history_ids[0]
                            investment_history.payment_received = investment_history.payment_received + lines.payment_amount
                            investment_history.payment_date = rec.payment_date
                            if lines.invoice_id.investment_id.options == 'full':
                                lines.invoice_id.investment_id.amount_paid = lines.invoice_id.investment_id.amount_paid + lines.payment_amount
                        if lines.invoice_id.token_id and lines.invoice_id.payment_state == 'paid':
                            lines.invoice_id.token_id.token_paid = True
                            lines.invoice_id.token_id.state = 'adjusted' if lines.invoice_id.token_id.create_open_file == True else 'paid'
                            lines.invoice_id.token_id.open_file_amount_received = True
                        if lines.invoice_id.file_ids.payment_type == 'installments':
                            lines.invoice_id.file_ids.payment_states = 'open'
                        if lines.invoice_id.file_ids.payment_type == 'lump_sum':
                            lines.invoice_id.file_ids.overall_status = 'close'
                        if lines.invoice_id.transfer_application_id and lines.invoice_id.invoice_line_ids.product_id == self.env.ref(
                                'real_estate.file_transfer'):
                            lines.invoice_id.transfer_application_id.payment_received = True
                        if lines.invoice_id.unit_swap_request_id and lines.invoice_id.amount_residual == 0.00:
                            lines.invoice_id.unit_swap_request_id.invoice_paid = True
                    # Update the Payments on Open Files
                    rec.update_open_files_payments()
                # Check if Investor is Paying on behalf of Customer
                rec.check_for_on_account_entry()
                # For Open Files Booking Payment Adjustment, Trigger Function of Investment
                if rec.investment_id and rec.multi_invoice_ids and rec.multi_invoice_ids.filtered(lambda l: l.invoice_id.property_invoice_type == 'investment'):
                    investment_booking_payment_line = rec.multi_invoice_ids.filtered(lambda l: l.invoice_id.property_invoice_type == 'investment')
                    # payment_amount = investment_booking_payment_line.payment_due if investment_booking_payment_line.payment_amount >
                    # investment_booking_payment_line.payment_due else investment_booking_payment_line.payment_amount
                    # rec.investment_id.update_investment_related_payment_data(payment_amount)
                    rec.investment_id.update_investment_related_payment_data()
                if rec.file_id and rec.multi_invoice_ids:
                    rec.link_payment_to_file()
                    confirmation_line = rec.file_id.installment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation_amount')
                    for line in rec.multi_invoice_ids:
                        if line.invoice_id.property_invoice_type == 'installment' and confirmation_line.invoice_id.id == line.invoice_id.id:
                            confirmation_line.compute_net_payment()
            if self.env.company.send_payment_sms:
                rec.send_sms()
        return res

    def validate_lines(self):
        for line in self.multi_invoice_ids:
            if line.payment_difference_handling == 'advance_payment':
                if line.payment_difference > -1:
                    raise UserError(_("You can not select advance payment while you are not actually paying it"))
                if not line.writeoff_account_id:
                    raise UserError(_("You have to select Advance Payment Account before paying advance payment"))

            if line.payment_difference_handling != 'advance_payment' and line.payment_difference <= -1 and line.invoice_id.type not in [
                'out_refund', 'in_invoice']:
                if line.payment_difference_handling != 'investor_adjustment' and line.invoice_id.type != 'out_invoice':
                    raise UserError(_("You have to select Advance Payment Action when you are actually paying it"))
            if line.payment_difference_handling == 'investor_adjustment':
                if line.payment_difference > -1:
                    raise UserError(_("You can not select Investor Adjustment while you are not actually paying it"))
                if not line.writeoff_account_id:
                    raise UserError(_("You have to select Investor Adjustment Account before paying advance payment"))

    # For Changing the Lines Account for Commission and Investor Adjustment Option
    def _prepare_payment_moves(self):
        all_move_vals = []
        for payment in self:
            if payment.payment_type not in ['inbound', 'outbound'] or self.payment_category != 'multi_inv_payment':

                res = super(AccountPaymentExt, self)._prepare_payment_moves()
                line_ids = False
                try:
                    line_ids = res[0].get('line_ids')
                    if payment.discount_amount:
                        line_ids.append((0, 0, {
                            'name': 'Discount Allowed',
                            # 'currency_id': payment.currency_id,
                            'debit': payment.discount_amount or 0.0,
                            'credit': 0.0,
                            'date_maturity': payment.payment_date,
                            # 'partner_id': payment.partner_id.commercial_partner_id.id,
                            'account_id': self.env.company.discount_allowed_account_id.id,
                            'payment_id': payment.id,
                            'is_advance_payment_account': True if payment.is_advance_payment and payment.destination_account_id == payment.advance_payment_account_id else False
                        }))
                        line_ids[0][2]['credit'] = line_ids[0][2]['credit'] + payment.discount_amount
                except:
                    pass

                if line_ids:
                    iterate = 0
                    for aml in res[0].get('line_ids'):
                        if self.is_advance_payment and self.destination_account_id == self.advance_payment_account_id:
                            res[0].get('line_ids')[iterate][2]['is_advance_payment_account'] = True
                        else:
                            res[0].get('line_ids')[iterate][2]['is_advance_payment_account'] = False
                        iterate = iterate + 1
                return res
            company_currency = payment.company_id.currency_id
            move_names = payment.move_name.split(
                payment._get_move_name_transfer_separator()) if payment.move_name else None
            move_vals = {
                'date': payment.payment_date,
                'ref': payment.communication,
                'journal_id': payment.journal_id.id,
                'currency_id': payment.journal_id.currency_id.id or payment.company_id.currency_id.id,
                'partner_id': payment.partner_id.id,
                'line_ids': []
            }
            for invoice in payment.multi_invoice_ids:

                # Compute amounts.
                write_off_amount = invoice.payment_difference_handling in (
                    'reconcile', 'advance_payment', 'investor_adjustment', 'commission_adjustment') and -invoice.payment_difference or 0.0
                if payment.payment_type in ('outbound', 'transfer'):
                    counterpart_amount = invoice.payment_amount if invoice.payment_amount >= 0 else invoice.payment_amount * -1

                    liquidity_line_account = payment.journal_id.default_debit_account_id
                else:
                    counterpart_amount = -(
                        invoice.payment_amount if invoice.payment_amount >= 0 else invoice.payment_amount * -1)
                    liquidity_line_account = payment.journal_id.default_credit_account_id
                    if invoice.payment_difference_handling == 'investor_adjustment':
                        liquidity_line_account = self.env.company.advance_payment_account_id
                    if invoice.payment_difference_handling == 'commission_adjustment':
                        if payment.payment_nature == 'on_account':
                            liquidity_line_account = payment.journal_id.default_credit_account_id
                        # else:
                        #     liquidity_line_account = self.env.company.commission_adjustment_account_id

                # Manage currency.
                if payment.currency_id == company_currency:
                    # Single-currency.
                    balance = counterpart_amount
                    write_off_balance = write_off_amount
                    counterpart_amount = write_off_amount = 0.0
                    currency_id = False
                else:
                    # Multi-currencies.
                    balance = payment.currency_id._convert(counterpart_amount, company_currency, payment.company_id,
                                                           payment.payment_date)
                    write_off_balance = payment.currency_id._convert(write_off_amount, company_currency,
                                                                     payment.company_id, payment.payment_date)
                    currency_id = payment.currency_id.id

                # Manage custom currency on journal for liquidity line.
                if payment.journal_id.currency_id and payment.currency_id != payment.journal_id.currency_id:
                    # Custom currency on journal.
                    if payment.journal_id.currency_id == company_currency:
                        # Single-currency
                        liquidity_line_currency_id = False
                    else:
                        liquidity_line_currency_id = payment.journal_id.currency_id.id
                    liquidity_amount = company_currency._convert(
                        balance, payment.journal_id.currency_id, payment.company_id, payment.payment_date)
                else:
                    # Use the payment currency.
                    liquidity_line_currency_id = currency_id
                    liquidity_amount = counterpart_amount

                # Compute 'name' to be used in receivable/payable line.
                rec_pay_line_name = ''

                if payment.partner_type == 'customer':
                    if payment.payment_type == 'inbound':
                        rec_pay_line_name += _("Customer Payment")
                    elif payment.payment_type == 'outbound':
                        rec_pay_line_name += _("Customer Credit Note")
                elif payment.partner_type == 'supplier':
                    if payment.payment_type == 'inbound':
                        rec_pay_line_name += _("Vendor Credit Note")
                    elif payment.payment_type == 'outbound':
                        rec_pay_line_name += _("Vendor Payment")
                if payment.multi_invoice_ids:
                    rec_pay_line_name += ': %s' % invoice.invoice_id.name

                # Compute 'name' to be used in liquidity line.
                liquidity_line_name = payment.name

                # if payment.payment_type == 'outbound':
                #     write_off_balance = write_off_balance * -1

                # ==== 'inbound' / 'outbound' ====
                move_vals['line_ids'].append(
                    # Receivable / Payable / Transfer line.
                    (0, 0, {
                        'reconcile_invoice_id': invoice.invoice_id.id,
                        'name': rec_pay_line_name,
                        'amount_currency': counterpart_amount + write_off_amount if currency_id else 0.0,
                        'currency_id': currency_id,
                        'debit': balance + write_off_balance - invoice.discount_amount > 0.0 and balance + write_off_balance - invoice.discount_amount or 0.0,
                        'credit': balance + write_off_balance - invoice.discount_amount < 0.0 and -balance - write_off_balance + invoice.discount_amount or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': payment.destination_account_id.id,
                        'payment_id': payment.id,
                        'is_advance_payment_account': True if payment.is_advance_payment and payment.destination_account_id == payment.advance_payment_account_id else False
                    })
                )
                move_vals['line_ids'].append(
                    # Liquidity line.
                    (0, 0, {
                        'reconcile_invoice_id': invoice.invoice_id.id,
                        'name': liquidity_line_name,
                        'amount_currency': -liquidity_amount if liquidity_line_currency_id else 0.0,
                        'currency_id': liquidity_line_currency_id,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': liquidity_line_account.id,
                        'payment_id': payment.id,
                        'is_advance_payment_account': True if payment.is_advance_payment and payment.destination_account_id == payment.advance_payment_account_id else False
                    })
                )
                if invoice.discount_amount:
                    name = ''
                    # if invoice.payment_difference_handling == 'reconcile':
                    if invoice.payment_difference_handling in ('commission_adjustment', 'reconcile'):
                        name = 'Write-Off'
                    elif invoice.payment_difference_handling == 'advance_payment':
                        name = 'Advance-Payment'

                    # Write-off line with discount amount.
                    move_vals['line_ids'].append((0, 0, {
                        'reconcile_invoice_id': invoice.invoice_id.id,
                        'name': '%s/%s' % (name, invoice.invoice_id.name),
                        'amount_currency': -write_off_amount,
                        'currency_id': currency_id,
                        'debit': invoice.discount_amount if payment.payment_type == 'inbound' else 0.0,
                        'credit': invoice.discount_amount * -1 if payment.payment_type == 'outbound' else 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': self.env.company.discount_allowed_account_id.id if payment.payment_type == 'inbound' else self.env.company.discount_earned_account_id.id,
                        'payment_id': payment.id,
                        'is_advance_payment_account': True if payment.is_advance_payment and payment.destination_account_id == payment.advance_payment_account_id else False
                    }))

                if write_off_balance:
                    name = ''
                    # if invoice.payment_difference_handling == 'reconcile':
                    if invoice.payment_difference_handling in ('commission_adjustment', 'reconcile'):
                        name = 'Write-Off'
                    elif invoice.payment_difference_handling == 'advance_payment':
                        name = 'Advance-Payment'
                    elif invoice.payment_difference_handling == 'investor_adjustment':
                        name = 'Investor-Adjustment'

                    # Write-off line.
                    move_vals['line_ids'].append((0, 0, {
                        'reconcile_invoice_id': invoice.invoice_id.id,
                        'name': '%s/%s' % (name, invoice.invoice_id.name),
                        'amount_currency': -write_off_amount,
                        'currency_id': currency_id,
                        'debit': write_off_balance < 0.0 and -write_off_balance or 0.0,
                        'credit': write_off_balance > 0.0 and write_off_balance or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': payment.partner_id.commercial_partner_id.id,
                        'account_id': invoice.writeoff_account_id.id,
                        'payment_id': payment.id,
                        'is_advance_payment_account': True if payment.is_advance_payment and payment.destination_account_id == payment.advance_payment_account_id else False
                    }))

                if move_names:
                    move_vals['name'] = move_names[0]

            all_move_vals.append(move_vals)
        return all_move_vals

    def update_open_files_payments(self):
        # pass
        for rec in self:
            if rec.company_id.id != 1:
                if rec.investment_id and rec.multi_invoice_ids and rec.multi_invoice_ids.filtered(lambda l: l.invoice_id.property_invoice_type == 'investment'):
                    booking_balance = rec.amount
                    # if rec.investment_id.reservation_type == 'bulk':
                    all_installments = self.env['installment.plan'].search(
                        [('investor_file_id.investment_id', '=', rec.investment_id.id), ('payment_status', 'in', ['not_paid', 'in_payment']),
                         ('installment_type', '=', 'down'), ('residual', '>', 0)])
                    adjustment_amount = rec.amount
                    if all_installments:
                        if adjustment_amount > 0:
                            for lines in all_installments:
                                diff = adjustment_amount - lines.residual
                                if adjustment_amount > 0:
                                    if not diff < 0:
                                        lines.amount_paid += lines.residual
                                        adjustment_amount -= lines.residual
                                    else:
                                        lines.amount_paid += adjustment_amount
                                        adjustment_amount = 0
                                    lines.residual = lines.amount - lines.amount_paid
                                    if lines.residual == 0:
                                        lines.payment_status = 'paid'
                                    else:
                                        if lines.amount_paid > 0:
                                            lines.payment_status = 'in_payment'
                                lines.net_payment = lines.amount_paid - lines.dealer_share
                        # amount_5_marla = rec.amount * (rec.investment_id.investment_line_ids.filtered(lambda l: l.unit_category_type_id.name == '5 Marla').no_of_units / rec.investment_id.no_of_units)
                        #
                        # amount_10_marla = rec.amount * (rec.investment_id.investment_line_ids.filtered(lambda l: l.unit_category_type_id.name == '10 Marla').no_of_units / rec.investment_id.no_of_units)
                        #
                        # amount_1_kanal = rec.amount * (rec.investment_id.investment_line_ids.filtered(lambda l: l.unit_category_type_id.name == '1 Kanal').no_of_units / rec.investment_id.no_of_units)
                        # installments_5_marla = self.env['installment.plan'].search(
                        #     [('investor_file_id.investment_id', '=', rec.investment_id.id), ('payment_status', 'in', ['not_paid', 'in_payment']),('installment_type', '=', 'down'),('residual', '>',
                        #                                                                                                                                                             0),
                        #      ('investor_file_id.unit_category_type_id.name', '=', '5 Marla')])
                        # if installments_5_marla:
                        #     if amount_5_marla > 0:
                        #         for lines in installments_5_marla:
                        #             diff = amount_5_marla - lines.residual
                        #             if amount_5_marla > 0:
                        #                 if not diff < 0:
                        #                     lines.amount_paid += lines.residual
                        #                     amount_5_marla -= lines.residual
                        #                 else:
                        #                     lines.amount_paid += amount_5_marla
                        #                     amount_5_marla = 0
                        #                 lines.residual = lines.amount - lines.amount_paid
                        #                 if lines.residual == 0:
                        #                     lines.payment_status = 'paid'
                        #                 else:
                        #                     if lines.amount_paid > 0:
                        #                         lines.payment_status = 'in_payment'
                        #             lines.net_payment = lines.amount_paid - lines.dealer_share
                        # installments_10_marla = self.env['installment.plan'].search([('investor_file_id.investment_id', '=', rec.investment_id.id),
                        #                                                              ('payment_status', 'in',['not_paid', 'in_payment']),
                        #                                                              ('installment_type', '=', 'down'), ('residual', '>', 0),
                        #                                                              ('investor_file_id.unit_category_type_id.name', '=', '10 Marla')])
                        # if installments_10_marla:
                        #     if amount_10_marla > 0:
                        #         for lines in installments_10_marla:
                        #             diff = amount_10_marla - lines.residual
                        #             if amount_10_marla > 0:
                        #                 if not diff < 0:
                        #                     lines.amount_paid += lines.residual
                        #                     amount_10_marla -= lines.residual
                        #                 else:
                        #                     lines.amount_paid += amount_10_marla
                        #                     amount_10_marla = 0
                        #                 lines.residual = lines.amount - lines.amount_paid
                        #                 if lines.residual == 0:
                        #                     lines.payment_status = 'paid'
                        #                 else:
                        #                     if lines.amount_paid > 0:
                        #                         lines.payment_status = 'in_payment'
                        #             lines.net_payment = lines.amount_paid - lines.dealer_share
                        # installments_1_kanal = self.env['installment.plan'].search(
                        #     [('investor_file_id.investment_id', '=', rec.investment_id.id), ('payment_status', 'in',['not_paid','in_payment']),
                        #      ('installment_type', '=', 'down'), ('residual', '>', 0), ('investor_file_id.unit_category_type_id.name', '=', '1 Kanal')])
                        # if installments_1_kanal:
                        #     if amount_1_kanal > 0:
                        #         for lines in installments_1_kanal:
                        #             diff = amount_1_kanal - lines.residual
                        #             if amount_1_kanal > 0:
                        #                 if not diff < 0:
                        #                     lines.amount_paid += lines.residual
                        #                     amount_1_kanal -= lines.residual
                        #                 else:
                        #                     lines.amount_paid += amount_1_kanal
                        #                     amount_1_kanal = 0
                        #                 lines.residual = lines.amount - lines.amount_paid
                        #                 if lines.residual == 0:
                        #                     lines.payment_status = 'paid'
                        #                 else:
                        #                     if lines.amount_paid > 0:
                        #                         lines.payment_status = 'in_payment'
                        #             lines.net_payment = lines.amount_paid - lines.dealer_share

    def check_for_on_account_entry(self):
        # pass
        if self.payment_nature == 'on_account':
            if self.advance_payment_id and self.advance_payment_id.amount_residual < self.amount:
                raise ValidationError('Advance Balance is less than Adjustment Amount. Please select other Advance Payment')
            description = 'Confirmation Adjustment of File - ' + self.file_id.name
            invoice = self.env['account.move'].search([('ref', '=', description), ('move_type', '=', 'out_invoice'), ('property_invoice_type', '=', 'others'),
                                                       ('company_id', '=', self.env.company.id),
                                                       ('partner_id', '=', self.file_id.investor_id.partner_id.id), ('state', '!=', 'cancelled')])
            if not invoice:
                invoice_line = [{
                    'name': description,
                    'quantity': 1,
                    'price_unit': self.amount,
                    'account_id': self.env.company.confirmation_adjustment_account_id.id,
                }]
                new_invoice = self.create_invoice(invoice_line, description)
                adv_pay = self.advance_payment_id
                self.apply_advance_payment_to_invoice(adv_pay, new_invoice)
            else:
                if len(invoice) == 1:
                    if invoice and invoice.amount_residual > 0 and invoice.amount_residual >= self.amount:
                        adv_pay = self.advance_payment_id
                        self.apply_advance_payment_to_invoice(adv_pay, invoice)
                    else:
                        invoice_line = [{
                            'name': description,
                            'quantity': 1,
                            'price_unit': self.amount,
                            'account_id': self.env.company.confirmation_adjustment_account_id.id,
                        }]
                        new_invoice = self.create_invoice(invoice_line, description)
                        adv_pay = self.advance_payment_id
                        self.apply_advance_payment_to_invoice(adv_pay, new_invoice)
                else:
                    invoice_line = [{
                        'name': description,
                        'quantity': 1,
                        'price_unit': self.amount,
                        'account_id': self.env.company.confirmation_adjustment_account_id.id,
                    }]
                    new_invoice = self.create_invoice(invoice_line, description)
                    adv_pay = self.advance_payment_id
                    self.apply_advance_payment_to_invoice(adv_pay, new_invoice)
        else:
            pass

    def apply_advance_payment_to_invoice(self, adv_pay, invoice):
        payment_amount = adv_pay.amount_residual
        multi_invoice_ids = []
        inv = self.env['multi.invoice.payment'].create(
            {'invoice_id': invoice.id,
             'payment_id': False,
             'payment_due': invoice.amount_residual,
             'payment_amount': invoice.amount_residual if payment_amount >= invoice.amount_residual else payment_amount})
        multi_invoice_ids.append(inv.id)
        payment_amount = payment_amount - invoice.amount_residual if payment_amount >= invoice.amount_residual else 0
        invoice.advance_payment_ids = [(4, adv_pay.id)]

        multi_invoices = self.env['multi.invoice.payment'].browse(multi_invoice_ids)

        # Applying Advance Payment against invoices
        invoices = multi_invoices.mapped('invoice_id')
        print("Applying Advance Payment against invoices")
        for record in invoices:
            partner_id = self.env['res.partner']._find_accounting_partner(record.partner_id).id
            invoice_move_lines = invoices.mapped('line_ids')
            invoice_move_lines = invoice_move_lines.filtered(
                lambda r: not r.reconciled and r.account_id.internal_type in
                          ('payable', 'receivable'))

            advance_payment_accounts = self.env['account.account']
            payment_move_line = {}
            for payment in adv_pay:
                payment.amount_to_adjust = 0
                payment_account = payment.advance_payment_account_id
                advance_payment_accounts |= payment_account
                if payment.id not in payment_move_line:
                    payment_move_line[payment.id] = self.env['account.move.line']
                payment_move_line[payment.id] |= payment.move_line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id == payment_account)
                payment.write(
                    {'invoice_ids': [(4, x.id, None) for x in invoices]})

            advance_payment_move_lines = []
            advance_payment_residual = 0
            if adv_pay.amount_residual >= record.amount_residual:
                advance_payment_residual = record.amount_residual
            elif adv_pay.amount_residual <= record.amount_residual:
                advance_payment_residual = adv_pay.amount_residual
            counterpart_balance = currency_exchange_diff = 0.0
            currency_company = adv_pay.company_id.currency_id
            payment_move_lines = self.env['account.move.line']
            payment_id = False
            for lines in payment_move_line.values():
                payment_move_lines |= lines
                for line in lines:
                    payment_id = line.payment_id
                    balance = abs(line.balance)
                    currency = line.currency_id or currency_company
                    currency_invoice = record.currency_id
                    payment_date = line.payment_id.payment_date

                    if currency_company != currency_invoice:
                        advance_payment_residual = currency_invoice.with_context(date=payment_date) \
                            .compute(advance_payment_residual,
                                     currency_company)

                    balance_now = balance_used = min(
                        balance, advance_payment_residual)
                    if currency != currency_company and balance:
                        if line.amount_currency:
                            amount_currency = abs(
                                line.amount_currency * (balance_used / balance))
                        else:
                            amount_currency = balance_used
                        balance_now = currency.compute(
                            amount_currency, currency_company)

                    if currency != currency_invoice:
                        balance_now = currency.with_context(date=payment_date).compute(balance_now,
                                                                                       currency_invoice)
                        balance_now = currency_invoice.compute(
                            balance_now, currency)

                    counterpart_balance += balance_now
                    currency_exchange_diff += balance_now - balance_used

                    if adv_pay.partner_type == 'customer':
                        credit = 0.0
                        debit = balance_used
                        advance_payment_residual -= debit
                    else:
                        debit = 0.0
                        credit = balance_used
                        advance_payment_residual -= credit

                    currency_company = currency_company.with_context(
                        date=payment_date)
                    if currency_company != currency_invoice:
                        advance_payment_residual = currency_company.compute(advance_payment_residual,
                                                                            currency_invoice)

                    if credit or debit:
                        advance_payment_move_lines.append((0, 0, {
                            'name': 'Advance Payment: %s' % ', '.join(
                                lines.mapped('move_id').mapped('name')),
                            'account_id': line.account_id.id,
                            'partner_id': partner_id,
                            'debit': debit,
                            'credit': credit,
                            'payment_id': payment_id.id,
                            'is_advance_payment_account': True,
                        }))

            if counterpart_balance:
                if adv_pay.partner_type == 'customer':
                    account_id = adv_pay.partner_id.property_account_receivable_id
                elif adv_pay.partner_type == 'supplier':
                    account_id = adv_pay.partner_id.property_account_payable_id
                else:
                    raise ValidationError(_("Partner type is neither customer nor supplier"))
                advance_payment_move_lines.append((0, 0, {
                    'name': 'Advance Payment: %s' % ', '.join(invoices.mapped('name')),
                    'account_id': account_id.id,
                    'partner_id': partner_id,
                    'debit': adv_pay.partner_type == 'supplier' and counterpart_balance or 0.0,
                    'credit': adv_pay.partner_type == 'customer' and counterpart_balance or 0.0,
                    'payment_id': payment_id.id,
                    'is_advance_payment_account': False,
                }))

            if currency_exchange_diff:
                currency_exchange_journal = adv_pay.company_id.currency_exchange_journal_id
                if currency_exchange_diff < 0:
                    if adv_pay.partner_type == 'supplier':
                        currency_exchange_account = currency_exchange_journal.default_debit_account_id
                        credit = 0.0
                        debit = abs(currency_exchange_diff)
                    else:
                        currency_exchange_account = currency_exchange_journal.default_credit_account_id
                        credit = abs(currency_exchange_diff)
                        debit = 0.0
                else:
                    if adv_pay.partner_type == 'supplier':
                        currency_exchange_account = currency_exchange_journal.default_credit_account_id
                        credit = currency_exchange_diff
                        debit = 0.0
                    else:
                        currency_exchange_account = currency_exchange_journal.default_debit_account_id
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
                move = self.env['account.move'].with_context(skip_validation=True).create({
                    'date': record.date,
                    'company_id': adv_pay.company_id.id,
                    'journal_id': adv_pay.journal_id.id,
                    'line_ids': advance_payment_move_lines,
                })
                move.action_post()

                invoice_payment_move_lines = move.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))
                advance_payment_move_lines = move.line_ids.filtered(
                    lambda r: not r.reconciled and r.account_id in advance_payment_accounts)

                (invoice_payment_move_lines + invoice_move_lines).reconcile()
                (advance_payment_move_lines + payment_move_lines).reconcile()

    def create_invoice(self, invoice_line, description):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'ref': description,
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'partner_id': self.file_id.investor_id.partner_id.id,
            'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
            'property_invoice_type': 'others',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_line
        })
        invoice.action_post()
        return invoice

    def link_payment_to_file(self):
        for line in self.multi_invoice_ids:
            if line.invoice_id and line.invoice_id.file_ids and line.payment_amount > 0 and line.invoice_id.property_invoice_type != 'maintenance_charges':
                installment_line = self.env['installment.plan'].search([('invoice_id', '=', line.invoice_id.id)], limit=1)
                if installment_line:
                    installment_line.payment_journal_id = self.journal_id.id
                if line.invoice_id.property_invoice_type in ('initial_payment', 'confirmation_amount', 'installment', 'balloon', 'balloting_amount', 'possession_amount', 'final'):
                    if line.id not in line.invoice_id.file_ids.installment_payments.mapped('multi_invoice_line_id.id'):
                        file_payment_line = self.env['file.installment.payment'].sudo().create({
                            'multi_invoice_line_id': line.id,
                            'name': ','.join(line.invoice_id.invoice_line_ids.mapped('name')),
                            'invoice_id': line.invoice_id.id,
                            'property_invoice_type': line.invoice_id.property_invoice_type,
                            'invoice_date': line.invoice_id.invoice_date,
                            'invoice_amount': line.payment_due,
                            'payment_id': line.payment_id.id,
                            'payment_amount': line.payment_amount,
                            'invoice_residual': line.payment_difference,
                            'file_id': line.invoice_id.file_ids.id
                        })
                else:
                    if line.id not in line.invoice_id.file_ids.additional_payments.mapped('multi_invoice_line_id.id'):
                        file_payment_line = self.env['file.additional.payment'].sudo().create({
                            'multi_invoice_line_id': line.id,
                            'name': ','.join(line.invoice_id.invoice_line_ids.mapped('name')) if line.invoice_id.property_invoice_type != 'late_payment'
                            else line.invoice_id.narration,
                            'invoice_id': line.invoice_id.id,
                            'property_invoice_type': line.invoice_id.property_invoice_type,
                            'invoice_date': line.invoice_id.invoice_date,
                            'invoice_amount': line.payment_due,
                            'payment_id': line.payment_id.id,
                            'payment_amount': line.payment_amount,
                            'invoice_residual': line.payment_difference,
                            'file_id': line.invoice_id.file_ids.id
                        })

    def action_draft(self):
        res = super(AccountPaymentExt, self).action_draft()
        for rec in self:
            if rec.payment_nature == 'on_account':
                description = 'Confirmation Adjustment of File - ' + rec.file_id.name
                invoices = self.env['account.move'].search(
                    [('ref', '=', description), ('move_type', '=', 'out_invoice'), ('property_invoice_type', '=', 'others'),
                     ('company_id', '=', self.env.company.id),
                     ('partner_id', '=', rec.file_id.investor_id.partner_id.id), ('state', 'not in', ['draft', 'cancel'])])
                if invoices:
                    for invoice in invoices:
                        # Unapplying Advance
                        label = 'Advance Payment: ' + str(invoice.name)
                        move_line = self.env['account.move.line'].search(
                            [('name', '=', label), ('move_id', '!=', invoice.id), ('full_reconcile_id', '!=', False),
                             ('payment_id', '=', rec.advance_payment_id.id)])
                        if move_line:
                            move_id = move_line.mapped('move_id')[0]
                            reverse_move = self.env['account.move.reversal'].with_context(
                                {'active_ids': [move_id.id], 'active_id': move_id.id,
                                 'active_model': 'account.move'}).create({
                                'refund_method': 'cancel',
                                'reason': 'Confirmation Payment Cancellation'})
                            reverse_move.reverse_moves()
                            reversed_move_id = self.env['account.move'].search([('reversed_entry_id', '=', move_id.id)])
                            if reversed_move_id:
                                for line in reversed_move_id.line_ids:
                                    line.payment_id = rec.advance_payment_id.id
                        invoice.button_draft()
                        invoice.button_cancel()
        return res

    def open_installment_wizard(self):
        date = fields.Date.today()
        if self.invoice_creation_quantity > 0:
            date = date + relativedelta(months=+self.invoice_creation_quantity)
        return {
            'res_model': 'installment.invoice.wizard',
            'type': 'ir.actions.act_window',
            'context': {
                'default_file_id': self.file_id.id,
                'default_society_id': self.file_id.society_id.id,
                'default_phase_id': self.file_id.phase_id.id,
                'default_payment_id': self.id,
                'default_from_payment': True,
                'default_from_file': True,
                'default_till_date': date
            },
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': self.env.ref("real_estate.installment_invoice_wizard_form").id,
            'target': 'new'
        }
