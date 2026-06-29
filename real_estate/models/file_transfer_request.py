# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import random
import string


class FileTransferRequest(models.Model):
    _name = 'file.transfer.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'name'
    _description = "File Transfer Request"

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'), tracking=True)

    membership_id = fields.Many2one('res.member', string='Member No', tracking=True)
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Member Type', related='membership_id.company_type')
    cnic = fields.Char(related='file_id.membership_id.cnic')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id')
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id')
    street_id = fields.Many2one('street', related='file_id.street_id')
    inventory_id = fields.Many2one('plot.inventory', related='file_id.inventory_id')
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='file_id.unit_category_type_id')
    unit_class_id = fields.Many2one('unit.class', related='file_id.unit_class_id')
    member_name = fields.Char(related='file_id.membership_id.name', string="Member Name")
    file_id = fields.Many2one('file')
    tracking_id = fields.Char(related='file_id.tracking_id', tracking=True)
    booking_date = fields.Date(related='file_id.booking_date')
    allow_request = fields.Boolean()
    reason = fields.Text()
    cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details', related='membership_id.cnic_line_ids', readonly=True)

    transfer_type = fields.Selection([
        ('sale', 'Sale'),
        ('gift', 'Gift'),
        ('inherit', 'Inherit'),
        ('open_file', 'Open File')
    ], tracking=True)

    by_pass_documents = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ])
    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('cancelation', 'Cancellation'),
        ('merge', 'Merge'),
        ('refund', 'Refund'),
    ], readonly=True, tracking=True)
    appointment_date = fields.Datetime(tracking=True)
    transferee_existing_partner = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], 'Is Member ?')
    transferee_partner_id = fields.Many2one('res.member', 'Name ', readonly=True, tracking=True)
    transferee_company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Transferee Type', related='transferee_partner_id.company_type')
    transferee_name = fields.Char('Transferee Name', readonly=True, tracking=True)
    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')

    relation_name = fields.Char(related='membership_id.relation_name')
    transferee_relation_name = fields.Char(tracking=True)
    transferee_cnic_number = fields.Char('CNIC Number', readonly=True, tracking=True)

    transferee_cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details ', related='transferee_partner_id.cnic_line_ids',
                                               readonly=True)

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
    deal_price = fields.Float(tracking=True)
    total_installments_paid = fields.Float(compute='_compute_installment_amount')
    installments_paid = fields.Integer(compute='_compute_installment_amount')
    total_installments_due = fields.Float(compute='_compute_due_installment_amount')
    installments_due = fields.Integer(compute='_compute_due_installment_amount')
    installment_created = fields.Boolean(related='file_id.installment_created')
    active = fields.Boolean(related='file_id.active')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment')

    total_documents_required = fields.Integer(compute='_compute_documents')
    total_taxes_required = fields.Integer(compute='_compute_taxes')

    traferer_setup_ids = fields.Many2many('requirements', 'requirements_transfer_request_rel', 'transfer_request_id',
                                          'requirement_id', readonly=True)
    traferee_setup_ids = fields.Many2many('requirements', readonly=True)
    traferer_tax_setup_ids = fields.Many2many('tax.setup.lines', 'tax_requirements_transfer_rel', 'transfer_request_id',
                                              'requirement_id')
    traferee_tax_setup_ids = fields.Many2many('tax.setup.lines')
    show_approve_button = fields.Boolean(compute="_compute_approve_button")

    @api.depends('allow_request')
    def _compute_approve_button(self):
        for rec in self:
            if rec.allow_request and rec.env.user.has_group('real_estate.group_transfer_disc_approvers') and rec.deal_price == 1.0:
                rec.show_approve_button = True
            elif not rec.allow_request:
                rec.show_approve_button = True
            elif rec.env.user.has_group('real_estate.group_approve_transfer_req') and rec.deal_price > 1.0:
                rec.show_approve_button = True
            else:
                rec.show_approve_button = False



    def _compute_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s: s.installment_type != 'down' and s.invoice_created == True and s.payment_status == 'paid')
        if rec:
            self.total_installments_paid = sum(rec.mapped('amount_paid'))
            self.installments_paid = len(rec)
        else:
            self.total_installments_paid = 0
            self.installments_paid = 0

    def _compute_due_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s: s.installment_type != 'down' and s.payment_status == 'not_paid' or s.payment_status == False)
        if rec:
            self.total_installments_due = sum(rec.mapped('amount'))
            self.installments_due = len(rec)
        else:
            self.total_installments_due = 0
            self.installments_due = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if self.env.company.id != 1:
                    random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    vals['name'] = 'PRN - ' + random_num
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code("file.transfer.request") or _('New')

        rec = super(FileTransferRequest, self).create(vals_list)

        return rec

    def request_cancel(self):
        self.file_id.state = 'available'
        self.state = 'cancel'

    def request_generate(self):
        docs = self.env['required.documents'].search([('transfer_req_id', '=', self.id)])
        if self.deal_price < 1 and self.transfer_type != 'open_file':
            raise ValidationError(_("Deal amount must be greater than or equal to 1."))
        if not docs and self.by_pass_documents != 'yes':
            raise ValidationError('Please get all the required documents.')
        taxes = self.env['required.taxes'].search([('transfer_req_id', '=', self.id)])
        # if not taxes:
        #     raise ValidationError('Please complete all the required taxes for seller/buyer.')

        rec = self.env['transfer.application']
        if not rec.search([('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]):
            self.file_id.state = 'inprocess'

            rec.create({
                'file_id': self.file_id.id,
                'membership_id': self.membership_id.id,
                'by_pass_documents': self.by_pass_documents,
                't_request_id': self.id,
                'appointment_date': self.appointment_date,
                'deal_price': self.deal_price,
                'allow_request': self.allow_request,
                'reason': self.reason,
                'transferee_existing_partner': self.transferee_existing_partner,
                'transferee_partner_id': self.transferee_partner_id.id,
                'transferee_company_type': self.transferee_company_type,
                'transferee_name': self.transferee_name,
                'transferee_cnic_number': self.transferee_cnic_number,
            })
            attachment = self.env['file.attachment']

            for recs in self.traferer_setup_ids:
                attachment.create({
                    'name': recs.name,
                    'transfer_type': 'transferer',
                    'transfer_id': rec.search([('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]).id
                })

            for recs in self.traferee_setup_ids:
                attachment.create({
                    'name': recs.name,
                    'transfer_type': 'transfree',
                    'transfer_id': rec.search([('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]).id
                })
            self.state = 'approved'
        else:
            raise ValidationError(_("Transfer form already generated of file : %s" % (self.file_id.name)))

    def _compute_documents(self):
        for rec in self:
            rec.total_documents_required = len(rec.traferer_setup_ids) + len(rec.traferee_setup_ids)

    def _compute_taxes(self):
        for rec in self:
            rec.total_taxes_required = len(rec.traferer_tax_setup_ids) + len(rec.traferee_tax_setup_ids)

    def required_documents(self):
        rule = []
        if self.traferee_setup_ids:
            if self.company_type == 'aop':
                for rec in self.membership_id.cnic_line_ids:
                    docs = self.env['setup'].search([('setup_for', '=', 'buyer'), ('transaction_type', '=', 'transfer')])
                    rule.append([0, 0, {'name': rec.member_name, 'rule': docs.id, 'party': docs.setup_for}])
            else:
                docs = self.env['setup'].search([('setup_for', '=', 'buyer'), ('transaction_type', '=', 'transfer')])
                rule.append([0, 0, {'name': self.membership_id.name, 'rule': docs.id, 'party': docs.setup_for}])
        if self.traferer_setup_ids:
            if self.transferee_company_type == 'aop':
                for rec in self.transferee_partner_id.cnic_line_ids:
                    docs = self.env['setup'].search([('setup_for', '=', 'seller'), ('transaction_type', '=', 'transfer')])
                    rule.append([0, 0, {'name': rec.member_name, 'rule': docs.id, 'party': docs.setup_for}])
            else:
                docs = self.env['setup'].search([('setup_for', '=', 'seller'), ('transaction_type', '=', 'transfer')], limit=1)
                for doc in docs.requirements_ids:
                    rule.append([0, 0, {'name': doc.name, 'rule': docs.id, 'party': docs.setup_for}])

        return {
            'name': _('Required Documents'),
            'view_mode': 'form',
            'res_model': 'required.documents',
            'res_id': self.env['required.documents'].search([('transfer_req_id', '=', self.id)]).id,
            'view_id': self.env.ref("real_estate.required_documents_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('transfer_req_id', '=', self.id)],
            'context': {'default_transfer_req_id': self.id,
                        'default_required_documents_line_ids': rule},
            'target': 'self'
        }

    def required_taxes(self):
        seller_rule = []
        buyer_rule = []
        if self.traferee_tax_setup_ids:
            taxes = self.env['tax.setup'].search([('setup_for', '=', 'seller'), ('transaction_type', '=', 'transfer')], limit=1)
            for rec in taxes.tax_setup_line_ids:
                if self.company_type == 'aop':
                    for lines in self.membership_id.cnic_line_ids:
                        if rec.tax_status == lines.tax_status:
                            seller_rule.append([0, 0,
                                                {'name': lines.member_name, 'product_id': rec.product_id.id, 'rate': rec.rate, 'rule': taxes.id,
                                                 'amount': self.deal_price * (rec.rate / 100)}])
                if rec.tax_status == self.membership_id.tax_status:
                    seller_rule.append([0, 0, {'name': self.membership_id.name, 'product_id': rec.product_id.id, 'rate': rec.rate, 'rule': taxes.id, 'amount': self.deal_price * (rec.rate / 100)}])

        if self.traferer_tax_setup_ids:
            taxes = self.env['tax.setup'].search([('setup_for', '=', 'buyer'), ('transaction_type', '=', 'transfer')], limit=1)
            for recs in taxes.tax_setup_line_ids:
                if self.transferee_company_type == 'aop':
                    for lines in self.transferee_partner_id.cnic_line_ids:
                        if recs.tax_status == lines.tax_status:
                            buyer_rule.append([0, 0,
                                               {'name': lines.member_name, 'product_id': recs.product_id.id, 'rate': recs.rate, 'rule': taxes.id,
                                                'amount': self.deal_price * (recs.rate / 100)}])
                if recs.tax_status == self.transferee_partner_id.tax_status:
                    buyer_rule.append([0, 0, {'name': self.transferee_partner_id.name, 'product_id': recs.product_id.id, 'rate': recs.rate, 'rule': taxes.id, 'amount': self.deal_price * (recs.rate / 100)}])

        return {
            'name': _('Required Taxes'),
            'view_mode': 'form',
            'res_model': 'required.taxes',
            'res_id': self.env['required.taxes'].search([('transfer_req_id', '=', self.id)]).id,
            'view_id': self.env.ref("real_estate.required_taxes_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('transfer_req_id', '=', self.id)],
            'context': {'default_transfer_req_id': self.id,
                        'default_membership_id': self.membership_id.id,
                        'default_transferee_partner_id': self.transferee_partner_id.id,
                        'default_seller_name': self.membership_id.name,
                        'default_buyer_name': self.transferee_partner_id.name,
                        'default_seller_required_tax_ids': seller_rule,
                        'default_buyer_required_tax_ids': buyer_rule
                        },
            'target': 'self'
        }

    def unlink(self):
        for rec in self:
            if rec.state == 'draft':
                rec.file_id.state = 'available'
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record once it is approved!'))

        return super(FileTransferRequest, self).unlink()


class ReqInvoicePopup(models.TransientModel):
    _name = "tax.invoice.popup"
    _description = "Tax Invoice Popup"

    required_tax_id = fields.Many2one('required.taxes', 'Required Taxes', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    date = fields.Date(required=True)
    journal_id = fields.Many2one('account.journal', 'Payment Journal', domain=[('type', 'in', ('cash', 'bank'))])
    cheque_name = fields.Char('Cheque Name')
    cheque_no = fields.Char('Cheque No.')
    bank_ref = fields.Char('Bank Reference')
    product_line = fields.One2many('tax.invoice.popup.line', 'tax_invoice_popup_id')
    payment_type = fields.Selection([('osp', 'One Step Payment'),
                                     ('tsp', 'Two Step Payment')], default=lambda self: self.env.company.payment_type)

    def create_invoice(self):
        prod = [(0, 0, {
            'product_id': rec.product_id.id,
            'name': rec.product_id.name,
            'account_id': rec.product_id.property_account_income_id.id,
            'quantity': rec.quantity,
            'price_unit': rec.unit_price,
            'company_id': self.env.company,
        }) for rec in self.product_line]

        invoice = self.env['account.move'].create({
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'company_id': self.env.company.id,
            'move_type': 'out_invoice',
            # 'user_id': self.required_tax_id.user_id.id,
            'required_tax_id': self.required_tax_id.id,
            'invoice_line_ids': prod
        })

        invoice.action_post()
        self.required_tax_id.invoice_id = invoice.id
        payment_type = self.env['res.company']._company_default_get().payment_type
        if payment_type and payment_type == 'osp':
            company = self.env.company
            payment = self.env['account.payment'].create({
                'partner_type': 'customer',
                'partner_id': self.partner_id.id,
                'amount': invoice.amount_residual,
                'memo': invoice.name,
                'cheque_name': self.cheque_name,
                'cheque_no': self.cheque_no,
                'bank_ref': self.bank_ref,
                'state': 'draft',
                'payment_type': 'inbound',
                'journal_id': self.journal_id.id,  # compulsory
                'req_id': self.req_id.id,
                'invoice_ids': [(4, invoice.id)]
            })
            payment.post()
            return True


class ReqInvoicePopupLine(models.TransientModel):
    _name = "tax.invoice.popup.line"
    _description = "Tax Invoice Popup Line"

    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Integer()
    unit_price = fields.Float()
    total = fields.Float()

    tax_invoice_popup_id = fields.Many2one('tax.invoice.popup')
