# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FileCancelApplication(models.Model):
    _name = 'file.cancel.application'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'name'
    _description = "File Cancel Application"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
    ], default='draft')

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))

    membership_id = fields.Many2one('res.member', string='Member No')
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id')
    member_name = fields.Char(related='file_id.membership_id.name')
    inventory_id = fields.Many2one('plot.inventory', related='file_id.inventory_id')
    file_id = fields.Many2one('file')
    tracking_id = fields.Char(related='file_id.tracking_id')
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id')

    transaction_type = fields.Selection([
        ('transfer', 'Cancel'),
        ('cancelation', 'Cancelation'),
        ('merge', 'Merge'),
        ('refund', 'Refund'),
    ], readonly=True)

    file_payment_history_id = fields.One2many('file.payment.history', 'file_id',
                                              related='file_id.file_payment_history_id')
    plan_description = fields.Char('Plan Description', related='file_id.plan_description')
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id')
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment')
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date')
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount')
    factor_amount = fields.Float(related='file_id.factor_amount')
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount')
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type')
    discount_amount = fields.Float(related='file_id.discount_amount')
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount')
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids')
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount')
    installment_created = fields.Boolean(related='file_id.installment_created')
    active = fields.Boolean(related='file_id.active')
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment')

    traferer_setup_ids = fields.Many2many('requirements', 'file_cance_request_rel', 'transfer_request_id',
                                          'requirement_id', readonly=True)
    traferee_setup_ids = fields.Many2many('requirements', readonly=True)
    reason = fields.Text()
    appointment_date = fields.Datetime(string='Date')
    request_by = fields.Selection(
        string='Request By',
        selection=[('dealer', 'Dealer'),
                   ('customer', 'Customer'), ],
        required=False, default='customer')

    cancel_type = fields.Selection(
        string='Cancel Type',
        selection=[('only_cancel', 'Only Cancel'),
                   ('cancel_and_reopen', 'Cancel And Reopen'), ],
        required=True, default='only_cancel')

    treat_booking_as = fields.Selection(
        string='Treat Booking As',
        selection=[('credit', 'Credit'),
                   ('advance_payment', 'Advance Payment'), ],
        required=True, default='credit')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("file.cancel.application") or _('New')
        rec = super(FileCancelApplication, self).create(vals_list)
        return rec

    def request_generate(self):
        for rec in self:
            current_date = fields.Date.today()
            installment_plan = rec.file_id.manual_installment_plan_ids or line.file_id.installment_plan_ids
            due_invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted').mapped('invoice_id')
            total_paid_amount = sum(installment_plan.filtered(lambda l: l.payment_status == 'paid').mapped('amount_paid'))
            installment_paid_amount = sum(installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'paid' and l.invoice_id.state == 'posted' and
                                                                              l.installment_type not in ['down', 'confirmation_amount']).mapped('amount_paid'))
            booking_amount = installment_plan.filtered(lambda l: l.payment_status == 'paid' and l.installment_type == 'down').mapped('amount_paid')
            dealer_share = installment_plan.filtered(lambda ins: ins.installment_type == 'down').dealer_share
            print(dealer_share)
            confirmation_installment = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'paid' and l.invoice_id.state == 'posted' and
                                                                           l.installment_type == 'confirmation_amount')
            confirmation_installment_invoice = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'paid' and l.invoice_id.state == 'posted' and
                                                                                   l.installment_type == 'confirmation_amount').mapped('id')
            net_booking_amount = sum(booking_amount) - dealer_share
            print(net_booking_amount)
            if rec.cancel_type == 'only_cancel':
                if due_invoices:
                    for invoice in due_invoices:
                        invoice.button_draft()
                        invoice.button_cancel()
                        reversed_entry = self.env['account.move'].sudo().search([('reversed_entry_id', '=', invoice.id)], order='id desc', limit=1)
                        if reversed_entry:
                            reversed_entry.date = current_date
                            reversed_entry.action_post()
                        for line_id in invoice.line_ids.filtered(lambda l: 'Reverse entry' in l.name):
                            line_id.date = current_date
                installment_ids = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted').mapped('id')
                if installment_ids:
                    self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(installment_ids),))
                if rec.file_id.investor_file or rec.file_id.investor_id or rec.file_id.investment_id:
                    credit_note_vals = {
                        'partner_id': rec.membership_id.partner_id.id,
                        'company_id': rec.env.company.id,
                        'invoice_date': rec.appointment_date,
                        'journal_id': rec.env.company.account_journal_id.id,
                        'ref': f"{rec.name} - {rec.file_id.name}",
                        'move_type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': rec.env.ref('real_estate.refund_product').product_id.id,
                            'name': f"Adjustment Amount For File {rec.file_id.name}",
                            'quantity': 1,
                            'price_unit': installment_paid_amount,
                        })],
                    }
                    credit_note = self.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = rec.file_id.id
                    credit_note.action_post()
                    # search for confirmation payment
                    confirmation_payments = self.env['multi.invoice.payment'].sudo().search([('invoice_id.id', '=', confirmation_installment.invoice_id.id)]).mapped('payment_id')
                    if confirmation_payments:
                        for payment in confirmation_payments:
                            payment.action_draft()
                            payment.cancel()
                    confirmation_installment.invoice_id.button_draft()
                    confirmation_installment.invoice_id.button_cancel()
                    self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(confirmation_installment_invoice),))
                    if self.treat_booking_as == 'credit':
                        booking_credit_note_vals = {
                            'partner_id': rec.file_id.investor_id.partner_id.id,
                            'company_id': rec.env.company.id,
                            'invoice_date': rec.appointment_date,
                            'journal_id': rec.env.company.account_journal_id.id,
                            'ref': f"{rec.name} - {rec.file_id.name}",
                            'move_type': 'out_refund',
                            'invoice_line_ids': [(0, 0, {
                                'product_id': rec.env.ref('real_estate.refund_product').product_id.id,
                                'name': f"Booking Adjustment Amount For File {rec.file_id.name}",
                                'quantity': 1,
                                'price_unit': net_booking_amount,
                            })],
                        }
                        booking_credit_created = self.env['account.move'].sudo().create(booking_credit_note_vals)
                        booking_credit_created.file_ids = rec.file_id.id
                        booking_credit_created.action_post()
                    if self.treat_booking_as == 'advance_payment':
                        adv_pay = self.env['account.payment'].create({
                            'state': 'draft',
                            'payment_category': 'advance_payment',
                            'advance_against': 'file' if rec.file_id else 'other',
                            'partner_id': rec.file_id.investor_id.partner_id.id,
                            'category_id': self.category_id.id,
                            # 'is_advance_payment': True,
                            # 'payment_type': rec.file_id.payment_type,
                            'payment_type': 'inbound',
                            'partner_type': 'customer',
                            'payment_date': fields.date.today(),
                            'currency_id': rec.file_id.company_id.currency_id.id,
                            'mode_of_payments': rec.file_id.investment_id.mode_of_payments,
                            'amount': net_booking_amount,
                            'advance_payment_account_id': self.env.company.file_cancel_adjust_account_id.id,
                            'journal_id': self.env.company.file_cancel_adjust_journal_id.id,
                            'memo': 'File Cancellation Booking Adjustment Amount',
                            'company_id': rec.file_id.company_id.id,
                            'branch_id': rec.file_id.branch_id.id,
                        })
                        adv_pay.post()
                else:
                    credit_note_vals = {
                        'partner_id': rec.membership_id.partner_id.id,
                        'company_id': rec.env.company.id,
                        'invoice_date': rec.appointment_date,
                        'file_ids': rec.file_id.id,
                        'journal_id': rec.env.company.account_journal_id.id,
                        'ref': f"{rec.name} - {rec.file_id.name}",
                        'move_type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': rec.env.ref('file_financials.product_merger_adjustment').id,
                            'name': f"Adjustment Amount For File {rec.file_id.name}",
                            'quantity': 1,
                            'price_unit': total_paid_amount,
                        })],
                    }
                    credit_note = rec.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = self.file_id.id
                    credit_note.action_post()
            else:
                if due_invoices:
                    for invoice in due_invoices:
                        invoice.button_draft()
                        invoice.button_cancel()
                        reversed_entry = self.env['account.move'].sudo().search([('reversed_entry_id', '=', invoice.id)], order='id desc', limit=1)
                        if reversed_entry:
                            reversed_entry.date = current_date
                            reversed_entry.action_post()
                        for line_id in invoice.line_ids.filtered(lambda l: 'Reverse entry' in l.name):
                            line_id.date = current_date
                installment_ids = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted').mapped('id')
                if installment_ids:
                    self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(installment_ids),))
                # Create Open File
                investor_files = self.env['investor.file']
                if rec.file_id.investor_file or rec.file_id.investor_id or rec.file_id.investment_id:
                    credit_note_vals = {
                        'partner_id': rec.membership_id.id,
                        'company_id': rec.env.company.id,
                        'invoice_date': rec.appointment_date,
                        'journal_id': rec.env.company.account_journal_id.id,
                        'ref': f"{rec.name} - {rec.file_id.name}",
                        'move_type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': rec.env.ref('real_estate.refund_product').product_id.id,
                            'name': f"Adjustment Amount For File {rec.file_id.name}",
                            'quantity': 1,
                            'price_unit': installment_paid_amount,
                        })],
                    }
                    credit_note = self.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = self.file_id.id
                    credit_note.action_post()
                    # search for confirmation payment
                    confirmation_payments = self.env['multi.invoice.payment'].sudo().search([('invoice_id.id', '=', confirmation_installment.invoice_id.id)]).mapped('payment_id')
                    if confirmation_payments:
                        for payment in confirmation_payments:
                            payment.action_draft()
                            payment.cancel()
                    confirmation_installment.invoice_id.button_draft()
                    confirmation_installment.invoice_id.button_cancel()
                    self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(confirmation_installment_invoice),))
                    open_file_data = {
                        'investor_id': rec.file_id.investor_id.id,
                        'investment_id': rec.file_id.investment_id.id,
                        'state': 'open',
                        'society_id': rec.file_id.society_id.id,
                        'project_type': rec.file_id.society_id.project_type,
                        'phase_id': rec.file_id.phase_id.id,
                        'sector_id': rec.file_id.sector_id.id,
                        'street_id': rec.file_id.street_id.id,
                        'category_id': rec.file_id.category_id.id,
                        'unit_category_type_id': rec.file_id.unit_category_type_id.id,
                        'size_id': rec.file_id.size_id.id,
                        'payment_type': rec.file_id.payment_type,
                        'plan_type': rec.file_id.plan_type,
                        'predefine_plan_id': rec.file_id.predefine_plan_id.id,
                        'interval_id': rec.file_id.interval_id.id,
                        'starting_date': self.appointment_date.strftime('%Y-%m-%d'),
                        'total_installment': rec.file_id.total_installment,
                        'payment_states': 'open',
                        'sale_amount': self.sale_amount,
                        'ttl_sale_amount': self.ttl_sale_amount,
                        'net_sale_amount': self.net_sale_amount,
                        'initial_payment': self.initial_payment,
                    }
                    open_file = investor_files.sudo().create(open_file_data)
                    if open_file:
                        booking = open_file.installment_plan_ids.filtered(lambda l: l.installment_type == 'down').mapped('id')
                        if booking:
                            self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'paid' WHERE id IN %s""", (tuple(booking),))
                        return {
                            'name': 'Investor File Management',
                            'view_mode': 'form',
                            'res_model': 'investor.file',
                            'res_id': open_file.id,
                            'type': 'ir.actions.act_window',
                            'target': 'current',
                        }
                else:
                    credit_note_vals = {
                        'partner_id': rec.membership_id.partner_id.id,
                        'company_id': rec.env.company.id,
                        'invoice_date': rec.appointment_date,
                        # 'file_ids': rec.file_id.id,
                        'journal_id': rec.env.company.account_journal_id.id,
                        'ref': f"{rec.name} - {rec.file_id.name}",
                        'move_type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': rec.env.ref('file_financials.product_merger_adjustment').id,
                            'name': f"Adjustment Amount For File {rec.file_id.name}",
                            'quantity': 1,
                            'price_unit': total_paid_amount,
                        })],
                    }
                    credit_note = rec.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = self.file_id.id
                    credit_note.action_post()
                rec.file_id.state = 'cancel'
                rec.file_id.file_status = 'cancel'
            rec.file_id.state = 'cancel'
            rec.file_id.file_status = 'cancel'
        self.state = 'cancel'

    def unlink(self):
        for rec in self:
            if rec.state == 'cancel':
                raise UserError(_('You cannot delete a record once it is approved!'))
        return super(FileCancelApplication, self).unlink()
