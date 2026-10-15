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
from odoo.exceptions import AccessError, ValidationError


class petty_cash_request(models.Model):
    _name = 'petty.cash.request'
    _description = 'Petty Cash Management'
    _order = 'name desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _get_request_by(self):
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
        return employee_id.id or False

    name = fields.Char('Name', default='/', tracking=1)
    note = fields.Text('Notes')
    request_to = fields.Many2one('hr.employee', string='Request To')
    request_by = fields.Many2one('hr.employee', string='Request By', default=_get_request_by)
    payment_journal_id = fields.Many2one(
        'account.journal', string='From (Payment Journal)',
        domain="[('type', 'in', ['bank', 'cash']), ('is_petty_cash', '=', False), ('company_id', '=', company_id)]",
        help='Bank / cash journal the money is paid out of.')
    petty_journal_id = fields.Many2one(
        'account.journal', string='To (Petty Cash Journal)', tracking=2,
        domain="[('is_petty_cash', '=', True), ('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]",
        help='Petty cash journal (fund) that receives the money.')
    date = fields.Date('Date', copy=False, default=fields.Datetime.now)
    request_amount = fields.Monetary('Request Amount', tracking=2)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    state = fields.Selection(string='State', selection=[('draft', 'Draft'),
                                                        ('request', 'Requested'),
                                                        ('approve', 'Approved'),
                                                        ('cancel', 'Cancel'),
                                                        ('reject', 'Reject')], default='draft', tracking=4)
    payment_id = fields.Many2one('account.payment', string='Payment', copy=False)
    balance = fields.Monetary('Balance', compute='_get_balance')

    @api.depends('request_amount')
    def _get_balance(self):
        for request in self:
            request.balance = request.request_amount

    @api.constrains('payment_journal_id', 'petty_journal_id', 'company_id')
    def _check_journals(self):
        for request in self:
            if request.payment_journal_id and request.payment_journal_id == request.petty_journal_id:
                raise ValidationError(_('The payment journal and the petty cash journal must be different.'))
            for journal in request.payment_journal_id | request.petty_journal_id:
                if journal.company_id != request.company_id:
                    raise ValidationError(_('Journal %(journal)s belongs to %(journal_company)s, not to %(company)s.',
                                            journal=journal.name, journal_company=journal.company_id.name,
                                            company=request.company_id.name))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.payment_journal_id.company_id != self.company_id:
            self.payment_journal_id = False
        if self.petty_journal_id.company_id != self.company_id:
            self.petty_journal_id = False

    def create_payment(self):
        """Fund the petty cash: pay the amount out of the payment journal into the petty
        cash journal's account (Dr Petty Cash / Cr Bank)."""
        self.ensure_one()
        petty_account = self.petty_journal_id._petty_cash_account()
        method_lines = self.payment_journal_id.outbound_payment_method_line_ids
        payment_method_line = method_lines.filtered(lambda l: l.code == 'manual')[:1] or method_lines[:1]
        if not payment_method_line:
            raise ValidationError(_('Configure at least one outgoing payment method on the payment journal %s.',
                                    self.payment_journal_id.name))
        # Odoo 19 books no journal entry for a payment without outstanding account: credit the
        # payment method's account, else the paying journal's own cash / bank account
        outstanding_account = payment_method_line.payment_account_id or self.payment_journal_id.default_account_id
        if not outstanding_account:
            raise ValidationError(_('Set a default account on the payment journal %s.', self.payment_journal_id.name))
        partner = self.request_by.work_contact_id
        if partner.company_id and partner.company_id != self.company_id:
            partner = partner.browse()  # contact of another company: leave the payment without partner
        payment = self.env['account.payment'].sudo().create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': partner.id or False,
            'company_id': self.company_id.id,
            'amount': self.request_amount,
            'currency_id': self.currency_id.id,
            'date': self.date,
            'memo': self.name,
            'journal_id': self.payment_journal_id.id,
            'destination_account_id': petty_account.id,
            'payment_method_line_id': payment_method_line.id,
        })
        payment.outstanding_account_id = outstanding_account
        payment.action_post()
        self.payment_id = payment

    def action_request(self):
        for request in self:
            if request.request_amount <= 0:
                raise ValidationError(_('Request Amount must be positive.'))
            request.state = 'request'

    def action_approve(self):
        if not self.env.su and not self.env.user.has_group('dev_petty_cash.group_petty_manager'):
            raise AccessError(_('Only a Petty Cash Manager can approve requests.'))
        for request in self:
            request.create_payment()
            request.state = 'approve'

    def action_cancel(self):
        self.state = 'cancel'

    def action_reject(self):
        if not self.env.su and not self.env.user.has_group('dev_petty_cash.group_petty_manager'):
            raise AccessError(_('Only a Petty Cash Manager can reject requests.'))
        self.state = 'reject'

    def action_draft(self):
        self.state = 'draft'

    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise ValidationError(_("You can delete Petty request in draft state only."))
        return super(petty_cash_request, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update({
                'name': self.env['ir.sequence'].next_by_code('petty.cash.request') or '/',
            })
        return super(petty_cash_request, self).create(vals_list)

# class account_payment(models.Model):
#    _inherit='account.payment'
#    
#    @api.model
#    def create(self,vals):
#        res = super(account_payment,self).create(vals)
#        return res        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
