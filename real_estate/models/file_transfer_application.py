# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import secrets


class TransferApplication(models.Model):
    _name = 'transfer.application'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 't_request_id'
    _description = "Transfer Application"

    name = fields.Char(default='Transfer Application')

    state = fields.Selection([
        ('open', 'Open'),
        ('transfered', 'Transferred')
    ], default='open', tracking=True)

    stages = fields.Selection([
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),

    ], default='draft')
    by_pass_documents = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ])

    transfer_type = fields.Selection([
        ('sale', 'Sale'),
        ('gift', 'Gift'),
        ('inherit', 'Inherit'),
        ('open_file', 'Open File')
        ],related="t_request_id.transfer_type")
    appointment_date = fields.Datetime(related='t_request_id.appointment_date')
    
    document_count = fields.Integer(compute='_document_count', string='# Documents')

    file_id = fields.Many2one('file', tracking=True)

    # Transferer
    image = fields.Binary(related='membership_id.image_1920', string="Image")
    membership_id = fields.Many2one('res.member', string='Member No')
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Member Type', related='membership_id.company_type')
    member_name = fields.Char(related='membership_id.name',string="Member Name")
    member_cnic = fields.Char('CNIC', related='membership_id.cnic')

    cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details', related='membership_id.cnic_line_ids', readonly=True)

    # Transferee
    transferee_existing_partner = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], 'Is Member ?')
    transferee_image = fields.Binary(related='transferee_partner_id.image_1920', string='Transferee Image')
    transferee_partner_id = fields.Many2one('res.member', 'Member No ',
                                            store=True, tracking=True)
    transferee_company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Transferee Type', related='transferee_partner_id.company_type')
    transferee_partner_id_name = fields.Char('Name ', related='t_request_id.transferee_partner_id.name')
    transferee_name = fields.Char('Transferee Name')
    transferee_cnic_number = fields.Char('CNIC ')

    transferee_cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details ', related='transferee_partner_id.cnic_line_ids', readonly=True)

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
    t_request_id = fields.Many2one('file.transfer.request')
    tracking_id = fields.Char(related='file_id.tracking_id', tracking=True)
    booking_date = fields.Date(related='file_id.booking_date')
    allow_request = fields.Boolean()
    reason = fields.Text()

    # Payment Plan
    file_payment_history_id = fields.One2many('file.payment.history', 'file_id',
                                              related='file_id.file_payment_history_id', readonly=True)
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

    # Combine Photo
    # we can use for adjusting the max_width=100, max_height=100
    combine_image = fields.Image(string='Combine Image')

    file_payment_ids = fields.One2many('file.payment', 'transfer_application_id')

    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    transfer_date = fields.Date('Transfer Date', required=True, default=fields.Date.today,)

    payment_by = fields.Selection([
        ('transferor', 'Transferor'),
        ('tranferee', 'Tranferee')
    ], string="Payment made by")
    transfer_witness_ids = fields.One2many('transfer.witness', 'transfer_application_id')
    tax_invoice_created = fields.Boolean(default=False)
    wave_transfer_fee = fields.Selection([
        ('yes','Yes'),
        ('no','No'),
    ], default='no')
    wave_transfer_amount = fields.Float()
    secret_token = fields.Char(string="Secret Token", required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)
    noc_reference = fields.Text()


    # @api.model
    def assign_secret_tokens(self):
        # Fetch records that have the token as 'New' or empty
        records_with_default_token = self.search([('secret_token', '=', 'New')])
        for record in records_with_default_token:
            # Assign a new unique token if the token is still 'New'
            record.secret_token = secrets.token_hex(10)

    def _compute_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s : s.installment_type != 'down' and s.invoice_created == True and s.payment_status == 'paid')
        if rec:
            self.total_installments_paid = sum(rec.mapped('amount_paid'))
            self.installments_paid = len(rec)
        else:
            self.total_installments_paid = 0
            self.installments_paid = 0

    def _compute_due_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(lambda s : s.installment_type != 'down' and s.payment_status == 'not_paid' or s.payment_status == False)
        if rec:
            self.total_installments_due = sum(rec.mapped('amount'))
            self.installments_due = len(rec)
        else:
            self.total_installments_due = 0
            self.installments_due = 0

    def _document_count(self):
        for each in self:
            document_ids = self.env['file.attachment'].search([('transfer_id', '=', each.id)])
            each.document_count = len(document_ids)

    def document_view(self):
        self.ensure_one()
        domain = [
            ('transfer_id', '=', self.id)]
        return {
            'name': _('Documents'),
            'domain': domain,
            'res_model': 'file.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'list,form',
            'view_type': 'form',
            'help': _('''<p class="oe_view_nocontent_create">
                           Click to Create for New Documents
                        </p>'''),
            'limit': 80,
            'context': "{'default_transfer_id': '%s', 'current_view': 'realestate'}" % self.id
        }

    def open_documents(self):
        return {
            'name': _('Required Documents'),
            'view_mode': 'form',
            'res_model': 'required.documents',
            'res_id': self.env['required.documents'].search([('transfer_req_id', '=', self.t_request_id.id)]).id,
            'view_id': self.env.ref("real_estate.required_documents_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('transfer_req_id', '=', self.t_request_id.id)],
            'context': {'default_transfer_app_id': self.id},
            'target': 'self'
        }

    def open_taxes(self):
        return {
            'name': _('Required Taxes'),
            'view_mode': 'form',
            'res_model': 'required.taxes',
            'res_id': self.env['required.taxes'].search([('transfer_req_id', '=', self.t_request_id.id)]).id,
            'view_id': self.env.ref("real_estate.required_taxes_form").id,
            'type': 'ir.actions.act_window',
            'domain': [('transfer_req_id', '=', self.t_request_id.id)],
            'context': {'default_transfer_app_id': self.id,
                        'default_other_charges_ids': [(0, 0, {'product_id': self.env.ref('real_estate.file_transfer').id})],
                        'default_charges_partner_id': self.membership_id.id if self.payment_by == 'transferor' or self.transfer_type == 'open' else self.transferee_partner_id.id,
                        'default_membership_id': self.membership_id.id,
                        },
            'target': 'self'
        }

    def create_invoice(self):
        if not self.payment_by:
            raise ValidationError(_('Please select "Payment Made BY" field'))

        if self.payment_by == "transferor":
            partner_id = self.membership_id.partner_id
        elif self.payment_by == "tranferee":
            partner_id = self.transferee_partner_id.partner_id

        if self.file_payment_ids:
            prod = [(0, 0, {
                'product_id': rec.product_id.id,
                'name': rec.product_id.name,
                'account_id': rec.product_id.property_account_income_id.id,
                'price_unit': rec.value if rec.payment_type == 'fix' else
                [self.file_id.net_sale_amount * rec.value / 100][0]
            }) for rec in self.file_payment_ids]

            invoice = self.env['account.move'].create({
                'transfer_application_id': self.id,
                # 'file_ids': self.file_id.id,
                'partner_id': partner_id.id,
                'account_id': self.membership_id.partner_id.property_account_receivable_id.id,
                'property_invoice_type': 'transfer_application',
                'type': 'out_invoice',
                'invoice_date': fields.Date.today(),
                'company_id': self.env.company.id,
                'invoice_line_ids': prod
            })
            invoice.file_ids = self.file_id.id
            invoice.action_post()

            self.stages = 'invoiced'
        else:
            raise ValidationError(_('Please add fees entry first'))

    def create_tax_invoices(self):
        taxes = self.env['required.taxes'].search([('transfer_req_id', '=', self.t_request_id.id)])
        if not self.transferee_partner_id and self.transfer_type != 'open_file':
            raise ValidationError("Please Create Member first to generate invoice.")

        # for recs in self:
        #     if recs.wave_transfer_fee == 'no':
        #         prod = [(0, 0, {
        #             'product_id': recs.env.ref('real_estate.file_transfer').id,
        #             'name': recs.env.ref('real_estate.file_transfer').name,
        #             'account_id': recs.env.ref('real_estate.file_transfer').property_account_income_id.id,
        #             'price_unit': recs.env.company.transfer_fee
        #         })]
        #
        #         invoice = recs.env['account.move'].create({
        #             'transfer_application_id': recs.id,
        #             'partner_id': recs.membership_id.id,
        #             'property_invoice_type': 'others',
        #             'type': 'out_invoice',
        #             'invoice_date': fields.Date.today(),
        #             'company_id': recs.env.company.id,
        #             'branch_id': recs.env.branch.id,
        #             'invoice_line_ids': prod
        #         })
        #
        #         invoice.action_post()
        #         self.tax_invoice_created = True
        #
        #     elif recs.wave_transfer_fee == 'yes' and recs.wave_transfer_amount >= 1:
        #         if recs.wave_transfer_amount < recs.env.company.transfer_fee:
        #             prod = [(0, 0, {
        #                 'product_id': recs.env.ref('real_estate.file_transfer').id,
        #                 'name': recs.env.ref('real_estate.file_transfer').name,
        #                 'account_id': recs.env.ref('real_estate.file_transfer').property_account_income_id.id,
        #                 'price_unit': recs.env.company.transfer_fee - recs.wave_transfer_amount
        #             })]
        #
        #             invoice = recs.env['account.move'].create({
        #                 'transfer_application_id': recs.id,
        #                 'partner_id': recs.membership_id.id,
        #                 'property_invoice_type': 'others',
        #                 'type': 'out_invoice',
        #                 'invoice_date': fields.Date.today(),
        #                 'company_id': recs.env.company.id,
        #                 'branch_id': recs.env.branch.id,
        #                 'invoice_line_ids': prod
        #             })
        #
        #             invoice.action_post()
        #             self.tax_invoice_created = True
        #
        #     else:
        #         raise ValidationError('Wave transfer amount must be greater than or equal to 1.')

        for rec in taxes:
            if rec.seller_required_tax_ids:
                seller_products = rec.seller_required_tax_ids.mapped('product_id')
                seller_unique_prods = []
                for x in seller_products:
                    if x not in seller_unique_prods:
                        seller_unique_prods.append(x.id)
                for lines in rec.seller_required_tax_ids:
                    for product in rec.env['product.product'].browse(seller_unique_prods):
                        if product == lines.product_id:
                            amount = sum(rec.seller_required_tax_ids.search([('required_taxes_seller_id', '=', taxes.id),
                                                                            ('product_id', 'in',seller_unique_prods)]).mapped('amount'))
                            prod = [(0, 0, {
                                'product_id': product.id,
                                'name': product.name,
                                'account_id': product.property_account_income_id.id,
                                'price_unit': amount
                            })]

                invoice = self.env['account.move'].create({
                    'transfer_application_id': self.id,
                    # 'file_ids': self.file_id.id,
                    'partner_id': taxes.membership_id.partner_id.id,
                    'property_invoice_type': 'others',
                    'type': 'out_invoice',
                    'invoice_date': fields.Date.today(),
                    'company_id': self.env.company.id,
                    'invoice_line_ids': prod
                })
                invoice.file_ids = self.file_id.id
                invoice.action_post()

            if rec.buyer_required_tax_ids:
                buyer_products = rec.buyer_required_tax_ids.mapped('product_id')
                buyer_unique_prods = []
                for x in buyer_products:
                    if x not in buyer_unique_prods:
                        buyer_unique_prods.append(x.id)
                for lines in rec.buyer_required_tax_ids:
                    for product in self.env['product.product'].browse(buyer_unique_prods):
                        if product == lines.product_id:
                            amount = sum(rec.buyer_required_tax_ids.search([('required_taxes_buyer_id','=',taxes.id),('product_id','in',buyer_unique_prods)]).mapped('amount'))
                            prod= [(0, 0, {
                                'product_id': product.id,
                                'name': product.name,
                                'account_id': product.property_account_income_id.id,
                                'price_unit': amount
                            })]

                invoice = self.env['account.move'].create({
                    'transfer_application_id': self.id,
                    # 'file_ids': self.file_id.id,
                    'partner_id': taxes.transferee_partner_id.partner_id.id,
                    'property_invoice_type': 'others',
                    'type': 'out_invoice',
                    'invoice_date': fields.Date.today(),
                    'company_id': self.env.company.id,
                    'invoice_line_ids': prod
                })
                invoice.file_ids = self.file_id.id
                invoice.action_post()
            if rec.other_charges_ids:
                for lines in rec.other_charges_ids:
                    prod = [(0, 0, {
                            'product_id': lines.product_id.id,
                            'name': lines.product_id.name,
                            'account_id': lines.product_id.property_account_income_id.id,
                            'price_unit': lines.amount
                            })]

                invoice = self.env['account.move'].create({
                    'transfer_application_id': self.id,
                    # 'file_ids': self.file_id.id,
                    'partner_id': taxes.charges_partner_id.partner_id.id,
                    'property_invoice_type': 'others',
                    'type': 'out_invoice',
                    'invoice_date': fields.Date.today(),
                    'company_id': self.env.company.id,
                    'invoice_line_ids': prod
                })
                invoice.file_ids = self.file_id.id
                invoice.action_post()

                self.tax_invoice_created = True

    def generate_invoice(self):
        if not self.transferee_partner_id:
            raise ValidationError("Please Create Member first to generate invoice.")
        context = {
            'default_invoice_line': [(0, 0, {'product_id': self.env.ref('real_estate.file_transfer').id,
                                             'from_file_transfer': True})],
            'default_file_id': self.file_id.id,
            'default_transfer_application_id': self.id,
            'default_from_file_transfer': True,
            'default_membership_id': self.membership_id.id if self.payment_by == 'transferor' else self.transferee_partner_id.id,
        }
        return {
            'res_model': 'invoice.popup',
            'type': 'ir.actions.act_window',
            'context': context,
            # 'domain': [('customer_id', '=', self.customer_id)],
            'view_mode': 'form',
            'view_type': 'form',
            # 'res_id': self.env['token.money'].search([('crm_id', '=', self.id)]).id,
            'view_id': self.env.ref("real_estate.invoice_popup").id,
            'target': 'new'
        }

    def create_partner(self):
        return {
            'name': _('Transferee Member'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.member',
            'view_id': self.env.ref('real_estate.view_member_form').id,
            'type': 'ir.actions.act_window',
            'context': {'default_name': self.transferee_name,
                        'default_cnic': self.transferee_cnic_number, 'current_view': 'realestate', 'default_project_type': 'housing_society'},
            'target': 'new'
        }

    def open_invoices(self):
        domain = [('transfer_application_id', '=', self.id)]
        # if self.payment_by == 'transferor':
        #     domain = [('file_ids', '=', self.file_id.id),('partner_id', '=', self.membership_id.id),('transfer_application_id', '=', self.id)]
        # if self.payment_by == 'tranferee':
        #     domain = [('file_ids', '=', self.file_id.id),('partner_id', '=', self.transferee_partner_id.id),('transfer_application_id', '=', self.id)]
        return {
            'name': _('Member Invoices'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': domain,
            'context': {
                'current_view': 'realestate'
            }
        }

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(self.env['account.move'].search([('transfer_application_id', '=', self.id)]).mapped('id'))
        # self.no_of_invoices = 0
        # if self.payment_by == 'transferor':
        #     domain = [('file_ids', '=', self.file_id.id), ('partner_id', '=', self.membership_id.id),('transfer_application_id', '=', self.id)]
        #     self.no_of_invoices = len(
        #         self.env['account.move'].search(domain).mapped('id'))
        # if self.payment_by == 'tranferee':
        #     domain = [('file_ids', '=', self.file_id.id), ('partner_id', '=', self.transferee_partner_id.id),('transfer_application_id', '=', self.id)]
        #     self.no_of_invoices = len(
        #         self.env['account.move'].search(domain).mapped('id'))

    def print_invoice(self):
        return self.env['account.move'].search([('name', '=', self.t_request_id.name), (
        'property_invoice_type', '=', 'transfer_application')]).invoice_print()

    def file_transfer(self):
        docs = self.env['required.documents'].search([('transfer_req_id', '=', self.t_request_id.id)])

        if self.transfer_type != 'open_file':
            if self.transferee_existing_partner != 'yes':
                raise ValidationError(_('Please create partner first'))
            if not all(docs.required_documents_line_ids.mapped('attachment')):
                raise ValidationError('Please attach all the required documents.')
            if self.wave_transfer_fee == 'no' and self.no_of_invoices < 1:
                raise ValidationError(_('Please create transfer fee invoice first.'))
            if self.wave_transfer_fee == 'yes' and self.wave_transfer_amount < self.env.company.transfer_fee and self.no_of_invoices < 1:
                raise ValidationError(_('Please create transfer fee invoice first.'))
            if not self.transfer_witness_ids:
                raise ValidationError(_('Please add witness'))
            if not self.combine_image:
                raise ValidationError(_('Please add combine image'))
            if self.wave_transfer_fee == 'no' and not self.payment_received:
                raise ValidationError(_('Please pay the transfer fee to confirm transfer.'))
            not_paid_installments = self.file_id.installment_plan_ids.filtered(
                lambda l: l.invoice_created == True and l.payment_status == 'not_paid')
            if self.allow_request and not_paid_installments:
                for installment in not_paid_installments:
                    credit_note_wizard = self.env['account.move.reversal'].with_context(
                        {'active_ids': [installment.invoice_id.id], 'active_id': installment.invoice_id.id,
                         'active_model': 'account.move'}).create({
                        'refund_method': 'cancel',
                        # this is the only mode for which the SO line is linked to the refund (https://github.com/odoo/odoo/commit/e680f29560ac20133c7af0c6364c6ef494662eac)
                        'reason': 'File transfer',
                        'file_ids': installment.file_id.id,
                    })
                    credit_note_wizard.reverse_moves()
                    installment.invoice_id = False
                    installment.invoice_created = False

                    prod = []

                    if self.env.company.ownership_percentage and installment.file_id.membership_id.company_type == 'aop':
                        for member in installment.file_id.membership_id.cnic_line_ids:
                            if installment.installment_type == 'final':
                                prod.append((0, 0, {
                                    'product_id': self.env.ref('real_estate.final_product').id,
                                    'name': member.member_name,
                                    'account_id': self.env.ref(
                                        'real_estate.final_product').property_account_income_id.id,
                                    'price_unit': (installment.amount * member.ownership) / 100,
                                    # 'tax_ids': tax_ids,
                                }))
                            elif installment.installment_type == 'installment':
                                prod.append((0, 0, {
                                    'product_id': self.env.ref('real_estate.installment_product').id,
                                    'name': member.member_name,
                                    'account_id': self.env.ref(
                                        'real_estate.installment_product').property_account_income_id.id,
                                    'price_unit': (installment.amount * member.ownership) / 100,
                                    # 'tax_ids': tax_ids,
                                }))
                            elif installment.installment_type == 'balloon':
                                prod.append((0, 0, {
                                    'product_id': self.env.ref('real_estate.balloon_payment').id,
                                    'name': member.member_name,
                                    'account_id': self.env.ref(
                                        'real_estate.balloon_payment').property_account_income_id.id,
                                    'price_unit': (installment.amount * member.ownership) / 100
                                }))
                            elif installment.installment_type == 'possession_amount':
                                prod = [(0, 0, {
                                    'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                    'name': self.env.ref('real_estate.possession_amount_product').name,
                                    'account_id': self.env.ref(
                                        'real_estate.possession_amount_product').property_account_income_id.id,
                                    'price_unit': installment.amount
                                })]

                            elif installment.installment_type == 'confirmation_amount':
                                prod = [(0, 0, {
                                    'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                    'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                    'account_id': self.env.ref(
                                        'real_estate.confirmation_amount_product').property_account_income_id.id,
                                    'price_unit': installment.amount
                                })]

                            elif installment.installment_type == 'balloting_amount':
                                prod = [(0, 0, {
                                    'product_id': self.env.ref('real_estate.balloting_product').id,
                                    'name': self.env.ref('real_estate.balloting_product').name,
                                    'account_id': self.env.ref(
                                        'real_estate.balloting_product').property_account_income_id.id,
                                    'price_unit': installment.amount
                                })]
                    else:
                        if installment.installment_type == 'final':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.final_product').id,
                                'name': self.env.ref('real_estate.final_product').name,
                                'account_id': self.env.ref(
                                    'real_estate.final_product').property_account_income_id.id,
                                'price_unit': installment.amount,
                                # 'tax_ids': tax_ids,
                            })]
                        elif installment.installment_type == 'installment':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.installment_product').id,
                                'name': self.env.ref('real_estate.installment_product').name,
                                'account_id': self.env.ref(
                                    'real_estate.installment_product').property_account_income_id.id,
                                'price_unit': installment.amount,
                                # 'tax_ids': tax_ids,
                            })]
                        elif installment.installment_type == 'balloon':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.balloon_payment').id,
                                'name': self.env.ref('real_estate.balloon_payment').name,
                                'account_id': self.env.ref(
                                    'real_estate.balloon_payment').property_account_income_id.id,
                                'price_unit': installment.amount
                            })]
                        elif installment.installment_type == 'possession_amount':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                'name': self.env.ref('real_estate.possession_amount_product').name,
                                'account_id': self.env.ref(
                                    'real_estate.possession_amount_product').property_account_income_id.id,
                                'price_unit': installment.amount
                            })]
                        elif installment.installment_type == 'confirmation_amount':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                'account_id': self.env.ref(
                                    'real_estate.confirmation_amount_product').property_account_income_id.id,
                                'price_unit': installment.amount
                            })]
                        elif installment.installment_type == 'balloting_amount':
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.balloting_product').id,
                                'name': self.env.ref('real_estate.balloting_product').name,
                                'account_id': self.env.ref(
                                    'real_estate.balloting_product').property_account_income_id.id,
                                'price_unit': installment.amount
                            })]
                        else:
                            prod = []

                    done_installment = len(installment.file_id.installment_plan_ids.search([
                        ('file_id', '=', installment.file_id.id),
                        ('invoice_id', '!=', False)
                    ]))

                    invoice = self.env['account.move'].create({
                        # 'file_ids': installment.file_id.id,
                        # 'invoice_payment_ref': installment.file_id.name,
                        'partner_id': self.transferee_partner_id.partner_id.id,
                        'type': 'out_invoice',
                        'journal_id': self.env.company.account_journal_id.id,
                        'property_invoice_type': 'installment',
                        'user_id': installment.file_id.user_id.id,
                        'date': installment.date,
                        'invoice_date': installment.date,
                        'invoice_payment_term_id': installment.file_id.env.company.payment_terms_final_id.id if installment.installment_type == 'final' else False,
                    })
                    invoice.file_ids = installment.file_id.id
                    invoice.invoice_line_ids = prod

                    invoice.action_post()

                    installment.file_id.file_payment_history_id.create({
                        'invoice_id': invoice.id,
                        'file_id': installment.file_id.id
                    })

                    installment.invoice_id = invoice.id
                    print("INVOICE ID:>>>>>>>", invoice.id)

                    installment.invoice_created = True


            self.file_id.membership_id = self.transferee_partner_id
            self.file_id.state = 'available'
            self.file_id.history_log(self.t_request_id.name, 'Transfer', fields.Date.context_today(self),
                                     self.transferee_partner_id.id, self.membership_id.id)

            self.state = 'transfered'
        else:
            if self.by_pass_documents == 'yes':
                self.file_id.membership_id = False
                self.file_id.state = 'available'
                self.file_id.history_log(self.t_request_id.name, 'Transfer (Open File)', fields.Date.context_today(self),
                                         False, self.membership_id.id)

                self.state = 'transfered'
            elif self.by_pass_documents == 'no':
                if not all(docs.required_documents_line_ids.mapped('attachment')):
                    raise ValidationError('Please attach all the required documents.')
                if self.wave_transfer_fee == 'no' and self.no_of_invoices < 1:
                    raise ValidationError(_('Please create transfer fee invoice first.'))
                if self.wave_transfer_fee == 'yes' and self.wave_transfer_amount <= self.env.company.transfer_fee and self.no_of_invoices < 1:
                    raise ValidationError(_('Please create transfer fee invoice first.'))
                if not self.transfer_witness_ids:
                    raise ValidationError(_('Please add witness'))
                if not self.combine_image:
                    raise ValidationError(_('Please add combine image'))
                if self.wave_transfer_fee == 'no' and not self.payment_received:
                    raise ValidationError(_('Please pay the transfer fee to confirm transfer.'))
                self.file_id.membership_id = self.transferee_partner_id
                self.file_id.state = 'available'
                self.file_id.history_log(self.t_request_id.name, 'Transfer (Open File)', fields.Date.context_today(self),
                                         False, self.membership_id.id)

                self.state = 'transfered'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('secret_token', _('New')) == _('New'):
                vals['secret_token'] = secrets.token_hex(10)
        return super(TransferApplication, self).create(vals_list)


class TransferWitness(models.Model):
    _name = 'transfer.witness'
    _description = "Transfer Witness"

    witness_for = fields.Selection([
        ('transferor', 'Transferor'),
        ('tranferee', 'Tranferee')
    ], required=True)
    name = fields.Char(required=True)
    father_name = fields.Char(required=True)
    cnic = fields.Char(string='CNIC', required=True)
    cnic_expiry = fields.Date(string='CNIC Expiry')
    cnic_front = fields.Binary(attachment=True, string='CNIC Front')
    cnic_back = fields.Binary(attachment=True, string='CNIC Back')

    transfer_application_id = fields.Many2one('transfer.application')


class AccountMove(models.Model):
    _inherit = 'account.move'

    transfer_application_id = fields.Many2one('transfer.application')