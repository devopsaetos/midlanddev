# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from lxml import etree as ET
import secrets


class AccountPaymentExt(models.Model):
	_inherit = 'account.payment'

	allow_bank_finance = fields.Boolean(related='company_id.allow_bank_finance', index=True)
	finance_by = fields.Selection([
		('bank', 'Bank'),
		('self', 'Self')
	])
	advance_against = fields.Selection([
		('file','File'),
		('investment','Investment'),
		('other','Other'),
	])
	file_id = fields.Many2one('file')
	investment_id = fields.Many2one('investment')
	payment_amount_cal = fields.Float()
	secret_token = fields.Char(string="Secret Token", required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)

	# @api.model
	def assign_secret_tokens(self):
		# Fetch records that have the token as 'New' or empty
		records_with_default_token = self.search([('secret_token', '=', 'New')])
		for record in records_with_default_token:
			# Assign a new unique token if the token is still 'New'
			record.secret_token = secrets.token_hex(10)

	def action_register_payment(self):
		res = super(AccountPaymentExt, self).action_register_payment()
		active_ids = self.env.context.get('active_ids')
		if active_ids:
			invoice = self.env['account.move'].browse(active_ids)
			res['context']['default_file_id'] = invoice.file_ids.id
		return res

	@api.onchange('file_id','investment_id')
	def onchange_advance_against(self):
		for rec in self:
			rec.partner_id = False
			if rec.file_id:
				rec.partner_id = rec.file_id.membership_id.partner_id.id
			if rec.investment_id:
				rec.partner_id = rec.investment_id.partner_id.partner_id.id

	def multi_line_domain(self):
		res = super(AccountPaymentExt, self).multi_line_domain()
		if self.file_id and self.partner_id:
			return self.multi_invoice_ids.search([
				('partner_id', '=', self.partner_id.id),
				('invoice_id.file_ids', '=', self.file_id.id),
				('state', '=', 'posted'),
				('active', '=', True),
				('payment_id', '=', False),
				('payment_state', '!=', 'paid'),
				('type', 'in',
				 ['out_invoice', 'in_refund'] if self.payment_type == 'inbound' else ['in_invoice', 'out_refund'])
			])
		elif self.investment_id and self.partner_id:
			return self.multi_invoice_ids.search([
				('partner_id', '=', self.partner_id.id),
				('invoice_id.file_ids', '=', self.investment_id.id),
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
		if self.file_id:
			res['domain']['multi_invoice_ids'].append((['invoice_id.file_ids','=',self.file_id.id]))
		if self.investment_id:
			res['domain']['multi_invoice_ids'].append((['invoice_id.investment_id','=',self.investment_id.id]))

		return res

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('secret_token', _('New')) == _('New'):
				vals['secret_token'] = secrets.token_hex(10)
		res = super(AccountPaymentExt, self).create(vals_list)
		for rec in res:
			if rec.name and 'FILE' in rec.name:
				rec.name = False

		return res

	def post(self):
		res = super(AccountPaymentExt, self).post()
		for rec in self:
			if not rec.base_payment_id and rec.payment_category and rec.file_id and rec.is_advance_payment:
				self.advance_amount_adjustment_files(rec)
			if rec.file_id:
				adv_pay = rec.search([('is_advance_payment', '=', True), ('payment_category', '=', 'advance_payment'), ('base_payment_id', '=', rec.id)])
				if adv_pay:
					for adv_payment in adv_pay:
						adv_payment.write({
							'advance_against': 'file' if rec.file_id else 'other',
							'file_id': rec.file_id.id})
						self.advance_amount_adjustment_files(adv_payment)
		if self.multi_invoice_ids:
			for rec in self.multi_invoice_ids:
				if rec.invoice_id.investment_id:
					investment_history = rec.invoice_id.investment_id.investment_history_ids[0]
					investment_history.payment_received = investment_history.payment_received + rec.payment_amount
					investment_history.payment_date = self.date
					if rec.invoice_id.investment_id.options == 'full':
						rec.invoice_id.investment_id.amount_paid = rec.invoice_id.investment_id.amount_paid + rec.payment_amount
				if rec.invoice_id.token_id and rec.invoice_id.payment_state == 'paid':
					rec.invoice_id.token_id.token_paid = True
					rec.invoice_id.token_id.state = 'adjusted' if rec.invoice_id.token_id.create_open_file == True else 'paid'
					rec.invoice_id.token_id.open_file_amount_received = True
				if rec.invoice_id.file_ids.payment_type == 'installments':
					rec.invoice_id.file_ids.payment_states = 'open'
				if rec.invoice_id.file_ids.payment_type == 'lump_sum':
					rec.invoice_id.file_ids.overall_status = 'close'
				if rec.invoice_id.transfer_application_id and rec.invoice_id.invoice_line_ids.product_id == self.env.ref('real_estate.file_transfer').product_id:
					rec.invoice_id.transfer_application_id.payment_received = True
				if rec.invoice_id.unit_swap_request_id and rec.invoice_id.amount_residual == 0.00:
					rec.invoice_id.unit_swap_request_id.invoice_paid = True

		return res

	def advance_amount_adjustment_files(self, adv_pay):
		if adv_pay.file_id:
			payment_amount = adv_pay.amount_residual
			if adv_pay.file_id.installment_plan_ids \
					and adv_pay.file_id.create_manually == False \
					and adv_pay.file_id.state not in ['cancel', 'refund'] \
					and adv_pay.file_id.society_id.company_id == self.env.user.company_id \
					and adv_pay:
				plans = adv_pay.file_id.installment_plan_ids.filtered(lambda l: l.payment_status != 'paid')
				multi_invoice_ids = []
				for installment in plans:

					if installment.state != 'paid' and not installment.invoice_created and payment_amount > 0:
						print("CREATING INVOICE AGAINST THIS %s FILE: " % (adv_pay.file_id))
						_re = self.env.ref('real_estate.installment_product')
						prod = [(0, 0, {
							'product_id': _re.product_id.id,
							'name': _re.name,
							'account_id': _re.product_id.property_account_income_id.id,
							'price_unit': installment.amount,
						})]

						invoice = self.env['account.move'].create({
							# 'file_ids': adv_pay.file_id.id,
							# 'invoice_payment_ref': adv_pay.file_id.name,
							'partner_id': adv_pay.file_id.membership_id.partner_id.id,
							'move_type': 'out_invoice',
							'journal_id': self.env.company.account_journal_id.id,
							'property_invoice_type': 'installment',
							'user_id': adv_pay.file_id.user_id.id,
							'date': installment.date,
							'invoice_date': installment.date,
							'invoice_payment_term_id': adv_pay.file_id.env.company.payment_terms_final_id.id,
							'invoice_line_ids': prod
						})
						invoice.file_ids = adv_pay.file_id.id
						invoice.action_post()
						installment.invoice_id = invoice.id
						installment.invoice_created = True
					if installment.state != 'paid' and installment.invoice_id and payment_amount > 0:
						inv = self.env['multi.invoice.payment'].create(
							{'invoice_id': installment.invoice_id.id, 'payment_id': False,
							 'payment_due': installment.invoice_id.amount_residual,
							 'payment_amount': installment.invoice_id.amount_residual if payment_amount >= installment.invoice_id.amount_residual else payment_amount})
						multi_invoice_ids.append(inv.id)
						payment_amount = payment_amount - installment.invoice_id.amount_residual if payment_amount >= installment.invoice_id.amount_residual else 0
						installment.invoice_id.advance_payment_ids = [(4, adv_pay.id)]

				multi_invoices = self.env['multi.invoice.payment'].browse(multi_invoice_ids)

				# Applying Advance Payment against invoices
				invoices = multi_invoices.mapped('invoice_id')
				print("Applying Advance Payment against invoices")
				for record in invoices:
					partner_id = self.env['res.partner']._find_accounting_partner(
						record.partner_id).id
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
							payment_move_line[payment.id] = self.env[
								'account.move.line']
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
							payment_date = line.payment_id.date

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
							raise ValidationError(_("Partner type is nither customer nor supplier"))
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
						name = adv_pay.journal_id.with_context(
							ir_sequence_date=record.date).sequence_id.next_by_id()
						move = self.env['account.move'].with_context(skip_validation=True).create({
							'name': name,
							'date': record.date,
							'company_id': adv_pay.company_id.id,
							'journal_id': adv_pay.journal_id.id,
							'line_ids': advance_payment_move_lines,
						})
						move.post()

						invoice_payment_move_lines = move.line_ids.filtered(
							lambda r: not r.reconciled and r.account_id.account_type in ('liability_payable', 'asset_receivable'))
						advance_payment_move_lines = move.line_ids.filtered(
							lambda r: not r.reconciled and r.account_id in
									  advance_payment_accounts)

						(invoice_payment_move_lines + invoice_move_lines).reconcile()
						(advance_payment_move_lines + payment_move_lines).reconcile()

	@api.model
	def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
		res = super(AccountPaymentExt, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
															 submenu=submenu)
		is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')

		if is_user:
			if view_type == 'form':
				doc = ET.XML(res['arch'])
				doc.set('edit', 'true')
				doc.set('create', 'true')
				res['arch'] = ET.tostring(doc)

			if view_type == 'tree':
				doc = ET.XML(res['arch'])
				doc.set('edit', 'true')
				doc.set('create', 'true')
				res['arch'] = ET.tostring(doc)
		else:
			if view_type == 'form':
				doc = ET.XML(res['arch'])
				doc.set('edit', 'false')
				doc.set('create', 'false')
				res['arch'] = ET.tostring(doc)

			if view_type == 'tree':
				doc = ET.XML(res['arch'])
				doc.set('edit', 'false')
				doc.set('create', 'false')
				res['arch'] = ET.tostring(doc)

		return res
