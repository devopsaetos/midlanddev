# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AllotmentApplication(models.Model):
    _name = 'file.allotment.application'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Allotment Application"

    name = fields.Char('Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'), tracking=True)
    by_pass_documents = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ])
    document_count = fields.Integer(compute='_document_count', string='# Documents')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    file_id = fields.Many2one('file', tracking=True)

    # Member Details
    membership_id = fields.Many2one('res.member', string='Member No')
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Member Type', related='membership_id.company_type')
    member_name = fields.Char(related='membership_id.name', string="Member Name")
    member_cnic = fields.Char('CNIC', related='membership_id.cnic')
    cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details', related='membership_id.cnic_line_ids', readonly=True)
    # Plot Detail
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
    tracking_id = fields.Char(related='file_id.tracking_id')
    booking_date = fields.Date(related='file_id.booking_date')

    # Payment Plan
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids',
                                           readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    deal_price = fields.Float()
    installment_created = fields.Boolean(related='file_id.installment_created', readonly=True)
    active = fields.Boolean(related='file_id.active', readonly=True)
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)
    total_installments_paid = fields.Float(compute='_compute_installment_amount')
    installments_paid = fields.Integer(compute='_compute_installment_amount')
    total_installments_due = fields.Float(compute='_compute_due_installment_amount')
    installments_due = fields.Integer(compute='_compute_due_installment_amount')
    payment_received = fields.Boolean()

    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),
        ('approved', 'Approved')
    ], default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('file.allotment.application.sequence') or _('New')
        new_record = super().create(vals_list)
        return new_record

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('You cannot delete this Record as it is processed now !'))
        return super(AllotmentApplication, self).unlink()

    def draft(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise ValidationError(_('You cannot change state to draft as the application is already invoiced!'))
            rec.state = 'draft'

    def invoice(self):
        for rec in self:
            # self.create_invoices()
            rec.state = 'invoiced'

    def approve(self):
        for rec in self:
            rec.state = 'approved'

    @api.onchange('file_id')
    def get_file_information(self):
        for rec in self:
            rec.membership_id = False
            if rec.file_id:
                rec.membership_id = rec.file_id.membership_id

    @api.onchange('file_id')
    def _compute_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s: s.installment_type != 'down' and s.invoice_created == True and s.payment_status == 'paid')
        if rec:
            self.total_installments_paid = sum(rec.mapped('amount_paid'))
            self.installments_paid = len(rec)
        else:
            self.total_installments_paid = 0
            self.installments_paid = 0

    @api.onchange('file_id')
    def _compute_due_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s: s.installment_type != 'down' and s.payment_status == 'not_paid' or s.payment_status == False)
        if rec:
            self.total_installments_due = sum(rec.mapped('amount'))
            self.installments_due = len(rec)
        else:
            self.total_installments_due = 0
            self.installments_due = 0

    def _document_count(self):
        for rec in self:
            document_ids = self.env['file.attachment'].search([('allotment_application_id', '=', rec.id)])
            rec.document_count = len(document_ids)

    def open_documents(self):
        return {
            'name': _('Required Documents'),
            'view_mode': 'form',
            'res_model': 'required.documents',
            'res_id': self.env['required.documents'].search([('allotment_application_id', '=', self.id)]).id,
            'view_id': self.env.ref("allotment.required_documents_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('allotment_application_id', '=', self.id)],
            'context': {'default_allotment_application_id': self.id},
            'target': 'self'
        }

    def open_taxes(self):
        return {
            'name': _('Required Taxes'),
            'view_mode': 'form',
            'res_model': 'required.taxes',
            'res_id': self.env['required.taxes'].search([('allotment_application_id', '=', self.id)]).id,
            'view_id': self.env.ref("allotment.required_taxes_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('allotment_application_id', '=', self.id)],
            'context': {'default_allotment_application_id': self.id,
                        'default_membership_id': self.membership_id.id,
                        },
            'target': 'self'
        }


class RequiredTaxesExt(models.Model):
    _inherit = 'required.taxes'

    allotment_application_id = fields.Many2one('file.allotment.application', string="Allotment application", tracking=True)
    allotment_required_tax_ids = fields.One2many('required.taxes.line', 'required_taxes_allotment_id')
    allotment_total_tax = fields.Float(compute='_compute_total_tax')

    @api.depends('allotment_required_tax_ids', 'seller_required_tax_ids', 'buyer_required_tax_ids', 'other_charges_ids')
    def _compute_total_tax(self):
        for rec in self:
            rec.seller_total_tax = sum(self.seller_required_tax_ids.mapped('amount'))
            rec.buyer_total_tax = sum(self.buyer_required_tax_ids.mapped('amount'))
            rec.buyer_total_tax = sum(self.buyer_required_tax_ids.mapped('amount'))
            rec.allotment_total_tax = sum(self.allotment_required_tax_ids.mapped('amount'))
            rec.total_charges = sum(self.other_charges_ids.mapped('amount'))


class RequiredTaxesLineExt(models.Model):
    _inherit = 'required.taxes.line'

    required_taxes_allotment_id = fields.Many2one('required.taxes', tracking=True)

    @api.depends('required_taxes_allotment_id.allotment_application_id', 'required_taxes_seller_id.transfer_req_id', 'required_taxes_buyer_id.transfer_req_id',
                 'rate')
    def _compute_amount(self):
        for rec in self:
            if rec.required_taxes_allotment_id:
                rec.amount = rec.required_taxes_allotment_id.allotment_application_id.net_sale_amount * (rec.rate / 100)
            if rec.required_taxes_seller_id:
                rec.amount = rec.required_taxes_seller_id.transfer_req_id.deal_price * (rec.rate / 100)
            if rec.required_taxes_buyer_id:
                rec.amount = rec.required_taxes_buyer_id.transfer_req_id.deal_price * (rec.rate / 100)


class RequiredDocumentsExt(models.Model):
    _inherit = 'required.documents'

    allotment_application_id = fields.Many2one('file.allotment.application', string="Allotment application", tracking=True)


class FileAttachmentExt(models.Model):
    _inherit = 'file.attachment'

    allotment_application_id = fields.Many2one('file.allotment.application', string="Allotment application", tracking=True)
