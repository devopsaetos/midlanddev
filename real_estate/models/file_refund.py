# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FileRefund(models.Model):
    _name = 'file.refund'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'name'
    _description = "File Refund"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('refund', 'Refund'),
    ], default='draft')

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))

    deduction_refund = fields.Float('Deduction(%)')

    membership_id = fields.Many2one('res.member', string='Member No')
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id')
    member_name = fields.Char(related='file_id.membership_id.name')
    inventory_id = fields.Many2one('plot.inventory', related='file_id.inventory_id')
    file_id = fields.Many2one('file')
    tracking_id = fields.Char(related='file_id.tracking_id')
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id')

    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
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

    traferer_setup_ids = fields.Many2many('requirements', 'requirements_request_rel', 'transfer_request_id',
                                          'requirement_id', readonly=True)
    traferee_setup_ids = fields.Many2many('requirements', readonly=True)
    booking_date = fields.Date(related='file_id.booking_date')
    deduction_type = fields.Selection([
        ('on_paid_amount', 'On Paid Amount'),
        ('on_file_amount', 'On File Amount'),
        ('select_deduction_type', 'Select Deduction Type')
    ], default='select_deduction_type')

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("file.refund.application") or _('New')

        rec = super(FileRefund, self).create(vals_list)

        return rec

    def request_generate(self):
        if self.deduction_type not in ['on_paid_amount', 'on_file_amount']:
            raise ValidationError(_('You should have to set "Deduction Type" first.'))

        processing_fee = self.file_id.file_payment_ids.filtered(
            lambda r: r.product_id.name == 'PROCESSING FEE').total or 0.0
        amount_paid = sum(self.file_id.installment_plan_ids.mapped('amount_paid')) \
            if self.deduction_type == 'on_paid_amount' else self.file_id.net_sale_amount
        deduction_amount = amount_paid * (self.deduction_refund / 100)
        reimbursable_amount = amount_paid - deduction_amount - processing_fee

        if reimbursable_amount <= 0.0:
            raise ValidationError(_('Your paid amount is not refundable'))

        refund_invoice = self.env['account.move'].create({
            'name': self.file_id.name,
            # 'file_ids': self.file_id.id,
            'move_type': 'in_invoice',
            'company_id': self.env.company.id,
            'journal_id': self.env.company.knockoff_journal_id.id,
            'partner_id': self.membership_id.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_date_due': fields.Date.today(),
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.env.ref('real_estate.refund_product').product_id.id,
                    'name': self.env.ref('real_estate.refund_product').name,
                    'account_id': self.env.ref('real_estate.refund_product').product_id.property_account_expense_id.id,
                    'price_unit': amount_paid
                }),
                (0, 0, {
                    'product_id': self.env.ref('real_estate.deductions').product_id.id,
                    'name': self.env.ref('real_estate.deductions').name,
                    # 'account_id': self.env.ref('real_estate.deductions').property_account_expense_id.id,
                    'price_unit': (deduction_amount + processing_fee) * -1
                })
            ]
        })
        refund_invoice.file_ids = self.file_id.id
        refund_invoice.action_post()
        self.state = 'refund'
        self.file_id.state = 'refund'
        self.file_id.file_status = 'cancel'
        self.file_id.inventory_id.state = 'avalible_for_sale'
