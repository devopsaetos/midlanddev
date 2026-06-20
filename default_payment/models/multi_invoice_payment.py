# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MultiInvoicePayment(models.Model):
    _name = "multi.invoice.payment"
    # _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Multi Invoice Payment"

    invoice_id = fields.Many2one('account.move')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], string='Status', related='invoice_id.state', store=True)
    invoice_payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'In Payment'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy')],
        string='Payment State', related='invoice_id.payment_state', store=True)
    type = fields.Selection(selection=[
        ('entry', 'Journal Entry'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
        ('out_receipt', 'Sales Receipt'),
        ('in_receipt', 'Purchase Receipt'),
    ], string='Type', related='invoice_id.move_type', store=True)
    active = fields.Boolean('Active', default=True, tracking=True)
    payment_id = fields.Many2one('account.payment')
    payment_date = fields.Date(related='payment_id.date', store=True)
    partner_id = fields.Many2one('res.partner', related='invoice_id.partner_id', store=True)
    name = fields.Char(string='Number', related='invoice_id.name')
    invoice_date = fields.Date(string='Invoice/Bill Date', related='invoice_id.invoice_date')
    invoice_date_due = fields.Date(string='Due Date', related='invoice_id.invoice_date_due')
    amount_total_signed = fields.Monetary(string='Total Signed', related='invoice_id.amount_total')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id')
    payment_due = fields.Monetary("Payment Due", default=lambda i: i.invoice_id.amount_residual if i.invoice_id.move_type in ['out_invoice',
                                                                                                                          'in_refund'] else -1 * i.invoice_id.amount_residual)
    # payment_due_1 = fields.Monetary("Payment Due", default=lambda i:i.invoice_id.amount_residual_signed if i.invoice_id.move_type in ['out_invoice', 'in_refund'] else -1*i.invoice_id.amount_residual_signed)
    # payment_due = fields.Monetary("Payment Due" , related='invoice_id.amount_residual_signed', store=True)
    payment_amount = fields.Monetary("Payment Amount", compute='_compute_payment_amount', store=True, readonly=False)
    discount_amount = fields.Monetary()
    payment_difference = fields.Monetary(compute='_compute_payment_difference')
    payment_difference_handling = fields.Selection([
        ('open', 'Keep open'),
        ('reconcile', 'Mark invoice as fully paid'),
        ('advance_payment', 'Advance Payment')], string="Payment Difference Handling", copy=False)
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", domain="[('deprecated', '=', False)]", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(MultiInvoicePayment, self).create(vals_list)
        return res

    @api.onchange('payment_amount')
    def onchange_payment_amount(self):
        for rec in self:
            rec.payment_difference_handling = False
            rec.writeoff_account_id = False

    @api.onchange('payment_difference')
    def onchange_payment_difference(self):
        for inv in self:
            if inv.payment_difference and inv.payment_difference_handling == False:
                inv.write({
                    'payment_difference_handling': 'open',
                })

    @api.onchange('payment_difference_handling')
    def onchange_payment_difference_handling(self):
        for rec in self:
            if not rec.payment_difference_handling:
                rec.writeoff_account_id = False
            elif rec.payment_difference_handling == 'advance_payment':
                rec.write({'writeoff_account_id': self.env.company.clearing_account_id.id})
                print(rec.writeoff_account_id)

    @api.depends('payment_due', 'discount_amount')
    def _compute_payment_amount(self):
        for inv in self:
            if inv.payment_id.payment_type == 'outbound' and inv.discount_amount > 0:
                inv.discount_amount = inv.discount_amount * -1
            inv.payment_amount = inv.payment_due - inv.discount_amount

    @api.depends('discount_amount', 'payment_amount')
    def _compute_payment_difference(self):
        for inv in self:
            inv.payment_difference = inv.payment_due - inv.payment_amount - inv.discount_amount
