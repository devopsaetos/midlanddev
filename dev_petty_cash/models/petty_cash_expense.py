# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError
from datetime import date

class petty_cash_expense(models.Model):
    _name = 'petty.cash.expense'
    _description = 'Petty Cash expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    @api.model
    def _get_request_by(self):
        employee_id =self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
        return employee_id.id or False
    
    name = fields.Char('Name', default='/', tracking=1)
    employee_id = fields.Many2one('hr.employee', string='Employee', default=_get_request_by, tracking=2)
    petty_journal_id = fields.Many2one(
        'account.journal', string='From (Petty Cash Journal)', tracking=2,
        domain="[('is_petty_cash', '=', True), ('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]")
    # no longer used for posting: the expense entry is booked in the petty cash journal
    payment_journal_id = fields.Many2one(
        'account.journal', string='To (Payment Journal)',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]")
    date = fields.Date('Date', copy=False, default=fields.Datetime.now)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self:self.env.company.currency_id)
    user_id = fields.Many2one('res.users', string='User', default=lambda self:self.env.user)
    company_id = fields.Many2one('res.company', default=lambda self:self.env.company)
    state = fields.Selection(string='State', selection=[('draft', 'Draft'),
                                                        ('confirm', 'Confirm'),
                                                        ('payment', 'Process Payment'),  # legacy, no longer set
                                                        ('done', 'Done'),
                                                        ('cancel','Cancel')], default='draft', tracking=4)
    expense_lines = fields.One2many('petty.expense.lines','expense_id', string='Expense Lines')
    payment_ids = fields.Many2many('account.payment', string='Payments', copy=False)
    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False, readonly=True,
                              help='Dr expense accounts / Cr petty cash, posted in the petty cash journal.')
    balance = fields.Monetary('Balance', compute='_get_balance')
    expense_amount = fields.Monetary('Expense Amount', compute='_get_expense_amount', store=True, tracking=3)
    request_ids = fields.Many2many('petty.cash.request', string='Requests')
    remaining_balance = fields.Monetary('Remaining Amount', compute='_get_remaining_balance')
    note = fields.Text('Notes')
    payment_count = fields.Integer('Payment Count', compute='_count_payment')
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method',
                                             domain="[('id', 'in', available_payment_method_line_ids)]",
                                             help="Manual: Pay or Get paid by any method outside of Odoo.\n"
                                                  "Payment Providers: Each payment provider has its own Payment Method. Request a transaction on/to a card thanks to a payment token saved by the partner when buying or subscribing online.\n"
                                                  "Check: Pay bills by check and print it from Odoo.\n"
                                                  "Batch Deposit: Collect several customer checks at once generating and submitting a batch deposit to your bank. Module account_batch_payment is necessary.\n"
                                                  "SEPA Credit Transfer: Pay in the SEPA zone by submitting a SEPA Credit Transfer file to your bank. Module account_sepa is necessary.\n"
                                                  "SEPA Direct Debit: Get paid in the SEPA zone thanks to a mandate your partner will have granted to you. Module account_sepa is necessary.\n")
    available_payment_method_line_ids = fields.Many2many('account.payment.method.line',
                                                         compute='_compute_payment_method_line_fields')
    partner_id = fields.Many2one('res.partner', string='Vendor')
    invoice_ids = fields.One2many('account.move', 'pc_expense_id', string='Bills')
    invoice_count = fields.Integer('Invoice Count', compute='_get_invoice_count')

    def _get_invoice_count(self):
        for order in self:
            count = len(self.invoice_ids)
            order.invoice_count = count

    def get_account(self, product_id):
        account_id = False
        if product_id:
            account_id = product_id.property_account_expense_id or False
        if not account_id:
            account_id = product_id.categ_id and product_id.categ_id.property_account_expense_categ_id or False
        return account_id

    def create_vendor_bill(self):
        invoice_lines = []
        for line_id in self.expense_lines:
            account_id = self.get_account(line_id.product_id)
            if not account_id:
                raise ValidationError(_('''There is no expense account defined for the product '%s' ''') % (
                    line_id.product_id.name))
            line_vals = {'product_id': line_id.product_id.id,
                         'name': line_id.name or line_id.product_id.name or '',
                         'account_id': account_id.id,
                         'price_unit': line_id.amount,
                         'quantity': 1,
                         'product_uom_id': line_id.product_id.uom_id and line_id.product_id.uom_id.id or False,
                         
                         }
            invoice_lines.append((0, 0, line_vals))
        vals = {'move_type': 'in_invoice',
                'partner_id': self.partner_id and self.partner_id.id or False,
                'pc_expense_id': self.id,
                'invoice_date': date.today(),
                'currency_id': self.currency_id.id,
                'invoice_line_ids': invoice_lines}
        self.env['account.move'].create(vals)

    def action_view_invoice(self):
        invoice_ids = self.invoice_ids
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids.ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoice_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.depends('payment_journal_id', 'currency_id')
    def _compute_payment_method_line_fields(self):
        for pay in self:
            pay.available_payment_method_line_ids = pay.payment_journal_id._get_available_payment_method_lines(
                'outbound')
    
    def action_view_payment(self):
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_account_payments")
        action['context']={}
        action['domain'] = [('id','in',self.payment_ids.ids)]
        return action
    
    @api.depends('payment_ids')
    def _count_payment(self):
        for expense in self:
            expense.payment_count = len(expense.payment_ids)
            
    @api.depends('expense_lines.amount')
    def _get_expense_amount(self):
        for expense in self:
            expense.expense_amount = sum(expense.expense_lines.mapped('amount'))

    @api.depends('balance', 'expense_amount')
    def _get_remaining_balance(self):
        for expense in self:
            expense.remaining_balance = expense.balance - expense.expense_amount
            
                    
    
    @api.depends('employee_id', 'petty_journal_id', 'currency_id')
    def _get_balance(self):
        for expense in self:
            # Calculate total approved funds (all users' documents: the balance belongs to the employee)
            request_ids = self.env['petty.cash.request'].sudo().search([
                ('request_by', '=', expense.employee_id.id),
                ('petty_journal_id', '=', expense.petty_journal_id.id),
                ('state', '=', 'approve')
            ])
            total_funds = 0.0
            for req in request_ids:
                if req.currency_id == expense.currency_id:
                    total_funds += req.request_amount
                else:
                    total_funds += req.currency_id._convert(
                        req.request_amount, expense.currency_id, 
                        expense.company_id, req.date
                    )
            
            # Calculate total spent (confirmed, legacy "payment" or done)
            # Exclude current record if it's already in those states to avoid double counting
            spent_expenses = self.env['petty.cash.expense'].sudo().search([
                ('employee_id', '=', expense.employee_id.id),
                ('petty_journal_id', '=', expense.petty_journal_id.id),
                ('state', 'in', ['confirm', 'payment', 'done']),
                ('id', '!=', expense._origin.id if hasattr(expense, '_origin') else expense.id)
            ])
            total_spent = 0.0
            for exp in spent_expenses:
                if exp.currency_id == expense.currency_id:
                    total_spent += exp.expense_amount
                else:
                    total_spent += exp.currency_id._convert(
                        exp.expense_amount, expense.currency_id, 
                        expense.company_id, exp.date
                    )
            
            expense.balance = total_funds - total_spent
        
    
    def _prepare_move_vals(self):
        """Dr each line's expense account (with its analytic account) / Cr petty cash."""
        self.ensure_one()
        petty_account = self.petty_journal_id._petty_cash_account()
        partner = self.partner_id or self.employee_id.work_contact_id
        if partner.company_id and partner.company_id != self.company_id:
            partner = partner.browse()
        lines = []
        for line in self.expense_lines:
            if not line.account_id:
                raise UserError(_('Set an account on the expense line "%s".', line.name or line.product_id.display_name))
            lines.append((0, 0, {
                'name': line.name or line.product_id.display_name or self.name,
                'account_id': line.account_id.id,
                'partner_id': partner.id or False,
                'debit': line.amount,
                'credit': 0.0,
                'analytic_distribution': {str(line.analytic_account_id.id): 100} if line.analytic_account_id else False,
            }))
        lines.append((0, 0, {
            'name': _('Petty cash expense %s', self.name),
            'account_id': petty_account.id,
            'partner_id': partner.id or False,
            'debit': 0.0,
            'credit': self.expense_amount,
        }))
        return {
            'move_type': 'entry',
            'journal_id': self.petty_journal_id.id,
            'date': self.date,
            'ref': self.name,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'line_ids': lines,
        }

    @api.constrains('petty_journal_id', 'company_id')
    def _check_journal_company(self):
        for expense in self:
            if expense.petty_journal_id and expense.petty_journal_id.company_id != expense.company_id:
                raise ValidationError(_('Journal %(journal)s belongs to %(journal_company)s, not to %(company)s.',
                                        journal=expense.petty_journal_id.name,
                                        journal_company=expense.petty_journal_id.company_id.name,
                                        company=expense.company_id.name))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.petty_journal_id.company_id != self.company_id:
            self.petty_journal_id = False

    def action_cofirm(self):
        for expense in self:
            if not expense.expense_lines or expense.expense_amount <= 0:
                raise ValidationError(_('Add at least one expense line with a positive amount.'))
            if expense.currency_id.compare_amounts(expense.expense_amount, expense.balance) > 0:
                raise ValidationError(_('%(employee)s has only %(balance)s petty cash balance in %(journal)s.',
                                        employee=expense.employee_id.name,
                                        balance=expense.currency_id.format(expense.balance),
                                        journal=expense.petty_journal_id.name))
            expense.state = 'confirm'

    def action_post_expense(self):
        """Book the expense: posts the journal entry and closes the expense."""
        if not self.env.su and not self.env.user.has_group('dev_petty_cash.group_petty_manager'):
            raise AccessError(_('Only a Petty Cash Manager can post expenses.'))
        for expense in self:
            if expense.state != 'confirm':
                continue
            move = self.env['account.move'].sudo().create(expense._prepare_move_vals())
            move.action_post()
            expense.write({'move_id': move.id, 'state': 'done'})

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    def action_cancel(self):
        for expense in self:
            if expense.move_id and expense.move_id.state == 'posted':
                expense.move_id.sudo().button_draft()
            if expense.move_id and expense.move_id.state == 'draft':
                expense.move_id.sudo().button_cancel()
            expense.state = 'cancel'

    def action_draft(self):
        self.write({'state': 'draft', 'move_id': False})

    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise ValidationError(_("You can delete expense in draft state only."))
        return super(petty_cash_expense, self).unlink()
        
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update({
                'name': self.env['ir.sequence'].next_by_code('petty.cash.expense') or '/',
            })
        return super(petty_cash_expense, self).create(vals_list)
        

class petty_expense_lines(models.Model):
    _name ='petty.expense.lines'
    _description = 'Petty Expense Lines'
    
    expense_id = fields.Many2one('petty.cash.expense', string='Expense', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Particulars')
    name = fields.Char(string='Description')
    account_id = fields.Many2one('account.account', string='Account')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    amount = fields.Monetary('Amount')
    currency_id = fields.Many2one(related='expense_id.currency_id', string='Currency')
    
    
    
    @api.onchange('product_id')
    def onchange_product(self):
        self.ensure_one()
        self = self.with_company(self.expense_id.company_id)
        self.name = self.product_id and self.product_id.name or ''
        if self.product_id:
            accounts = self.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=False)
            account_id = accounts['expense'] or False
            self.account_id = account_id and account_id.id or False
            self.amount = self.product_id.standard_price or 0.0
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
