# -*- coding: utf-8 -*-

import logging
import qrcode
import base64
from io import BytesIO
from werkzeug.urls import url_encode
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import dateutil.parser
from lxml import etree as ET
import secrets
from hashids import Hashids

_logger = logging.getLogger(__name__)



class File(models.Model):
    _name = 'file'
    _description = "File"
    _rec_name = 'tracking_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')
    state = fields.Selection([
        ('available', 'Available'),
        ('cancel', 'Cancel'),
        ('inprocess', 'Inprocess'),
        ('refund', 'Refund'),
        ('merged', 'Merged')
    ], default='available')
    file_status = fields.Selection([
        ('draft', 'Draft'),
        ('lock', 'Lock'),
        ('approve', 'Approve'),
        ('dispute', 'Legal Dispute'),
        ('cancel', 'Cancel'),
        ('merged_and_cancel', 'Merged And Cancel')
    ], default='draft', tracking=True)
    invoice_payment_type = fields.Selection([('osp', 'One Step Payment'),
                                             ('tsp', 'Two Step Payment')],
                                            default=lambda self: self.env.company.payment_type, readonly=False)

    name = fields.Char('File Number', required=True, copy=False, index=True, readonly=True,
                       default=lambda self: _('New'), tracking=True)
    active = fields.Boolean(default=True)
    tracking_id = fields.Char(required=True, copy=False, index=True, readonly=False, store=True,
                              default=lambda self: _('*'))
    booking_date = fields.Date('Booking Date', default=fields.Date.today(), tracking=True)
    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')
    ], string='Payment Type', tracking=True)
    membership_id = fields.Many2one('res.member', string='Member Name',
                                    tracking=True)
    member_company_type = fields.Selection([('person', 'Individual'),
                                            ('company', 'Company'),
                                            ('aop', 'Joint Owner')],
                                           related='membership_id.company_type', store=True)
    membership_name = fields.Char(string='Name', store=True, related='membership_id.name', tracking=True)
    user_id = fields.Many2one('res.users', "Sale Person", tracking=True)
    preference_ids = fields.One2many('preference', 'file_id', tracking=True)
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", store=True, readonly=False,
                                 tracking=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", store=True, readonly=False,
                               tracking=True)
    sector_id = fields.Many2one('sector', readonly=False, tracking=True)
    street_id = fields.Many2one('street', readonly=False, tracking=True)
    inventory_id = fields.Many2one('plot.inventory', 'Plot No', domain=lambda self: self._check_inventory_id(),
                                   tracking=True)
    unit_number = fields.Char(related='inventory_id.name', store=True, readonly=False, tracking=True)
    covered_area = fields.Integer('Covered Area', compute='_covered_area', store=True, tracking=True)
    category_id = fields.Many2one('plot.category', store=True, string='Category', readonly=False,
                                  tracking=True)
    size_id = fields.Many2one('unit.size', 'Size', related="inventory_id.size_id", readonly=False)
    standard_area = fields.Float('Total Area(sqft)', related="inventory_id.standard_area", readonly=False, store=True,
                                 tracking=True)
    unit_category_type_id = fields.Many2one('unit.category.type', related="inventory_id.unit_category_type_id",
                                            store=True, readonly=False, tracking=True)
    unit_class_id = fields.Many2one('unit.class', related="inventory_id.unit_class_id", store=True, readonly=False,
                                    tracking=True)
    price_list_id = fields.Many2one('price.list', compute='_price_list', store=True, readonly=False,
                                    tracking=True)
    kin_line_ids = fields.One2many('res.kin', 'file_id', ondelete='cascade')
    is_downpayment = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partially_paid', 'Partially Paid'),
        ('fully_paid', 'Fully Paid')
    ], compute='_compute_status')
    is_preference = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partially_paid', 'Partially Paid'),
        ('fully_paid', 'Fully Paid')
    ], compute='_compute_status')
    is_balloting = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partially_paid', 'Partially Paid'),
        ('fully_paid', 'Fully Paid')
    ], compute='_compute_status')
    construction_strat_date = fields.Date('Construction Start Date')
    completion_date = fields.Date('Completion Date', )
    completion_year = fields.Char('Completion Year')
    property_info_criteria = fields.Boolean(compute='_property_info_criteria')
    # Payment Plan
    include_installment = fields.Boolean()
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ], default='custom')
    predefine_plan_id = fields.Many2one('predefine.plan')
    installment_created = fields.Boolean(default=False)
    plan_description = fields.Char('Plan Description', store=True, readonly=False)
    interval_id = fields.Many2one(
        'payment.interval',
        'Payment Interval',
    )
    total_installment = fields.Integer(
        'No of Installment',
    )
    starting_date = fields.Date()
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', readonly=False, string="Installment Status")

    overall_status = fields.Selection([
        ('open', "Open"),
        ('close', "Close"),
    ], string="Payment Status", store=True, readonly=True, compute='_compute_overall_status', tracking=True)

    create_manually = fields.Boolean(default=False, string="Create Manually", tracking=True)
    # File Info
    file_type = fields.Selection([
        ('new', 'New'),
        ('legacy', 'Legacy')
    ], default='new')  # Added this field to import data and this field is invisible on form
    type = fields.Selection([
        ('normal', 'Normal'),
        ('gift', 'Complementary'),
        ('in_lieu', 'In Lieu'),
        ('investor', 'Investor'),
    ], default='normal')  # Added this field for actual file type
    plot_state = fields.Selection([
        ('plot', 'Plot'),
        ('possession', 'Possession'),
        ('construction', 'Construction'),
        ('house_completed', 'House Completed'),
        ('resident', 'Resident')
    ], default='plot', tracking=True)
    allow_bank_finance = fields.Boolean(related='society_id.company_id.allow_bank_finance', index=True)
    finance_by = fields.Selection([
        ('bank', 'Bank'),
        ('self', 'Self')
    ])
    sale_amount = fields.Float('Sale Amount', store=True, readonly=False, compute='_sale_amount',
                               tracking=True)  #
    custom_sale_amount = fields.Float('Sale Amount ')
    add_custom_value = fields.Boolean()
    factor_amount = fields.Float(readonly=True, store=True, compute='_sale_amount')
    ttl_sale_amount = fields.Float(
        'Total Sale Amount', readonly=False, store=True, compute='_sale_amount'
    )
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage')
    initial_calculation_basis = fields.Selection([('percentage', 'Percentage'),
                                                  ('fix', 'Fix')], default='percentage')
    balloting_calculation_basis = fields.Selection([('percentage', 'Percentage'), ('fix', 'Fix')],
                                                   default='percentage', string='Final Calculation Basis')
    discount_amount = fields.Float(store=True, readonly=False, tracking=True)
    net_sale_amount = fields.Float('Net Sale Amount', store=True, readonly=True)
    balloting_amount = fields.Float(readonly=False, tracking=True)
    balloting_amount_percentage = fields.Float(string='Final Payment Percentage', readonly=False,
                                               tracking=True)
    initial_payment = fields.Float('Initial Payment', readonly=False, tracking=True)
    initial_payment_percentage = fields.Float('Initial Payment Percentage', readonly=False, tracking=True)
    balance_amount = fields.Float('Balance Amount', compute='_compute_balance_amount', store=True, readonly=True)
    remaining_payment = fields.Float(compute='_compute_remaining_amount', store=True, readonly=False)
    balloon_payment = fields.Float()
    balloon_payment_start = fields.Integer()
    possession_amount = fields.Float()
    confirmation_amount = fields.Float()
    installment_amount = fields.Float()
    possession_amount_interval = fields.Integer()
    possession_amount_frequency = fields.Integer()
    confirmation_amount_interval = fields.Integer()
    confirmation_amount_frequency = fields.Integer()
    balloon_payment_interval = fields.Integer()
    balloon_payment_frequency = fields.Integer()
    primary_amount = fields.Float()
    primary_amount_interval = fields.Integer()
    primary_amount_frequency = fields.Integer()

    file_payment_ids = fields.One2many('file.payment', 'file_payment_plan_id', tracking=True)
    file_payment_view_ids = fields.One2many('file.payment.view', 'file_id', tracking=True)
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', tracking=True)
    manual_installment_plan_ids = fields.One2many('installment.plan', 'file_id', tracking=True)
    new_product_ids = fields.One2many('new.product.line', 'file_id', tracking=True)
    file_payment_history_id = fields.One2many('file.payment.history', 'file_id', tracking=True)
    file_request_history_ids = fields.One2many('file.request.history', 'file_id', tracking=True)
    payment_ids = fields.One2many(
        'account.payment', 'file_id',
        'Payments', required=True, tracking=True
    )
    from_member = fields.Boolean(default=False)
    from_open_file = fields.Boolean(default=False)
    token_generated = fields.Boolean(default=False)
    # payment_id = fields.One2many('payment.detail', 'file_id')
    # cancellation_id = fields.One2many('cancellation.detail', 'file_id')

    history_ids = fields.One2many('file.history', 'file_id', ondelete='cascade', tracking=True)
    joint_owner_ids = fields.One2many('joint.owner', 'file_id', ondelete='cascade', tracking=True)
    poa_ids = fields.One2many('power.attorney', 'file_id', ondelete='cascade', tracking=True)
    unit_type = fields.Selection([
        ('plot', 'Plot'),
        ('unit', 'Unit'),
    ])
    crm_id = fields.Many2one('crm.lead', tracking=True)
    token_id = fields.Many2one('token.money', tracking=True)
    allotment_no = fields.Char('Allotment No')
    letter_date = fields.Date(tracking=True)
    last_payment_date = fields.Date()
    notes = fields.Text('External Notes')
    predefined_remark_id = fields.Many2one('predefine.remarks')
    internal_notes = fields.Text('Internal Notes')
    initial_invoice = fields.Boolean(default=False)


    # next of kin from member
    kin_name = fields.Char(tracking=True, default=lambda
        l: l.membership_id.kin_name if l.membership_id.company_type == 'person' else '', store=False)
    kin_cnic = fields.Char(string='CNIC', tracking=True, default=lambda
        l: l.membership_id.kin_cnic if l.membership_id.company_type == 'person' else '', store=False)
    kin_mobile = fields.Char(string='Mobile No', tracking=True, default=lambda
        l: l.membership_id.kin_mobile if l.membership_id.company_type == 'person' else '', store=False)
    kin_member_relation = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('wife', 'Wife'),
        ('husband', 'Husband'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('other', 'Other'),
    ], string='Relation With Member', tracking=True)
    other_relation = fields.Char('Relation ', tracking=True)

    # Investor Fields
    investment_adjustment = fields.Boolean()
    investor_id = fields.Many2one('res.investor', string='Investor No')
    investment_id = fields.Many2one('investment', string='Investment No')
    investor_file = fields.Many2one('investor.file', string='Investor File')

    # Tax for all file invoices and grace period for Down Payment
    installment_tax_ids = fields.Many2many('account.tax')
    grace_period = fields.Integer()

    # pricing policy
    pricing_policy = fields.Selection([('area', 'Area Base'),
                                       ('unit_base', 'Unit Base')], related='society_id.pricing_policy', store=True)
    rate_sq_ft = fields.Float(string="Rate/Sq-ft")

    # _sql_constraints = [
    #     ('tracking_id_uniq', 'unique (tracking_id)', 'The tracking id of the file must be unique !')
    # ]

    # @api.onchange('rate_sq_ft')
    # def rate_sqft_change(self):
    #     for rec in self:
    #         if rec.rate_sq_ft and rec.pricing_policy == 'area' and rec.price_list_id.price_list_type == "sq_ft":
    #             if rec.sale_amount:
    #                 rec.sale_amount = 0
    correspondence_address = fields.Text(string='Corresponding Address')
    installment_payments = fields.One2many('file.installment.payment', 'file_id', string='Installment_payments',
                                           required=False)
    additional_payments = fields.One2many('file.additional.payment', 'file_id', string='Additional Payments',
                                          required=False)

    installment_due_count = fields.Integer(string="Installment Due Count", compute='count_due_installments', store=True)

    qr_code = fields.Binary("QR Code", compute='generate_qr_code', attachment=True, store=True)
    merger_ref = fields.Char()
    secret_token = fields.Char(string="Secret Token", required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)

    qr_hashid = fields.Char(string="Hash", readonly=True, copy=False)
    hash_salt = fields.Char(string="salt", readonly=True, copy=False)
    file_ownership_type = fields.Selection([
        ('investor', 'Investor'),
        ('land_seller', 'Land Seller'),
        ('end_user', 'End User'),
    ], default='end_user')



    # @api.model
    def assign_secret_tokens(self):
        # Fetch records that have the token as 'New' or empty
        records_with_default_token = self.search([('secret_token', '=', 'New')])
        for record in records_with_default_token:
            # Assign a new unique token if the token is still 'New'
            record.secret_token = secrets.token_hex(10)

    @api.depends('tracking_id', 'name')
    def generate_qr_code(self):
        for rec in self:
            params = ""
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            '''url_params = {
                'id': self.id,
                'view_type': 'form',
                'model': 'file',
                # 'menu_id': self.env.ref('module_name.menu_record_id').id,
                'action': self.env.ref('real_estate.action_file').id,
            }'''

            salt = secrets.token_urlsafe(16)
            hashids = Hashids(salt=salt, min_length=15)

            if isinstance(rec.id, int):  # Skip if not a saved record
                hashed_id = hashids.encode(rec.id)
                params = f'/file/verification/{hashed_id}'

                rec.qr_hashid = hashed_id
                rec.hash_salt = salt

            # params = '/file/verification/%s' % (rec.id)
            url = base_url + params
            data = (rec.tracking_id or '') + '/' + (rec.name or '')
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image

    @api.model
    def generate_qr_code_for_all(self):
        for rec in self.search([('qr_code', '=', False)]):
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )

            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            params = '/file/verification/%s' % (rec.id)
            url = base_url + params
            data = (rec.tracking_id or '') + '/' + (rec.name or '')
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image

    @api.depends('price_list_id', 'inventory_id')
    def _covered_area(self):
        for rec in self:
            rec.covered_area = 0.0
            for recs in rec.price_list_id.pricelist_line:
                if (rec.pricing_policy == 'area' and rec.price_list_id.price_list_type == 'sq_ft'
                        and not rec.inventory_id):
                    rec.covered_area = recs.area
                else:
                    rec.covered_area = rec.inventory_id.standard_area

    @api.onchange('covered_area', 'rate_sq_ft')
    def rate_sq_ft_without_unit(self):
        for rec in self:
            if not rec.inventory_id and not rec.price_list_id:
                rec.custom_sale_amount = rec.covered_area * rec.rate_sq_ft
                rec.sale_amount = rec.custom_sale_amount
                rec.ttl_sale_amount = rec.sale_amount

    @api.onchange('initial_payment_percentage', 'balloting_amount_percentage', 'net_sale_amount')
    def calculate_initial_and_balloting_amount(self):
        for rec in self:
            if (rec.plan_type == 'custom' and
                    rec.payment_type == 'installments'):
                if rec.initial_payment_percentage and rec.initial_calculation_basis == 'percentage':
                    rec.initial_payment = round(rec.net_sale_amount * (rec.initial_payment_percentage / 100))
                if rec.balloting_amount_percentage and rec.balloting_calculation_basis == 'percentage':
                    rec.balloting_amount = round(rec.net_sale_amount * (rec.balloting_amount_percentage / 100))
                if rec.initial_payment + rec.balloting_amount > rec.net_sale_amount:
                    raise ValidationError(
                        _("Total of initial and final payment amount is exceeding from net sale amount"))

    @api.onchange('initial_calculation_basis')
    def initial_make_value_zero(self):
        for rec in self:
            if rec.initial_calculation_basis:
                rec.initial_payment_percentage = 0.00
                rec.initial_payment = 0.00

    @api.onchange('balloting_calculation_basis')
    def balloting_make_value_zero(self):
        for rec in self:
            if rec.balloting_calculation_basis:
                rec.balloting_amount_percentage = 0.00
                rec.balloting_amount = 0.00

    @api.onchange('plan_type', 'predefine_plan_id')
    def onchange_plan_type(self):
        for rec in self:
            # Reset payment fields every time plan changes to avoid stale values
            rec.initial_payment = 0.0
            rec.balloting_amount = 0.0
            rec.balloon_payment = 0.0
            rec.possession_amount = 0.0
            rec.confirmation_amount = 0.0
            rec.r = 0.0
            rec.installment_amount = 0.0
            if rec.plan_type == 'predefine' and rec.predefine_plan_id:
                rec.plan_description = rec.predefine_plan_id.name
                rec.interval_id = rec.predefine_plan_id.interval_id.id
                rec.total_installment = rec.predefine_plan_id.total_installment
        # Recompute payment amounts from plan lines using existing logic
        self._balloon_payment()

    @api.onchange('membership_id')
    def _onchange_membership_id_tracking_id(self):
        # Tracking ID otherwise defaults to '*' and only gets a real value
        # from an ir.sequence at create() time — showing the Member Number
        # here as soon as a Member is picked gives it a meaningful value
        # immediately, and create()'s sequence fallback only fires when this
        # is still '*', so it won't be overwritten afterward.
        if self.membership_id:
            self.tracking_id = self.membership_id.ref

    @api.onchange('inventory_id')
    def _onchange_inventory(self):
        self.preference_ids.unlink()

        if self.inventory_id:
            self.category_id = self.inventory_id.category_id.id
            self.unit_category_type_id = self.inventory_id.unit_category_type_id.id
            self.street_id = self.inventory_id.street_id.id

        if self.inventory_id.preference_factor_ids and not self.token_id:
            self.preference_ids = [(0, 0, {
                'factor_id': rec.id,
                'basis': 'percentage',
                'value': rec.percentage,
            }) for rec in self.inventory_id.preference_factor_ids]

        if self.price_list_id.price_list_type == 'sq_ft' and self.pricing_policy == 'area' and self.inventory_id:
            self.rate_sq_ft = False

        # Force Price List / Sale Amount to re-evaluate right away — don't
        # rely on the framework's automatic depends-cascade alone, since
        # unit_category_type_id/category_id above are set as side effects
        # within this same onchange rather than by the user directly.
        self._price_list()
        self._sale_amount()

    @api.onchange('price_list_id')
    def _onchange_price_list_id(self):
        # Covers a manual Price List change too, same reasoning as above.
        self._sale_amount()

    @api.onchange('manual_installment_plan_ids')
    def _sale_amount_manually_cal(self):
        serial_number = 1
        for rec in self.manual_installment_plan_ids:
            rec.installment_number = serial_number
            if not rec.line_calculated:
                rec.percentage = 100 - sum(
                    [x.percentage for x in self.manual_installment_plan_ids if x.line_calculated] +
                    [x.value for x in self.file_payment_ids if self.file_payment_ids.payment_type == 'percentage'])
                rec.line_calculated = True

                # total_amount = sum(self.manual_installment_plan_ids.mapped('amount_manual'))
                # if total_amount > self.net_sale_amount:
                #     raise ValidationError('Amount cannot exceed Net Sale Amount')
            serial_number = serial_number + 1

    @api.onchange('predefine_plan_id', 'custom_sale_amount', 'sale_amount')
    def _balloon_payment(self):
        for recs in self:
            if recs.predefine_plan_id:
                # for setting the starting date of installment plan after confirmation
                if recs.env.ref('real_estate.confirmation_amount_product').id \
                        in recs.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                    recs.starting_date = recs.booking_date + \
                                         relativedelta(months=+recs.predefine_plan_id.confirmation_amount_period + 1)
                for pre_plan in recs.predefine_plan_id.predefine_plan_line_ids:

                    if recs.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                        recs.initial_payment = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if recs.env.ref('real_estate.installment_product').id == pre_plan.product_id.id:
                        recs.installment_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if recs.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                        recs.balloting_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if recs.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                        recs.balloon_payment = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.balloon_payment_interval = pre_plan.interval
                        recs.balloon_payment_frequency = pre_plan.frequency
                        recs.balloon_payment_start = pre_plan.start_from
                        recs.include_installment = pre_plan.include_installment

                    if recs.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                        recs.possession_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.possession_amount_interval = pre_plan.interval
                        recs.possession_amount_frequency = pre_plan.frequency

                    if recs.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                        recs.confirmation_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.confirmation_amount_interval = pre_plan.interval
                        recs.confirmation_amount_frequency = pre_plan.frequency

                    if recs.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                        recs.primary_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.primary_amount_interval = pre_plan.interval
                        recs.primary_amount_frequency = pre_plan.frequency

    @api.onchange('sale_amount')
    def _factor_update(self):
        for rec in self.preference_ids:
            rec._compute_total_value()

    @api.onchange('society_id', 'phase_id', 'street_id', 'category_id', 'unit_category_type_id', 'sector_id')
    def _phase_domain(self):
        # Clear a stale Unit only if it no longer belongs to the newly
        # picked Street — guarded (not unconditional) because this onchange
        # also re-fires when _onchange_inventory sets self.street_id to
        # match a just-picked Unit; in that case they already match, so
        # nothing gets cleared and the Unit selection isn't undone.
        if self.inventory_id and self.street_id and self.inventory_id.street_id != self.street_id:
            self.inventory_id = False
            # Force these to re-evaluate right away against the now-cleared
            # Unit, rather than relying on the automatic depends-cascade.
            self._price_list()
            self._sale_amount()
        inventory_domain = []
        state_domain = [('state', '=', 'reserved')] if self.crm_id or self.token_id else \
            [('state', '=', 'avalible_for_sale')]
        if all([self.society_id, self.phase_id, self.category_id, self.unit_category_type_id]):
            inventory_domain = inventory_domain + [
                ('society_id', '=', self.society_id.id),
                ('phase_id', '=', self.phase_id.id),
                ('sector_id', '=', self.sector_id.id),
            ]

        if not inventory_domain:
            inventory_domain.append(('id', '=', False))
        if self.street_id:
            return {
                'domain': {'inventory_id': [('street_id', '=', self.street_id.id), ('state', '=', 'avalible_for_sale')]}
            }
        else:
            return {'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'inventory_id': inventory_domain + state_domain
            }
            }

    def lock(self):
        self.file_status = 'lock'
        self.inventory_id.state = 'sold'
        if not self.installment_plan_ids and self.payment_type != 'lump_sum' and self.balance_amount != 0:
            raise ValidationError("Please create installment plan first.")

    def approve(self):
        if self.no_of_invoices < 1 and self.type == 'normal':
            raise ValidationError("Please generate initial invoice first.")
        if self.payment_states == 'draft':
            raise ValidationError("Please pay the down payment invoice.")
        self.file_status = 'approve'


    def bulk_file_approve(self):
        active_ids = self._context.get('active_ids')
        files = self.env['file'].browse(active_ids)
        for file in files:
            if not file.no_of_invoices < 1 and not file.type == 'normal' and not file.payment_states == 'draft':
                file.file_status = 'approve'



    # this function calculates the total due amount of a member

    def _compute_residual_amount(self, p_partner, p_file):

        v_amount = sum(self.env['account.move'].search([('partner_id', '=', p_partner),
                                                        ('name', '=', p_file)]).mapped('amount_residual'))
        return v_amount

    # this function calculates the total paid amount of a member

    def _compute_paid_amount(self, p_partner, p_file):

        v_amount_paid = sum(self.env['account.move'].search([('partner_id', '=', p_partner),
                                                             ('name', '=', p_file)]).mapped('amount_total'))
        return v_amount_paid

    @api.model
    def _product_income_account(self, product):
        """Return the income account for a product, falling back to category then first income account."""
        if product and product._name == 'product.realestate':
            product = product.product_id
        if not product:
            return self.env['account.account'].search(
                [('account_type', 'in', ('income', 'income_other')),
                 ('company_ids', 'in', self.env.company.ids)], limit=1)
        account = product.property_account_income_id
        if not account:
            account = product.categ_id.property_account_income_categ_id
        if not account:
            account = self.env['account.account'].search(
                [('account_type', 'in', ('income', 'income_other')),
                 ('company_ids', 'in', self.env.company.ids)], limit=1)
        return account

    @api.model
    def _product_expense_account(self, product):
        """Return the expense account for a product, falling back to category then first expense account."""
        account = product.property_account_expense_id
        if not account:
            account = product.categ_id.property_account_expense_categ_id
        if not account:
            account = self.env['account.account'].search(
                [('account_type', 'in', ('expense', 'expense_depreciation')),
                 ('company_ids', 'in', self.env.company.ids)], limit=1)
        return account

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Member Invoices'),
            'res_model': 'account.move',
            'domain': [('file_ids', '=', self.id), ('partner_id', '=', self.membership_id.partner_id.id)],
            'context': {'default_name': self.name, 'default_partner_id': self.membership_id.partner_id.id,
                        'current_view': 'realestate'},
        }

    def open_other_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Other Invoices'),
            'res_model': 'account.move',
            'domain': [('property_invoice_type', 'not in', ('initial_payment', 'installment')),
                       ('file_ids', '=', self.id)],
            'context': {'default_name': self.name, 'default_partner_id': self.membership_id.partner_id.id,
                        'current_view': 'realestate'},
        }

    def _compute_no_of_invoices(self):
        for rec in self:
            rec.no_of_invoices = len(
                rec.env['account.move'].search([('file_ids', '=', rec.id), ('partner_id', '=', rec.membership_id.partner_id.id)]))

    @api.depends('installment_plan_ids.residual')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_payment = sum(rec.installment_plan_ids.mapped('residual'))

    def reset_installment_plan(self):
        if len(self.installment_plan_ids.mapped('invoice_id').ids) > 1:
            raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        self.installment_plan_ids.unlink()
        self.installment_created = False

    def create_installment_plan(self):
        # balance_amount only recomputes when net_sale_amount/initial_payment/
        # balloting_amount actually change; force it fresh here so a plan
        # regenerated after those were fixed elsewhere (e.g. Sale Amount was
        # corrected) doesn't build off a stale stored value.
        self._compute_balance_amount()
        if self.balance_amount == 0 and self.balloting_amount == 0:
            raise ValidationError('You cannot create plan with zero "Balance Amount".')

        # Clear existing non-invoiced installment lines before regenerating
        existing = self.installment_plan_ids.filtered(lambda l: not l.invoice_created)
        if existing:
            existing.unlink()
        self.installment_created = False

        if all([self.starting_date, self.interval_id, self.total_installment, self.net_sale_amount]) and self.active:
            dates = [fields.Date.from_string(self.starting_date)]

            if self.installment_tax_ids:
                tax_id = self.installment_tax_ids
            else:
                tax_id = self.env.company.installment_tax_ids

            interval = 0
            possession_interval = 0
            confirmation_interval = 0
            primary_interval = 0
            start_balloon_payment = False
            installment_count = 1
            balloon_interval = self.balloon_payment_interval
            # when start_from is 0, first balloon fires at the first interval
            balloon_start = self.balloon_payment_start or self.balloon_payment_interval

            # Running pool left for the regular monthly "Installment" lines
            # once Booking/Confirmation/Balloon/Possession/Balloting are
            # carved out — kept in a local var, NOT written back to
            # self.balance_amount (a stored compute field that must keep
            # reflecting the file's true outstanding balance, not this
            # scratch total).
            working_balance = self.balance_amount

            if self.predefine_plan_id:
                for rec in self.predefine_plan_id.predefine_plan_line_ids:
                    if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
                        interval_limit = round(self.total_installment / self.balloon_payment_interval)
                        deduction = self.balloon_payment * self.balloon_payment_frequency
                        if deduction > working_balance:
                            raise ValidationError(_(
                                'Balloon Payment in plan "%s" results in an amount (%.2f) larger than the '
                                'remaining Balance Amount (%.2f). Please correct the Balloon Payment percentage/'
                                'value on that plan line.') % (self.predefine_plan_id.name, deduction, working_balance))
                        working_balance = working_balance - deduction
                    if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
                        deduction = self.possession_amount * self.possession_amount_frequency
                        if deduction > working_balance:
                            raise ValidationError(_(
                                'Possession Amount in plan "%s" results in an amount (%.2f) larger than the '
                                'remaining Balance Amount (%.2f). Please correct the Possession Amount percentage/'
                                'value on that plan line.') % (self.predefine_plan_id.name, deduction, working_balance))
                        working_balance = working_balance - deduction
                    if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
                        deduction = self.confirmation_amount * self.confirmation_amount_frequency
                        if deduction > working_balance:
                            raise ValidationError(_(
                                'Confirmation Amount in plan "%s" results in an amount (%.2f) larger than the '
                                'remaining Balance Amount (%.2f). Please correct the Confirmation Amount percentage/'
                                'value on that plan line.') % (self.predefine_plan_id.name, deduction, working_balance))
                        working_balance = working_balance - deduction
                    if rec.product_id.id == rec.env.ref('real_estate.balloting_product').id:
                        deduction = self.primary_amount * self.primary_amount_frequency
                        if deduction > working_balance:
                            raise ValidationError(_(
                                'Balloting Amount in plan "%s" results in an amount (%.2f) larger than the '
                                'remaining Balance Amount (%.2f). Please correct the Balloting Amount percentage/'
                                'value on that plan line.') % (self.predefine_plan_id.name, deduction, working_balance))
                        working_balance = working_balance - deduction
                if self.predefine_plan_id.include_in_plan == 'no':
                    for rec in range(1, (self.total_installment + self.balloon_payment_frequency +
                                         self.possession_amount_frequency + self.primary_amount_frequency)):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
            else:
                if self.investment_id:

                    dates = [fields.Date.from_string(
                        self.installment_plan_ids.filtered(lambda l: l.invoice_created)[-1].date + relativedelta(
                            months=+self.interval_id.nom))]

                    for rec in range(1, self.investment_id.remaining_installments):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

            balance = working_balance
            amount = 0

            if self.initial_payment and self.type == 'normal':
                booking_tax = round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else 0
                booking_total = self.initial_payment + booking_tax
                # a token already paid is an advance against the Booking installment,
                # same as investment.receive_payment() nets it off the Deal's first
                # plan line - credit it here so the Booking line shows the true
                # outstanding amount instead of the full price on top of the token.
                token_amount = 0.0
                if self.token_id and self.token_id.token_paid:
                    token_amount = min(self.token_id.token_fees, booking_total)
                self.installment_plan_ids.create({
                    'date': self.booking_date + relativedelta(days=+self.grace_period),
                    'installment_type': 'down',
                    'installment_name': 'Booking',
                    'installment_number': 1,
                    'amount': self.initial_payment,
                    'tax_amount': booking_tax,
                    'amount_paid': token_amount,
                    'residual': max(booking_total - token_amount, 0.0),
                    'payment_status': 'paid' if token_amount and token_amount >= booking_total else (
                        'in_payment' if token_amount else 'not_paid'),
                    'file_id': self.id
                })

            if (self.plan_type == 'predefine'
                    and self.env.ref('real_estate.confirmation_amount_product').id
                    in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                installment_number = 3
                if confirmation_interval < self.confirmation_amount_frequency:
                    self.installment_plan_ids.create({
                        'date': self.booking_date + relativedelta(
                            months=+self.predefine_plan_id.confirmation_amount_period),
                        'installment_number': 2,
                        'installment_type': 'confirmation_amount',
                        'installment_name': 'Confirmation',
                        'payment_status': 'not_paid',
                        'amount': self.confirmation_amount,
                        'tax_amount': round((self.confirmation_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                        'residual': self.confirmation_amount + round(
                            (self.confirmation_amount * tax_id[0].amount) / 100,
                            2) if tax_id else self.confirmation_amount,
                        'file_id': self.id
                    })
                    confirmation_interval += 1
            else:
                installment_number = 2

            # balloons replace installment slots only when the plan treats them as
            # installments; treated as balloons they come on top of the regular ones
            balloon_uses_slots = (not self.include_installment and self.predefine_plan_id
                                  and self.predefine_plan_id.include_in_plan == 'yes'
                                  and self.predefine_plan_id.treat_balloon_as == 'installment')
            installment_amount = round(working_balance / (
                    self.total_installment - self.balloon_payment_frequency)) if balloon_uses_slots else round(
                working_balance / self.total_installment)

            expected_installments = self.total_installment

            def _pending_plan_events():
                # balloon/possession/balloting lines whose slot falls beyond the
                # generated dates still have to be scheduled
                if self.plan_type != 'predefine' or not self.predefine_plan_id:
                    return False
                plan_products = self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids
                if (self.env.ref('real_estate.balloon_payment').id in plan_products
                        and interval < self.balloon_payment_frequency):
                    return True
                if (self.env.ref('real_estate.possession_amount_product').id in plan_products
                        and possession_interval < self.possession_amount_frequency):
                    return True
                if (self.env.ref('real_estate.balloting_product').id in plan_products
                        and primary_interval < self.primary_amount_frequency):
                    return True
                return False

            date_index = 0
            while date_index < len(dates) or (_pending_plan_events()
                                              and len(dates) < self.total_installment + 120):
                if date_index >= len(dates):
                    dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                rec = dates[date_index]
                date_index += 1
                # first balloon payment
                if self.balloon_payment_frequency and not start_balloon_payment:
                    if installment_number == balloon_start:
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.installment_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'balloon',
                            'installment_name': 'Installment' + ' ' + str(installment_count) if
                            self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                            'payment_status': 'not_paid',
                            'residual': amount + installment_amount if self.include_installment else amount,
                            'amount': amount + installment_amount if self.include_installment else amount,
                            'file_id': self.id
                        })
                        if self.predefine_plan_id.treat_balloon_as == 'installment':
                            installment_count += 1
                        interval = interval + 1
                        balloon_interval += balloon_start
                        start_balloon_payment = True
                        installment_number = installment_number + 1
                        continue
                # for recs in self.predefine_plan_id.predefine_plan_line_ids:
                if (self.plan_type == 'predefine'
                        and self.env.ref('real_estate.possession_amount_product').id
                        in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                    try:
                        installment_number % self.possession_amount_interval == 0
                    except Exception as e:
                        raise ValidationError(_('%s Possession Interval should be greater than 0:' % (e)))
                    else:
                        if installment_number % self.possession_amount_interval == 0 \
                                and possession_interval < self.possession_amount_frequency:
                            if balance:
                                amount = self.possession_amount if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.installment_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'possession_amount',
                                'installment_name': 'Possession',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'file_id': self.id
                            })
                            possession_interval += 1
                            installment_number = installment_number + 1
                            continue

                if (self.plan_type == 'predefine'
                        and self.env.ref('real_estate.balloting_product').id
                        in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                    try:
                        installment_number % self.primary_amount_interval == 0
                    except Exception as e:
                        raise ValidationError(_('%s Balloting Interval should be greater than 0:' % (e)))
                    else:
                        if installment_number % self.primary_amount_interval == 0 \
                                and primary_interval < self.primary_amount_frequency:
                            if balance:
                                amount = self.primary_amount if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.installment_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloting_amount',
                                'installment_name': 'Balloting',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'file_id': self.id
                            })
                            primary_interval += 1
                            installment_number = installment_number + 1
                            continue
                if (self.plan_type == 'predefine' and self.env.ref(
                        'real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped(
                    'product_id').ids and (installment_number % balloon_interval == 0
                                           and interval < self.balloon_payment_frequency and start_balloon_payment)):
                    # if installment_number % balloon_interval != 0 or interval >= self.balloon_payment_frequency:
                    #     print(rec)
                    #     if balance > 0:
                    #         amount = installment_amount if balance > installment_amount else balance
                    #     else:
                    #         amount = 0
                    #
                    #     self.installment_plan_ids.create({
                    #         'date': rec,
                    #         'installment_number': installment_number,
                    #         'installment_name': 'Installment' + ' '+str(installment_count),
                    #         'amount': amount,
                    #         'tax_amount': round((amount * tax_id[0].amount) / 100,2) if tax_id else 0,
                    #         'residual': amount + round((amount * tax_id[0].amount) / 100,2) if tax_id else amount,
                    #         'payment_status': 'not_paid',
                    #         'file_id': self.id
                    #     })
                    #     installment_count += 1
                    #     installment_number = installment_number + 1
                    #     continue

                    if balance:
                        amount = self.balloon_payment if balance > installment_amount else balance
                    else:
                        amount = 0
                    self.installment_plan_ids.create({
                        'date': rec,
                        'installment_number': installment_number,
                        'installment_type': 'balloon',
                        'installment_name': 'Installment' + ' ' + str(installment_count) if
                        self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                        'payment_status': 'not_paid',
                        'residual': amount + installment_amount if self.include_installment else amount,
                        'amount': amount + installment_amount if self.include_installment else amount,
                        'file_id': self.id
                    })
                    if self.predefine_plan_id.treat_balloon_as == 'installment':
                        installment_count += 1
                    interval = interval + 1
                    balloon_interval += self.balloon_payment_interval
                    installment_number = installment_number + 1
                    continue
                elif self.plan_type == 'custom' and not self.investment_id:
                    self.installment_plan_ids.create({
                        'date': rec,
                        'installment_number': installment_number,
                        'installment_type': 'installment',
                        'installment_name': 'Installment' + ' ' + str(installment_count),
                        'payment_status': 'not_paid',
                        'amount': installment_amount,
                        'tax_amount': round((installment_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                        'residual': installment_amount + round((installment_amount * tax_id[0].amount) / 100,
                                                               2) if tax_id else installment_amount,
                        'file_id': self.id
                    })
                    installment_count += 1
                    installment_number = installment_number + 1
                elif self.investment_id:
                    if self.investment_id.options == 'down' and self.investment_id.remaining_installments > 0:
                        installment_number = self.installment_plan_ids[-1].installment_number + 1
                        paid_installments = (
                                                    self.total_installment - self.investment_id.remaining_installments) * round(
                            working_balance / self.total_installment)
                        amount = round(
                            (working_balance - paid_installments) / self.investment_id.remaining_installments)
                        self.installment_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' ' + str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': amount,
                            'tax_amount': round((amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                            'residual': amount + round((amount * tax_id[0].amount) / 100, 2) if tax_id else amount,
                            'file_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                else:
                    if self.plan_type == 'predefine' and installment_count > expected_installments:
                        # all regular installment slots are filled; keep the slot
                        # numbering moving so later balloon/possession slots land
                        # on their configured positions
                        installment_number = installment_number + 1
                        continue
                    self.installment_plan_ids.create({
                        'date': rec,
                        'installment_number': installment_number,
                        'installment_type': 'installment',
                        'installment_name': 'Installment' + ' ' + str(installment_count),
                        'payment_status': 'not_paid',
                        'amount': installment_amount,
                        'tax_amount': round((installment_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                        'residual': installment_amount + round((installment_amount * tax_id[0].amount) / 100,
                                                               2) if tax_id else installment_amount,
                        'file_id': self.id
                    })
                    installment_count += 1
                    installment_number = installment_number + 1

            plan = self.env['installment.plan'].search([('file_id', '=', self.id)])
            if self.balloting_amount:
                plan.create({
                    'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                    'installment_type': 'final',
                    'installment_name': 'Final',
                    'payment_status': 'not_paid',
                    'installment_number': installment_number,
                    'amount': self.balloting_amount,
                    'tax_amount': round((self.balloting_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                    'residual': self.balloting_amount + round((self.balloting_amount * tax_id[0].amount) / 100,
                                                              2) if tax_id else self.balloting_amount,
                    'file_id': self.id
                })

            total = sum(self.installment_plan_ids.mapped('amount'))
            if not self.type == 'investor':
                last_line = self.installment_plan_ids[-1]
                if total < self.net_sale_amount:
                    price = self.net_sale_amount - total
                    last_line.update({
                        'amount': last_line.amount + price,
                        'residual': last_line.residual + price
                    })
                elif total > self.net_sale_amount:
                    price = total - self.net_sale_amount
                    last_line.update({
                        'amount': last_line.amount - price,
                        'residual': last_line.residual - price
                    })

            self.installment_created = True

        else:
            raise ValidationError(
                _("Installment Starting Date,Interval and total installments sould be there for active files"))

    def history_log(self, ref_number, transection, date, new_member_id, ex_member_id):

        self.history_ids.create({
            'ref_number': ref_number,
            'name': transection,
            'transaction_date': date,
            'new_member_id': new_member_id,
            'ex_member_id': ex_member_id,
            'file_id': self.id,
        })

    def check_duplicity(self, products):
        list_of_product_id = [x.product_id.id for x in products if
                              x.product_id.id != self.env.ref('real_estate.installment_product').id]
        for i in list_of_product_id:
            if list_of_product_id.count(i) > 1:
                raise ValidationError(_("Duplicity of products are not allowed"))

    def generate_invoice(self):
        if self.token_id and not self.token_id.token_paid:
            raise ValidationError(_('Please pay fees against this Token: %s . ') % (self.token_id.serial_number))
        down_payment = self.env.ref('real_estate.downpayment_product')
        token_adjustment = self.env.ref('real_estate.token_adjustment')
        lump_sum = self.env.ref('real_estate.lump_sum_product')
        data = []

        if self.payment_type == 'lump_sum':
            amount = self.net_sale_amount
            total = self.net_sale_amount
            product = lump_sum.id
        elif self.create_manually and self.manual_installment_plan_ids[0].product_id == down_payment:
            amount = self.manual_installment_plan_ids[0].amount_manual
            total = self.manual_installment_plan_ids[0].amount_manual
            product = down_payment.id
        else:
            amount = self.initial_payment
            total = self.initial_payment
            product = down_payment.id
        data.append((0, 0, {
            'product_id': product,
            'total': total,
            'initial_payment': amount,
        }))

        if self.token_id:
            data.append((0, 0, {
                'product_id': token_adjustment.id,
                'total': -self.token_id.token_fees,
                'initial_payment': -self.token_id.token_fees,
            }))

        context = {
            'default_invoice_line': data,
            'default_file_id': self.id,
            'default_membership_id': self.membership_id.id,
            'default_payment_type': self.invoice_payment_type,
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

    def _create_inv(self, prod):
        invoice = self.env['account.move'].create({
            # 'file_ids': self.id,
            # this id is just for invoice create method i will extract this field from there and push remaining values
            # 'invoice_payment_ref': self.name,
            'move_type': 'out_invoice',
            'user_id': self.user_id.id,
            'partner_id': self.membership_id.partner_id.id,
            # 'account_id': self.membership_id.property_account_receivable_id.id,
            'property_invoice_type': 'initial_payment',
            'date': self.booking_date,
            'invoice_date': self.booking_date,
            # 'invoice_date_due': self.booking_date,
            'invoice_line_ids': prod
        })
        invoice.file_ids = self.id
        invoice.action_post()

        self.payment_states = 'open'
        self.inventory_id.state = 'sold'

        self.history_log(invoice.name, 'First Owner', invoice.create_date, self.membership_id.id,
                         self.env.user.company_id.partner_id.id)
        self.initial_invoice = False
        self.env['confirmation'].confirmation_popup('Invoice')

        return invoice

    def create_invoice(self):
        if self.create_manually:
            # check duplicity
            self.check_duplicity(self.manual_installment_plan_ids)
            if self.manual_installment_plan_ids:
                prod = [(0, 0, {
                    'product_id': rec.product_id.product_id.id,
                    'name': rec.product_id.name,
                    'account_id': self._product_income_account(rec.product_id).id,
                    'price_unit': rec.amount_manual,
                    # 'is_fully_paid': rec.is_fully_paid
                }) for rec in self.manual_installment_plan_ids if rec.product_id.id != self.env.ref(
                    'real_estate.installment_product').id and rec.product_id.id != self.env.ref(
                    'real_estate.final_product').id]

                invoice = self._create_inv(prod)

                for installment in self.manual_installment_plan_ids:
                    if installment.product_id.id != self.env.ref(
                            'real_estate.installment_product').id and installment.product_id.id != self.env.ref(
                        'real_estate.final_product').id:
                        installment.invoice_id = invoice.id
                        installment.invoice_created = True
        else:
            # check duplicity
            self.check_duplicity(self.file_payment_ids)
            down_payment = self.env.ref('real_estate.downpayment_product')
            if self.initial_payment:
                prod = [(0, 0, {
                    'product_id': down_payment.product_id.id,
                    'name': down_payment.name,
                    'account_id': self._product_income_account(down_payment).id,
                    'price_unit': self.initial_payment,
                    # 'is_fully_paid': rec.is_fully_paid
                })]
                self._create_inv(prod)
        
        return True

    @api.depends('payment_states', 'installment_plan_ids')
    def _compute_overall_status(self):
        for rec in self:
            if rec.installment_plan_ids and rec.payment_states == 'close':
                if rec.installment_plan_ids.search_count(
                        [('file_id', '=', rec.id), ('payment_status', '=', 'paid')]) == len(rec.installment_plan_ids):
                    rec.overall_status = 'close'
                else:
                    rec.overall_status = 'open'
            else:
                rec.overall_status = 'open'

    @api.model
    def compute_overall_status_all_files(self):
        files = self.search([])
        print("Total Files", len(files))
        for rec in files:
            if rec.installment_plan_ids and rec.payment_states in ('open', 'close'):
                if rec.installment_plan_ids.search_count(
                        [('file_id', '=', rec.id), ('payment_status', '=', 'paid')]) == len(rec.installment_plan_ids):
                    rec.overall_status = 'close'
                    rec.payment_states = 'close'
                    print("FILE>>>>> %s  overall status closed and payment status closed." % (rec))
                else:
                    rec.overall_status = 'open'
                    print("FILE>>>>> %s status open." % (rec))
            else:
                print("NOT UPDATING ANY STATUS OF FILE %s" % (rec))

    @api.depends('society_id', 'phase_id', 'category_id', 'unit_category_type_id', 'sector_id')
    def _property_info_criteria(self):
        if all([self.society_id, self.phase_id, self.category_id, self.unit_category_type_id, self.sector_id]):
            self.property_info_criteria = True
        else:
            self.property_info_criteria = False

    @api.depends('net_sale_amount')
    def _compute_balloting_amount(self):
        self.balloting_amount = round(
            self.net_sale_amount * (self.env.company.balloting_percentage / 100))

    @api.depends('file_payment_history_id')
    def _compute_status(self):
        for rec in self:
            rec.is_balloting = 'not_paid'
            rec.is_downpayment = 'not_paid'
            rec.is_preference = 'not_paid'
            # invoices = self.env['account.move'].search([
            #     ('name', '=', rec.name),
            #     ('state', '=', 'paid'),
            #     ])

            # total_downpayment = rec.file_payment_ids.search([
            #     ('file_payment_plan_id', '=', rec.id),
            #     ('product_id', '=', self.env.ref('real_estate.downpayment_product').id),
            #     ]).total

            # total_paid_downpayment = sum(invoices.mapped('invoice_line_ids').search([
            #     ('invoice_id', 'in', invoices.mapped('id')),
            #     ('product_id', '=', self.env.ref('real_estate.downpayment_product').id),
            #     ]).mapped('price_unit'))

            # if total_downpayment > total_paid_downpayment:
            #     rec.is_downpayment = 'partially_paid'

            # if total_downpayment == total_paid_downpayment:
            #     rec.is_downpayment = 'fully_paid'

            # total_preference = rec.file_payment_ids.search([
            #     ('file_payment_plan_id', '=', rec.id),
            #     ('product_id', '=', self.env.ref('real_estate.preferences_product').id),
            #     ]).total

            # total_paid_preference = sum(invoices.mapped('invoice_line_ids').search([
            #     ('invoice_id', 'in', invoices.mapped('id')),
            #     ('product_id', '=', self.env.ref('real_estate.preferences_product').id),
            #     ]).mapped('price_unit'))

            # if total_preference > total_paid_preference:
            #     rec.is_preference = 'partially_paid'

            # if total_preference == total_paid_preference:
            #     rec.is_preference = 'fully_paid'

            # total_balloting = rec.file_payment_ids.search([
            #     ('file_payment_plan_id', '=', rec.id),
            #     ('product_id', '=', self.env.ref('real_estate.balloting_product').id),
            #     ]).total

            # total_paid_balloting = sum(invoices.mapped('invoice_line_ids').search([
            #     ('invoice_id', 'in', invoices.mapped('id')),
            #     ('product_id', '=', self.env.ref('real_estate.balloting_product').id),
            #     ]).mapped('price_unit'))

            # if total_balloting > total_paid_balloting:
            #     rec.is_balloting = 'partially_paid'

            # if total_balloting == total_paid_balloting:
            #     rec.is_balloting = 'fully_paid'

    @api.depends('file_payment_ids')
    def _compute_initial_amount(self):

        self.initial_payment = round(
            sum(val.total for val in self.file_payment_ids if val.product_id.is_include_net_amount))

    @api.depends('net_sale_amount', 'initial_payment', 'balloting_amount', 'confirmation_amount',
                 'confirmation_amount_frequency')
    def _compute_balance_amount(self):
        amount = 0
        add_ballotting = False

        # for rec in self.file_payment_ids:
        #
        #     if rec.product_id.id == self.env.ref('real_estate.balloting_product').id:
        #         add_ballotting = True
        #
        #     if rec.product_id.is_include_net_amount:
        #         if rec.payment_type == 'fix':
        #             amount = amount + rec.value
        #         else:
        #             amount = amount + [self.sale_amount * rec.value / 100][0]
        for rec in self:
            # Confirmation is carved out of the sale price same as Booking/Balloting
            # (create_installment_plan()'s working_balance already deducts it before
            # sizing the regular installments) - Balance Amount was missing this
            # carve-out, so it overstated what's actually left once Confirmation
            # is invoiced.
            confirmation_total = rec.confirmation_amount * rec.confirmation_amount_frequency
            rec.balance_amount = round(
                rec.net_sale_amount - rec.initial_payment - rec.balloting_amount - confirmation_total)
        # if self.balance_amount and self.balance_amount < 0:
        #     raise ValidationError('Balance Amount cannot be less than zero')

    @api.constrains('balance_amount')
    def _check_balance_amount(self):
        for rec in self:
            if rec.balance_amount and rec.balance_amount < 0:
                raise ValidationError('Balance Amount cannot be less than zero')

    @api.onchange('discount_amount', 'discount_type', 'ttl_sale_amount')
    def _net_sale_amount(self):
        for rec in self:
            rec.net_sale_amount = rec.ttl_sale_amount - [round(
                (
                        rec.ttl_sale_amount * rec.discount_amount) / 100) if rec.discount_type == 'percentage' else rec.discount_amount][
                0]

    @api.depends('society_id', 'phase_id', 'category_id', 'unit_category_type_id',
                 'inventory_id', 'preference_ids', 'price_list_id', 'custom_sale_amount', 'add_custom_value',
                 'factor_amount', 'sale_amount', 'rate_sq_ft')
    def _sale_amount(self):

        for recs in self:
            if recs.add_custom_value:
                if recs.covered_area and recs.rate_sq_ft:
                    recs.custom_sale_amount = recs.covered_area * recs.rate_sq_ft
                    recs.sale_amount = recs.custom_sale_amount
                    recs.ttl_sale_amount = recs.sale_amount
                elif recs.custom_sale_amount:
                    recs.sale_amount = recs.custom_sale_amount
                    recs.ttl_sale_amount = recs.custom_sale_amount
                factor = 0
                for rec in recs.preference_ids:
                    if rec.approved and rec.basis == 'fix':
                        factor = factor + rec.value
                        if recs.ttl_sale_amount:
                            recs.ttl_sale_amount = recs.ttl_sale_amount + factor
                    if rec.approved and rec.basis == 'percentage':
                        factor = factor + (recs.custom_sale_amount * rec.value) / 100
                        if recs.ttl_sale_amount:
                            recs.ttl_sale_amount = recs.ttl_sale_amount + factor
                        else:
                            recs.ttl_sale_amount = recs.custom_sale_amount + factor
                    else:
                        recs.ttl_sale_amount = recs.ttl_sale_amount
                    if recs.crm_id or recs.token_id:
                        factor = factor + (recs.custom_sale_amount * rec.value) / 100
                        if recs.ttl_sale_amount:
                            recs.ttl_sale_amount = recs.ttl_sale_amount
                        else:
                            recs.ttl_sale_amount = recs.custom_sale_amount + factor
                        rec.total = factor
                recs.factor_amount = factor
            else:
                if recs.price_list_id:
                    # Reset before re-matching so switching to a Unit/Product
                    # with no matching price list line doesn't leave the
                    # previous selection's price lingering, and track the
                    # match locally (NOT via recs.sale_amount) so a match
                    # found on an earlier line — or a stale stored value from
                    # a previous compute — never blocks re-evaluating against
                    # the currently selected Unit/Product.
                    recs.sale_amount = 0.0
                    recs.ttl_sale_amount = 0.0
                    matched = False
                    _logger.info(
                        "SALE_AMOUNT_DEBUG file=%s price_list=%s(type=%s) "
                        "file.category=%s file.sector=%s file.unit_category_type=%s(id=%s)",
                        recs.id, recs.price_list_id.name, recs.price_list_id.price_list_type,
                        recs.category_id.name, recs.sector_id.name,
                        recs.unit_category_type_id.name, recs.unit_category_type_id.id,
                    )
                    for rec in recs.price_list_id.pricelist_line:
                        _logger.info(
                            "  line id=%s category=%s sector=%s unit_category_type=%s(id=%s) price=%s",
                            rec.id, rec.category_id.name, rec.sector_id.name,
                            rec.unit_category_type_id.name, rec.unit_category_type_id.id, rec.price,
                        )
                        if recs.price_list_id.price_list_type == 'unit':
                            if (rec.size_id == recs.size_id
                                    and rec.category_id == recs.category_id
                                    and rec.sector_id == recs.sector_id
                                    and rec.unit_inventory_id == recs.inventory_id
                                    and rec.starting_date <= recs.booking_date <= rec.end_date):
                                recs.sale_amount = rec.price
                                recs.ttl_sale_amount = recs.sale_amount
                                matched = True

                            elif (rec.size_id == recs.size_id
                                  and rec.category_id == recs.category_id
                                  and rec.sector_id == recs.sector_id
                                  and rec.unit_inventory_id == recs.inventory_id
                                  and rec.starting_date <= recs.booking_date <= rec.end_date):
                                recs.sale_amount = rec.price
                                recs.ttl_sale_amount = recs.sale_amount
                                matched = True

                        if recs.price_list_id.price_list_type == 'sq_ft' and recs.pricing_policy == 'area':
                            if (rec.size_id == recs.size_id and rec.category_id == recs.category_id
                                    and rec.sector_id == recs.sector_id
                                    and rec.unit_inventory_id == recs.inventory_id
                                    and rec.starting_date <= recs.booking_date <= rec.end_date):
                                recs.rate_sq_ft = rec.price
                                recs.sale_amount = recs.rate_sq_ft * (recs.covered_area or rec.area)
                                recs.ttl_sale_amount = recs.sale_amount
                                matched = True

                            elif (rec.category_id == recs.category_id
                                  and rec.sector_id == recs.sector_id
                                  and rec.unit_inventory_id == recs.inventory_id
                                  and rec.starting_date <= recs.booking_date <= rec.end_date):
                                recs.rate_sq_ft = rec.price
                                recs.sale_amount = recs.rate_sq_ft * (recs.covered_area or rec.area)
                                recs.ttl_sale_amount = recs.sale_amount
                                matched = True

                        # Fallback — applies whenever the type-specific branches
                        # above haven't already matched a line this pass (covers
                        # price_list_type == 'generic', and 'unit'/'sq_ft'
                        # lists where no line matches this exact unit). Blank
                        # fields on the price list line are treated as
                        # wildcards, since a "Generic" line is meant to apply
                        # broadly rather than requiring every criterion set.
                        if not matched:
                            if ((not rec.category_id or rec.category_id == recs.category_id)
                                    and (not rec.sector_id or rec.sector_id == recs.sector_id)
                                    and (not rec.unit_category_type_id
                                         or rec.unit_category_type_id == recs.unit_category_type_id)):
                                recs.sale_amount = rec.price
                                recs.ttl_sale_amount = recs.sale_amount
                                matched = True

                    _logger.info(
                        "SALE_AMOUNT_DEBUG result matched=%s sale_amount=%s",
                        matched, recs.sale_amount,
                    )

                    # Running totals — NOT gated on recs.ttl_sale_amount's own
                    # (stale) truthiness, which broke whenever sale_amount
                    # legitimately computed to 0 (a falsy value indistinguishable
                    # from "not yet set" under the old per-branch checks).
                    factor = 0
                    crm_factor = 0
                    for rec in recs.preference_ids:
                        if recs.crm_id or recs.token_id:
                            rec.total = (recs.sale_amount * rec.value) / 100
                            if rec.approved:
                                crm_factor += rec.total
                            recs.factor_amount = round(crm_factor) if rec.approved else 0
                        elif rec.approved and rec.basis == 'fix':
                            factor = factor + rec.value
                            recs.factor_amount = factor
                        elif rec.approved and rec.basis == 'percentage':
                            factor = factor + (recs.sale_amount * rec.value) / 100
                            recs.factor_amount = factor
                        else:
                            recs.factor_amount = 0.0

                    if recs.crm_id or recs.token_id:
                        recs.ttl_sale_amount = recs.sale_amount + crm_factor
                    elif recs.preference_ids:
                        recs.ttl_sale_amount = recs.sale_amount + factor
                else:
                    recs.sale_amount = 0.0
                    recs.ttl_sale_amount = 0.0
                    recs.factor_amount = 0.0

    @api.depends('unit_category_type_id', 'category_id', 'booking_date', 'sector_id')
    def _price_list(self, check=True):
        for rec in self:
            if rec.unit_category_type_id and rec.category_id and rec.sector_id and not rec.add_custom_value:
                record = rec.env['price.list'].search([
                    '|',
                    '&',
                    ('starting_date', '<=', rec.booking_date),
                    ('end_date', '=', False),
                    '&',
                    ('starting_date', '<=', rec.booking_date),
                    ('end_date', '>=', rec.booking_date),
                ])
                record = record.search([
                    ('society_id', '=', rec.society_id.id),
                    ('phase_id', '=', rec.phase_id.id),
                    ('id', 'in', record.ids)
                ])

                record = record.mapped('id')

                if not record:
                    raise ValidationError(_("Price List of relevant date does not exist"))
                if len(record) > 1:
                    raise ValidationError(
                        _("Our date is falling between to active price lists ,Something is going wrong"))
                if check:
                    if len(record) == 1:
                        rec.price_list_id = record[0]
                    else:
                        rec.price_list_id = False
            else:
                rec.price_list_id = False

    @api.constrains('discount_amount', 'discount_type')
    def _check_percentage(self):
        for rec in self:
            if rec.discount_type == 'percentage' and rec.discount_amount > 100:
                raise ValidationError(
                    _("Value in Discount could not exceed 100 percentage while 'Discount Type' is percentage"))

    @api.constrains('manual_installment_plan_ids')
    def _check_manual_installment_plan_ids(self):
        if self.manual_installment_plan_ids:
            total_percentage = sum(self.manual_installment_plan_ids.mapped('percentage'))

    @api.constrains('size_id', 'category_id', 'booking_date')
    def _check_price_list_id(self):

        self._price_list(False)

    @api.onchange('create_manually')
    def _onchange_create_manually(self):
        for rec in self:
            if rec.create_manually == True:
                rec.initial_payment = 0
                rec.balloting_amount = 0
                rec.balance_amount = 0
                rec.balance_amount = rec.net_sale_amount

    @api.model
    def installment_invoices(self):
        # --------------------------------------
        date = self.env.ref('real_estate.ir_cron_check_challenge').till_date or fields.Date.today()

        company_id = self.env.company.id
        cr = self._cr
        cr.execute(f"""
                    SELECT 
                        ip.id AS installment_id, 
                        f.id AS file_id, 
                        f.membership_id AS member_id, 
                        ip.date AS installment_date, 
                        ip.installment_type AS installment_type,
                        ip.amount AS installment_amount
                    FROM installment_plan ip
                    INNER JOIN file f ON f.id = ip.file_id
                    WHERE
                        ip.invoice_created = 'false'
                        AND ip.date <= '{date}'
                        AND ip.installment_type != 'down'
                        AND f.state = 'available'
                        AND f.create_manually = 'false'
                        AND f.file_status = 'approve'
                        AND ip.company_id = {company_id}
                        AND f.payment_type = 'installments'
                """)
        installments = cr.dictfetchall()
        if installments:
            for installment in installments:
                payment_terms = self.env.company.payment_terms_final_id if installment['installment_type'] == 'final' else self.env.company.payment_terms_installment_id
                try:
                    tax_ids = self.env.company.installment_tax_ids.ids
                    prod = []
                    if installment['installment_type'] == 'final':
                        _re = self.env.ref('real_estate.final_product')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount'],
                            'tax_ids': tax_ids,
                        })]
                    elif installment['installment_type'] == 'installment':
                        _re = self.env.ref('real_estate.installment_product')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount'],
                            'tax_ids': tax_ids,
                        })]
                    elif installment['installment_type'] == 'balloon':
                        _re = self.env.ref('real_estate.balloon_payment')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount']
                        })]
                    elif installment['installment_type'] == 'possession_amount':
                        _re = self.env.ref('real_estate.possession_amount_product')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount']
                        })]
                    elif installment['installment_type'] == 'confirmation_amount':
                        _re = self.env.ref('real_estate.confirmation_amount_product')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount']
                        })]
                    elif installment['installment_type'] == 'balloting_amount':
                        _re = self.env.ref('real_estate.balloting_product')
                        prod = [(0, 0, {
                            'product_id': _re.product_id.id,
                            'name': _re.name,
                            'account_id': self._product_income_account(_re).id,
                            'price_unit': installment['installment_amount']
                        })]
                    installment_line = self.env['installment.plan'].sudo().browse(installment['installment_id'])
                    invoice = self.env['account.move'].create({
                        'partner_id': self.env['res.member'].browse(installment['member_id']).partner_id.id,
                        'move_type': 'out_invoice',
                        'journal_id': (
                            self.env.company.account_journal_id.id
                            or self.env['account.journal'].search(
                                [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1
                            ).id
                        ),
                        'property_invoice_type': installment['installment_type'] if installment['installment_type'] else 'installment',
                        'user_id': self.user_id.id,
                        'date': installment['installment_date'],
                        'invoice_date': installment['installment_date'],
                        'invoice_payment_term_id': payment_terms.id,
                    })

                    invoice.file_ids = installment['file_id']
                    invoice.installment_id = installment['installment_id']
                    invoice.invoice_line_ids = prod

                    invoice.action_post()
                    installment_line.file_id.file_payment_history_id.create({
                        'invoice_id': invoice.id,
                        'file_id': installment['file_id']
                    })

                    installment_line.invoice_id = invoice.id
                    installment_line.invoice_created = True
                    try:
                        self.env.cr.commit()
                    except:
                        pass

                except Exception as e:
                    raise ValueError('There is some error: %s in auto invoice creation for installment' % e)
        # -----------------------------------------
        # files = self.installment_plan_ids.search_read(
        #     [('invoice_created', '=', False),
        #      ('file_id.society_id.company_id', '=', self.env.company.id),
        #      ('date', '<=', date),
        #      ('installment_type', '!=', 'down'),
        #      ('invoice_created', '=', False),
        #      ('file_id.state', '=', 'available'),
        #      ('file_id.state', 'not in', ['cancel', 'refund']),
        #      ('file_id.create_manually', '=', False),
        #      ('file_id.file_status', '=', 'approve'),
        #      ('file_id.society_id.company_id', '=', self.env.company.id),
        #      ('file_id.payment_type', '=', 'installments')], ['file_id'])



        # count = 0
        # if files:
        #     for file in files:
        #         rec = self.browse(file['file_id'][0])
        #         tax_ids = rec.installment_tax_ids.ids if rec.installment_tax_ids else rec.env.company.installment_tax_ids.ids
        #         no_of_installment = []
        # 
        #         if rec.installment_plan_ids.filtered(lambda x: x.date <= date and not x.invoice_created):
        #             for installment in rec.installment_plan_ids.filtered(lambda x: x.date <= date and not x.invoice_created):
        #                 payment_terms = rec.env.company.payment_terms_final_id if \
        #                     installment.installment_type == 'final' else rec.env.company.payment_terms_installment_id
        # 
        #                 if installment.installment_type != 'down' and installment.date <= date and not installment.invoice_created:
        #                     try:
        #                         prod = []
        # 
        #                         if self.env.company.ownership_percentage and rec.membership_id.company_type == 'aop':
        #                             for member in rec.membership_id.cnic_line_ids:
        #                                 if installment.installment_type == 'final':
        #                                     prod.append((0, 0, {
        #                                         'product_id': self.env.ref('real_estate.final_product').id,
        #                                         'name': member.member_name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.final_product').property_account_income_id.id,
        #                                         'price_unit': (installment.amount * member.ownership) / 100,
        #                                         'tax_ids': tax_ids,
        #                                     }))
        #                                 elif installment.installment_type == 'installment':
        #                                     prod.append((0, 0, {
        #                                         'product_id': self.env.ref('real_estate.installment_product').id,
        #                                         'name': member.member_name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.installment_product').property_account_income_id.id,
        #                                         'price_unit': (installment.amount * member.ownership) / 100,
        #                                         'tax_ids': tax_ids,
        #                                     }))
        #                                 elif installment.installment_type == 'balloon':
        #                                     prod.append((0, 0, {
        #                                         'product_id': self.env.ref('real_estate.balloon_payment').id,
        #                                         'name': member.member_name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.balloon_payment').property_account_income_id.id,
        #                                         'price_unit': (installment.amount * member.ownership) / 100
        #                                     }))
        #                                 elif installment.installment_type == 'possession_amount':
        #                                     prod = [(0, 0, {
        #                                         'product_id': self.env.ref('real_estate.possession_amount_product').id,
        #                                         'name': self.env.ref('real_estate.possession_amount_product').name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.possession_amount_product').property_account_income_id.id,
        #                                         'price_unit': installment.amount
        #                                     })]
        #                                 elif installment.installment_type == 'confirmation_amount':
        #                                     prod = [(0, 0, {
        #                                         'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
        #                                         'name': self.env.ref('real_estate.confirmation_amount_product').name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.confirmation_amount_product').property_account_income_id.id,
        #                                         'price_unit': installment.amount
        #                                     })]
        #                                 elif installment.installment_type == 'balloting_amount':
        #                                     prod = [(0, 0, {
        #                                         'product_id': self.env.ref('real_estate.balloting_product').id,
        #                                         'name': self.env.ref('real_estate.balloting_product').name,
        #                                         'account_id': self.env.ref(
        #                                             'real_estate.balloting_product').property_account_income_id.id,
        #                                         'price_unit': installment.amount
        #                                     })]
        #                         else:
        #                             if installment.installment_type == 'final':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.final_product').id,
        #                                     'name': self.env.ref('real_estate.final_product').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.final_product').property_account_income_id.id,
        #                                     'price_unit': installment.amount,
        #                                     'tax_ids': tax_ids,
        #                                 })]
        #                             elif installment.installment_type == 'installment':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.installment_product').id,
        #                                     'name': self.env.ref('real_estate.installment_product').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.installment_product').property_account_income_id.id,
        #                                     'price_unit': installment.amount,
        #                                     'tax_ids': tax_ids,
        #                                 })]
        #                             elif installment.installment_type == 'balloon':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.balloon_payment').id,
        #                                     'name': self.env.ref('real_estate.balloon_payment').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.balloon_payment').property_account_income_id.id,
        #                                     'price_unit': installment.amount
        #                                 })]
        #                             elif installment.installment_type == 'possession_amount':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.possession_amount_product').id,
        #                                     'name': self.env.ref('real_estate.possession_amount_product').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.possession_amount_product').property_account_income_id.id,
        #                                     'price_unit': installment.amount
        #                                 })]
        #                             elif installment.installment_type == 'confirmation_amount':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
        #                                     'name': self.env.ref('real_estate.confirmation_amount_product').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.confirmation_amount_product').property_account_income_id.id,
        #                                     'price_unit': installment.amount
        #                                 })]
        #                             elif installment.installment_type == 'balloting_amount':
        #                                 prod = [(0, 0, {
        #                                     'product_id': self.env.ref('real_estate.balloting_product').id,
        #                                     'name': self.env.ref('real_estate.balloting_product').name,
        #                                     'account_id': self.env.ref(
        #                                         'real_estate.balloting_product').property_account_income_id.id,
        #                                     'price_unit': installment.amount
        #                                 })]
        # 
        #                         invoice = self.env['account.move'].create({
        #                             'partner_id': rec.membership_id.id,
        #                             'move_type': 'out_invoice',
        #                             'journal_id': self.env.company.account_journal_id.id,
        #                             # 'property_invoice_type': 'installment',
        #                             'property_invoice_type': installment.installment_type if installment.installment_type else 'installment',
        #                             'user_id': rec.user_id.id,
        #                             'date': installment.date,
        #                             'invoice_date': installment.date,
        #                             'invoice_payment_term_id': payment_terms.id,
        #                         })
        # 
        #                         invoice.file_ids = rec.id
        # 
        #                         invoice.invoice_line_ids = prod
        # 
        #                         invoice.action_post()
        #                         rec.file_payment_history_id.create({
        #                             'invoice_id': invoice.id,
        #                             'file_id': rec.id
        #                         })
        # 
        #                         installment.invoice_id = invoice.id
        #                         installment.invoice_created = True
        #                         count += 1
        # 
        #                         try:
        #                             self.env.cr.commit()
        #                         except:
        #                             pass
        # 
        #                         # if count == 20:
        #                         #     count = 0
        # 
        #                     except Exception as e:
        #                         raise ValueError('There is some error: %s in auto invoice creation for installment' % e)
        # 
        #                 no_of_installment.append(installment.invoice_created)
        #         else:
        #             no_of_installment.append(False)
        # 
        #         if all(no_of_installment):
        #             rec.payment_states = 'close'

    def open_installment_wizard(self):
        return {
            'res_model': 'installment.invoice.wizard',
            'type': 'ir.actions.act_window',
            'context': {'default_file_id': self.id, 'default_from_file': True},
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': self.env.ref("real_estate.installment_invoice_wizard_form").id,
            'target': 'new'
        }

    @api.model
    def manual_installment_invoices(self):
        date = self.env.ref('real_estate.ir_cron_manual_installment').till_date or fields.Date.today()

        for rec in self.search([('create_manually', '=', True)]):
            if rec.installment_tax_ids:
                tax_ids = rec.installment_tax_ids.ids
            else:
                tax_ids = rec.env.company.installment_tax_ids.ids
            no_of_installment = []
            installment_product = self.env.ref('real_estate.installment_product')
            final_product = self.env.ref('real_estate.final_product')
            if rec.manual_installment_plan_ids \
                    and rec.payment_states == 'open' \
                    and rec.state not in ['cancel', 'refund'] \
                    and rec.society_id.company_id == self.env.user.company_id:
                for installment in rec.manual_installment_plan_ids:
                    if installment.date <= date \
                            and not installment.invoice_created \
                            and installment.product_id.id in [installment_product.id, final_product.id]:
                        try:
                            prod = [(0, 0, {
                                'product_id': installment.product_id.product_id.id,
                                'name': installment.product_id.name,
                                'account_id': self._product_income_account(installment.product_id).id,
                                'price_unit': installment.amount_manual,
                                'tax_ids': tax_ids,
                            })]

                            invoice = self.env['account.move'].create({
                                # 'file_ids': rec.id,
                                'move_type': 'out_invoice',
                                # 'invoice_payment_ref': rec.name,
                                'partner_id': rec.membership_id.partner_id.id,
                                'company_id': self.env.company.id,
                                'property_invoice_type': 'installment',
                                # 'invoice_nature': 'Installment',
                                'user_id': rec.user_id.id,
                                'date': installment.date,
                                'invoice_date': installment.date,
                                'invoice_date_due': installment.date,
                                # 'account_id': rec.membership_id.property_account_receivable_id.id,
                                'invoice_line_ids': prod
                            })
                            invoice.file_ids = rec.id
                            invoice.action_post()

                            rec.file_payment_history_id.create({
                                'invoice_id': invoice.id,
                                'file_id': rec.id
                            })

                            installment.invoice_id = invoice.id

                            installment.invoice_created = True
                        except Exception as e:
                            raise UserError('There is some error: %s in auto invoice creation for manual installment' % (e))
                    no_of_installment.append(installment.invoice_created)
            else:
                no_of_installment.append(False)

            if all(no_of_installment):
                rec.payment_states = 'close'

    @api.model
    def advance_amount_adjustment(self):
        date = self.env.ref('real_estate.ir_cron_advance_adjustment').till_date or fields.Date.today()
        # files = self.env['account.payment'].search([('file_id', '!=', False), ('is_advance_payment', '=', True), ('state', '=', 'posted')]).mapped('file_id')
        files = self.env['account.payment'].search(
            [('file_id', '!=', False), ('is_advance_payment', '=', True), ('state', '=', 'paid'),
             ('amount_residual', '>', 0)]).mapped('file_id')
        print("TOTAL FILES: ", len(files))
        if not files:
            print("No advance found against file with residual amount > 0.")  # Adding this to see in logs on server
        for rec in files:
            advance_payments = self.env['account.payment'].search(
                [('file_id', '=', rec.id), ('is_advance_payment', '=', True), ('state', '=', 'paid'),
                 ('amount_residual', '>', 0)], order='id asc')
            print("ADVANCE PAYMENT: ", advance_payments.ids)
            for advance_payment in advance_payments:
                payment_amount = advance_payment.amount_residual
                if rec.installment_plan_ids \
                        and rec.create_manually == False \
                        and rec.state not in ['cancel', 'refund'] \
                        and rec.society_id.company_id == self.env.user.company_id \
                        and advance_payment:
                    plans = rec.installment_plan_ids.filtered(lambda l: l.payment_status != 'paid')
                    multi_invoice_ids = []
                    for installment in plans:

                        if installment.state != 'paid' and not installment.invoice_created and payment_amount > 0:
                            print("CREATING INVOICE AGAINST THIS %s FILE: " % (rec))
                            _re = self.env.ref('real_estate.installment_product')
                            prod = [(0, 0, {
                                'product_id': _re.product_id.id,
                                'name': _re.name,
                                'account_id': self._product_income_account(_re).id,
                                'price_unit': installment.amount,
                            })]

                            invoice = self.env['account.move'].create({
                                # 'file_ids': rec.id,
                                # 'invoice_payment_ref': rec.name,
                                'partner_id': rec.membership_id.partner_id.id,
                                'move_type': 'out_invoice',
                                'journal_id': (
                                    self.env.company.account_journal_id.id
                                    or self.env['account.journal'].search(
                                        [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1
                                    ).id
                                ),
                                'property_invoice_type': 'installment',
                                'user_id': rec.user_id.id,
                                'date': installment.date,
                                'invoice_date': installment.date,
                                'invoice_payment_term_id': rec.env.company.payment_terms_final_id.id,
                                'invoice_line_ids': prod
                            })
                            invoice.file_ids = rec.id
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
                            installment.invoice_id.advance_payment_ids = [(4, advance_payment.id)]

                    multi_invoices = self.env['multi.invoice.payment'].browse(multi_invoice_ids)

                    # Applying Advance Payment against invoices
                    invoices = multi_invoices.mapped('invoice_id')
                    print("Applying Advance Payment against invoices")
                    for record in invoices:
                        partner_id = self.env['res.partner']._find_accounting_partner(
                            record.partner_id).id
                        invoice_move_lines = invoices.mapped('line_ids')
                        invoice_move_lines = invoice_move_lines.filtered(
                            lambda r: not r.reconciled and r.account_id.account_type in
                                      ('asset_receivable', 'liability_payable'))

                        advance_payment_accounts = self.env['account.account']
                        payment_move_line = {}
                        for payment in advance_payment:
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
                        if advance_payment.amount_residual >= record.amount_residual:
                            advance_payment_residual = record.amount_residual
                        elif advance_payment.amount_residual <= record.amount_residual:
                            advance_payment_residual = advance_payment.amount_residual
                        counterpart_balance = currency_exchange_diff = 0.0
                        currency_company = advance_payment.company_id.currency_id
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

                                if advance_payment.partner_type == 'customer':
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
                            if advance_payment.partner_type == 'customer':
                                account_id = advance_payment.partner_id.property_account_receivable_id
                            elif advance_payment.partner_type == 'supplier':
                                account_id = advance_payment.partner_id.property_account_payable_id
                            else:
                                raise ValidationError(_("Partner type is nither customer nor supplier"))
                            advance_payment_move_lines.append((0, 0, {
                                'name': 'Advance Payment: %s' % ', '.join(invoices.mapped('name')),
                                'account_id': account_id.id,
                                'partner_id': partner_id,
                                'debit': advance_payment.partner_type == 'supplier' and counterpart_balance or 0.0,
                                'credit': advance_payment.partner_type == 'customer' and counterpart_balance or 0.0,
                                'payment_id': payment_id.id,
                                'is_advance_payment_account': False,
                            }))

                        if currency_exchange_diff:
                            currency_exchange_journal = advance_payment.company_id.currency_exchange_journal_id
                            if currency_exchange_diff < 0:
                                if advance_payment.partner_type == 'supplier':
                                    currency_exchange_account = currency_exchange_journal.default_debit_account_id
                                    credit = 0.0
                                    debit = abs(currency_exchange_diff)
                                else:
                                    currency_exchange_account = currency_exchange_journal.default_credit_account_id
                                    credit = abs(currency_exchange_diff)
                                    debit = 0.0
                            else:
                                if advance_payment.partner_type == 'supplier':
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
                                'company_id': advance_payment.company_id.id,
                                'journal_id': advance_payment.journal_id.id,
                                'line_ids': advance_payment_move_lines,
                            })
                            move.action_post()

                            invoice_payment_move_lines = move.line_ids.filtered(
                                lambda r: not r.reconciled and r.account_id.account_type in ('liability_payable', 'asset_receivable'))
                            advance_payment_move_lines = move.line_ids.filtered(
                                lambda r: not r.reconciled and r.account_id in
                                          advance_payment_accounts)

                            (invoice_payment_move_lines + invoice_move_lines).reconcile()
                            (advance_payment_move_lines + payment_move_lines).reconcile()

    @api.model
    def _check_inventory_id(self):

        return [('id', 'not in', [rec.inventory_id.id for rec in self.env['file'].search([])])]

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        res = super(File, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

        is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')
        is_user2 = self.env.user.has_group('real_estate.group_can_create_record')
        try:
            from_member = self._context['from_member']
        except:
            from_member = False

        if not from_member and is_user:
            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='file_management']")
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='file_management']")
                doc.set('edit', 'true')
                res['arch'] = ET.tostring(doc)
        elif from_member and is_user:
            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='file_management']")
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)

            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='file_management']")
                doc.set('edit', 'true')
                res['arch'] = ET.tostring(doc)
        else:
            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='file_management']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='file_management']")
                doc.set('create', 'false')
                doc.set('edit', 'false')
                res['arch'] = ET.tostring(doc)

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if 'token_generated' in val:
                val['token_generated'] = True
            if val.get('name', _('New')) == _('New'):
                if val.get('project_type') == 'skyscraper' or self._context.get('current_view') == 'buildings':
                    val['name'] = self.env['ir.sequence'].next_by_code("file.skyscraper") or _('New')
                else:
                    val['name'] = self.env['ir.sequence'].next_by_code("file") or _('New')
            if val.get('tracking_id', _('*')) == _('*') and val.get('type') != 'investor':
                if val.get('project_type') == 'skyscraper' or self._context.get('current_view') == 'buildings':
                    val['tracking_id'] = self.env['ir.sequence'].next_by_code("file.tracking.building") or _('*')
                elif val.get('project_type') == 'housing_society' or self._context.get('current_view') == 'realestate':
                    val['tracking_id'] = self.env['ir.sequence'].next_by_code("file.tracking") or _('*')
            if val.get('secret_token', _('New')) == _('New'):
                val['secret_token'] = secrets.token_hex(10)

        return super(File, self).create(vals_list)

    def write(self, vals):
        return super(File, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.file_status == 'lock' or rec.file_status == 'approve':
                raise UserError(_('You cannot delete file once it is locked or approved!'))

        return super(File, self).unlink()

    @api.depends('name', 'tracking_id')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.name and record.name != 'New':
                name = "%s / %s" % (record.tracking_id, record.name)
            result.append((record.id, name))
        return result

    @api.depends('installment_plan_ids','installment_plan_ids.invoice','installment_plan_ids.payment_status')
    def count_due_installments(self):
        for rec in self:
            rec.installment_due_count = len(
                rec.installment_plan_ids.filtered(
                    lambda p: p.invoice and p.payment_status not in ['paid', 'cancel']
                )
            )



class FilePayment(models.Model):
    _name = 'file.payment'
    _rec_name = 'product_id'
    _description = "File Payment"

    product_id = fields.Many2one('product.realestate', ondelete='set null')
    payment_type = fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage')
    ], string='Calculation Base')
    value = fields.Float(digits=(2, 6))
    total = fields.Float()
    initial_payment = fields.Float()
    remaining_payment = fields.Float(compute='_compute_remaining_value')
    no_of_installment = fields.Integer()
    per_installment = fields.Float(compute='_compute_per_installment')
    is_fully_paid = fields.Boolean(compute='_compute_remaining_value')
    file_payment_plan_id = fields.Many2one('file')
    transfer_application_id = fields.Many2one('transfer.application')

    @api.constrains('initial_payment', 'remaining_payment')
    def _check_percentage(self):
        if self.initial_payment > self.total:
            raise ValidationError(
                _("Initial Payment could not exceed the total payment of product."))

        if self.remaining_payment and not self.no_of_installment:
            raise ValidationError(
                _("No of Installment could not be zero if There is a remaining_payment unpaid."))

    @api.depends('remaining_payment', 'no_of_installment')
    def _compute_per_installment(self):
        for rec in self:
            rec.per_installment = round(
                rec.remaining_payment / rec.no_of_installment if rec.no_of_installment > 0 else 0)

    @api.depends('total', 'initial_payment')
    def _compute_remaining_value(self):
        for rec in self:
            rec.remaining_payment = round(rec.total - rec.initial_payment)
            rec.is_fully_paid = True if rec.total != 0.00 and rec.total == rec.initial_payment else False

    # @api.depends('value', 'payment_type')
    # def _compute_total_value(self):
    #     for rec in self:
    #         rec.total = round(rec.value) if rec.payment_type == 'fix' else \
    #         [round(rec.file_payment_plan_id.net_sale_amount * rec.value / 100)][0]

    @api.onchange('remaining_payment')
    def _onchanage_remainging_payment(self):
        for rec in self:
            if rec.remaining_payment:
                rec.no_of_installment = 1
            else:
                rec.no_of_installment = 0


class InstallmentPlan(models.Model):
    _name = 'installment.plan'

    _rec_name = 'date'
    _description = "Installment Plan"

    # serial_no = fields.Integer()
    line_calculated = fields.Boolean(default=False)
    product_id = fields.Many2one('product.realestate', ondelete='set null',
                                 default=lambda self: self.env.ref('real_estate.installment_product').id,
                                 )
    date = fields.Date(required=True)
    percentage = fields.Float(digits=(2, 6))
    amount = fields.Float()
    amount_manual = fields.Float(string='Amount ', store=True, readonly=False, compute='_compute_amount')
    installment_number = fields.Integer(readonly=False)
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', 'Ref')
    new_installment_number = fields.Integer()
    state = fields.Char(string='Status', readonly=False, related='invoice_id.invoice_way_type')
    installment_type = fields.Selection([
        ('down', 'Booking Payment'),
        ('installment', 'Installment'),
        ('balloon', 'Balloon'),
        ('final', 'Final Payment'),
        ('possession_amount', 'Possession'),
        ('balloting_amount', 'Balloting'),
        ('confirmation_amount', 'Confirmation')
    ], default='installment')
    file_id = fields.Many2one('file')

    # New Fields

    file_type = fields.Selection([
        ('new', 'New'),
        ('legacy', 'Legacy')
    ], default='new')
    invoice = fields.Char(related='invoice_id.name', store=True, readonly=False)

    payment_date = fields.Date('Payment Date', store=True, compute='_payment_date', readonly=False)
    # payment_created_date = fields.Date('Payment Create Date', store=True, related='invoice_id.payment_id.create_date', readonly=False)
    # payment_created_by = fields.Char('Payment Created By', store=True, related='invoice_id.payment_id.create_uid.name', readonly=False)
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('installment', 'Installment'),
        ('transfer_application', 'Transfer Application'),
        ('others', 'Others'),
    ], related='invoice_id.property_invoice_type', readonly=False, string='Invoice Type')
    amount_paid = fields.Float('Amount Paid', store=True, compute='_invoice_id_data', readonly=False)
    residual = fields.Float('Amount Due', store=True, compute='_invoice_id_data', readonly=False)
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=False, copy=False, tracking=True,
        related='invoice_id.payment_state')
    double_check_paid_amount = fields.Boolean(compute="_double_check_paid_amount")
    investor_payment = fields.Boolean()
    tax_amount = fields.Float()
    installment_name = fields.Char()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)

    # return_line_id = fields.Many2one('return.line')

    @api.depends('invoice_created', 'invoice_id', 'amount_paid')
    def _payment_date(self):
        for rec in self:
            rec.payment_date = ''
            if rec.invoice_created:
                multi_inv = self.env['multi.invoice.payment'].search([('invoice_id', '=', rec.invoice_id.id)])
                if len(multi_inv) > 1:
                    multi_inv = multi_inv[-1]
                payment = multi_inv.payment_id

                # finding payment reference in case of advance application
                if not payment:
                    payment = self.env['account.payment'].search([('invoice_ids', '=', rec.invoice_id.id), ('is_advance_payment', '=', True)])
                    if len(payment) > 1:
                        payment = payment[-1]
                    # if payment and rec.payment_status in ('in_payment', 'paid'):
                    # rec.payment_date = dateutil.parser.parse(str(payment.payment_date)) if payment.date else ''
                if payment and rec.amount_paid > 0:
                    rec.payment_date = payment.date if payment.date else False

    def _double_check_paid_amount(self):
        for rec in self:
            if rec.invoice_id and rec.amount_paid != rec.invoice_id.amount_total - rec.invoice_id.amount_residual:
                rec._invoice_id_data()
            rec.double_check_paid_amount = True

    @api.depends('invoice_id', 'invoice_id.amount_residual', 'file_id.token_id', 'installment_type')
    def _invoice_id_data(self):
        for rec in self:
            token_amount = 0
            if rec.file_id.token_id and rec.invoice_created and rec.installment_type == 'down':
                token = rec.file_id.token_id
                token_amount = token.token_fees
                ''

    @api.depends('invoice_created', 'invoice_id', 'amount_paid')
    def _payment_created_by(self):
        for rec in self:
            rec.payment_created_by = ''
            if rec.invoice_created:
                multi_inv = self.env['multi.invoice.payment'].search([('invoice_id', '=', rec.invoice_id.id)])
                if len(multi_inv) > 1:
                    multi_inv = multi_inv[-1]
                payment = multi_inv.payment_id

                # finding payment reference in case of advance application
                if not payment:
                    payment = self.env['account.payment'].search(
                        [('invoice_ids', '=', rec.invoice_id.id), ('is_advance_payment', '=', True)])
                    if len(payment) > 1:
                        payment = payment[-1]
                if payment and rec.payment_status == 'paid':
                    rec.payment_created_by = dateutil.parser.parse(str(payment.create_uid.name)) if date else ''

    def _double_check_paid_amount(self):
        for rec in self:
            if rec.invoice_id and rec.amount_paid != rec.invoice_id.amount_total - rec.invoice_id.amount_residual:
                rec._invoice_id_data()
            rec.double_check_paid_amount = True

    @api.depends('invoice_id', 'invoice_id.amount_residual', 'file_id.token_id', 'installment_type')
    def _invoice_id_data(self):
        for rec in self:
            token_amount = 0
            if rec.file_id.token_id and rec.invoice_created and rec.installment_type == 'down':
                token = rec.file_id.token_id
                token_amount = token.token_fees
                token.state = 'adjusted'
            rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual + token_amount
            rec.residual = rec.invoice_id.amount_residual

    @api.depends('file_id.net_sale_amount', 'percentage')
    def _compute_amount(self):
        self.amount_manual = 0
        for rec in self:
            if rec.file_id.installment_tax_ids:
                tax_id = rec.file_id.installment_tax_ids
            else:
                tax_id = self.env.company.installment_tax_ids
            if rec.file_id.create_manually == True:
                rec.amount_manual = round(rec.file_id.net_sale_amount * (rec.percentage / 100))
                rec.tax_amount = round(rec.amount_manual * (tax_id[0].amount / 100), 2) if tax_id else 0
                rec.residual = rec.amount_manual + round(rec.amount_manual * (tax_id[0].amount / 100),
                                                         2) if tax_id else rec.amount_manual

    def unlink(self):
        for rec in self:
            if rec.invoice_created:
                raise UserError(_('You cannot delete record when invoice is created!'))

        return super(InstallmentPlan, self).unlink()


class PaymentInterval(models.Model):
    _name = 'payment.interval'
    _rec_name = 'name'
    _description = "Payment Interval"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    name = fields.Char()
    nom = fields.Integer('Number of Months')


class FilePaymentHistory(models.Model):
    _name = 'file.payment.history'
    _description = "File Payment History"

    date_invoice = fields.Date('Invoice Date', related='invoice_id.invoice_date')
    payment_date = fields.Date('Payment Date', compute='_payment_date')
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('installment', 'Installment'),
        ('transfer_application', 'Transfer Application'),
        ('others', 'Others'),
    ], related='invoice_id.property_invoice_type', string='Invoice Type')
    # transaction_type = fields.Char('Transaction Type', related = 'invoice_id.transaction_type')
    invoice_id = fields.Many2one('account.move')
    amount_total = fields.Float('Total Amount', compute='_invoice_id_data')
    amount_paid = fields.Float('Amount Paid', compute='_invoice_id_data')
    residual = fields.Float('Amount Due', compute='_invoice_id_data')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, related='invoice_id.state')

    file_id = fields.Many2one('file')

    def _payment_date(self):
        for rec in self:
            date = rec.env['account.payment'].search([
                # ('id', 'in', rec.invoice_id.payment_ids.ids),
                ('state', '=', 'paid'),
                # ('invoice_ids.id', '=', rec.invoice_id.id)
            ], limit=1, order='id desc')

            rec.payment_date = dateutil.parser.parse(str(date.create_date)) if date else ''

    def _invoice_id_data(self):
        for rec in self:
            rec.amount_total = rec.invoice_id.amount_total
            rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
            rec.residual = rec.invoice_id.amount_residual


class FileHistory(models.Model):
    _name = 'file.history'

    _description = "File History"

    name = fields.Char('Transaction')
    ref_number = fields.Char(string="Request Number")
    transaction_date = fields.Date()
    new_member_id = fields.Many2one('res.member')
    ex_member_id = fields.Many2one('res.member')
    merged_amount = fields.Float(string='Merged Amount')
    file_id = fields.Many2one('file')


class FileRequestHistory(models.Model):
    _name = 'file.request.history'

    _description = "File Request History"

    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('member_swap', 'Member Swap')
    ], track_visibility='always')
    ref_number = fields.Char(string="Request Number")
    old_inventory_id = fields.Many2one('plot.inventory')
    new_inventory_id = fields.Many2one('plot.inventory')
    old_membership_id = fields.Many2one('res.member', string='Old Member No')
    new_membership_id = fields.Many2one('res.member', string='New Member No')
    old_amount = fields.Float()
    new_amount = fields.Float()
    transaction_date = fields.Date()

    file_id = fields.Many2one('file')


class JointOwner(models.Model):
    _name = 'joint.owner'

    _description = "Joint Owner"

    name = fields.Char()
    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('F/O', 'F/O'),
        ('M/O', 'M/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')
    relation_name = fields.Char('Relation Name')
    percentage = fields.Float()
    cnic = fields.Char('CNIC', copy=False)

    file_id = fields.Many2one('file')


class PowerOfAttorney(models.Model):
    _name = 'power.attorney'

    _description = "Power Of Attorney"

    name = fields.Char()
    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('F/O', 'F/O'),
        ('M/O', 'M/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')
    relation_name = fields.Char('Relation Name')
    cnic = fields.Char('CNIC', copy=False)
    date = fields.Date()

    file_id = fields.Many2one('file')


class InvoicePopup(models.TransientModel):
    _name = "invoice.popup"
    _description = "Invoice Popup"

    file_id = fields.Many2one('file', 'File', readonly=True)
    membership_id = fields.Many2one('res.member', readonly=True)
    date = fields.Date(required=True)
    from_installment_number = fields.Integer()
    journal_id = fields.Many2one('account.journal', 'Payment Journal', domain=[('type', 'in', ('cash', 'bank'))])
    invoice_line = fields.One2many('invoice.popup.line', 'invoice_pop_id')
    from_file_transfer = fields.Boolean(default=False)
    transfer_application_id = fields.Many2one('transfer.application')
    cheque_name = fields.Char('Cheque Name')
    cheque_no = fields.Char('Cheque No')
    bank_ref = fields.Char('Bank Reference')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    payment_type = fields.Selection([('osp', 'One Step Payment'),
                                     ('tsp', 'Two Step Payment')], related='company_id.payment_type')

    def create_invoice(self):
        file = self.file_id
        installment_number = self.from_installment_number
        if self.file_id.installment_tax_ids:
            tax_ids = self.file_id.installment_tax_ids  # allowing only 1 tax on installment or lumpsum
        else:
            tax_ids = self.env.company.installment_tax_ids
        if installment_number:
            # check if invoice created on sepecific number of installment
            if file.mapped('installment_plan_ids')[installment_number - 1].invoice_id:
                raise ValidationError(_(
                    "The invoice of installment number : %s is already created so you can not complete this operation." % (
                        installment_number)))
            available_installment = len(file.installment_plan_ids.search([
                ('file_id', '=', file.id),
                ('invoice_id', '=', False)
            ]))
            required_installment = max(self.invoice_line.mapped('no_of_installment'))

            if required_installment > available_installment:
                raise ValidationError(
                    _("You can not exceed installments more the %s in this transaction" % (available_installment)))

            for rec in self.invoice_line:
                if not rec.is_fully_paid:
                    number_of_time = rec.no_of_installment
                    per_installment = rec.per_installment
                    count = 1
                    for line in file.installment_plan_ids:
                        if count >= self.from_installment_number:
                            if number_of_time and not line.invoice_id:
                                line.amount = line.amount + per_installment
                                number_of_time = number_of_time - 1
                        count = count + 1
                file.new_product_ids.create({
                    'product_id': rec.product_id.id,
                    'payment_type': rec.payment_type,
                    'value': rec.value,
                    'total': rec.total,
                    'initial_payment': rec.initial_payment,
                    'remaining_payment': rec.remaining_payment,
                    'no_of_installment': rec.no_of_installment,
                    'per_installment': rec.per_installment,
                    'is_fully_paid': rec.is_fully_paid,
                    'installment_start_number': self.from_installment_number,
                    'file_id': file.id,
                })

        for rec in self.invoice_line:
            if not rec.is_fully_paid:
                number_of_time = rec.no_of_installment
                per_installment = rec.per_installment
                for line in file.installment_plan_ids:
                    if line.installment_number == 0:
                        line.amount = rec.initial_payment
                    if number_of_time and line.installment_number > 0:
                        line.update({'amount': line.amount + per_installment})
                        number_of_time = number_of_time - 1

        if 0 in self.invoice_line.mapped('total'):
            raise ValidationError(_("Unit price of the products should be non zero number"))
        prod = []
        if self.env.company.ownership_percentage and file.membership_id.company_type == 'aop':
            for member in file.membership_id.cnic_line_ids:
                for rec in self.invoice_line:
                    if rec.initial_payment:
                        prod.append((0, 0, {
                            'product_id': rec.product_id.product_id.id,
                            'name': member.member_name,
                            'account_id': file._product_income_account(rec.product_id).id,
                            'price_unit': (rec.initial_payment * member.ownership) / 100,
                            'company_id': self.env.company,
                            'tax_ids': tax_ids.ids,
                        }))
        else:
            prod = [(0, 0, {
                'product_id': rec.product_id.product_id.id,
                'name': rec.product_id.name,
                'account_id': file._product_income_account(rec.product_id).id,
                'price_unit': rec.initial_payment,
                'company_id': self.env.company,
                'tax_ids': tax_ids.ids,
            }) for rec in self.invoice_line if rec.initial_payment]

        has_initial = True if prod else False

        if has_initial:
            # for rec in self.invoice_line:
            invoice = self.env['account.move'].create({
                # 'file_ids': file.id,
                'transfer_application_id': self.transfer_application_id.id if self.from_file_transfer else '',
                'company_id': self.env.company.id,
                'partner_id': self.membership_id.partner_id.id or file.membership_id.partner_id.id,
                'property_invoice_type': 'initial_payment',
                'move_type': 'out_invoice',
                'user_id': file.user_id.id,
                'date': self.date,
                'invoice_date': self.file_id.booking_date + relativedelta(days=+self.file_id.grace_period),
                'invoice_payment_term_id': self.env.company.payment_terms_initial_id.id,
                # 'invoice_date_due': self.date,
                'journal_id': (
                    self.env.company.account_journal_id.id
                    or self.env['account.journal'].search(
                        [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1
                    ).id
                ),
                # 'account_id': self.membership_id.property_account_receivable_id.id,
                'invoice_line_ids': prod,
            })
            invoice.file_ids = file.id
            invoice.action_post()

            payment_type = self.env.company.payment_type
            if payment_type and payment_type == 'osp':
                inv = [(0, 0, {'invoice_id': invoice.id,
                               'payment_id': False,
                               'payment_due': invoice.amount_residual,
                               'payment_amount': invoice.amount_residual
                               })]

                payment = self.env['account.payment'].create({
                    'date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'payment_category': 'multi_inv_payment',
                    'partner_id': self.membership_id.partner_id.id,
                    'file_id': self.file_id.id,
                    'amount': invoice.amount_residual,
                    'journal_id': self.journal_id.id,
                    'company_id': self.env.company.id,
                    'currency_id': self.env.company.currency_id.id,
                    'multi_invoice_ids': inv,
                    'memo': invoice.name,
                    'cheque_name': self.cheque_name,
                    'cheque_no': self.cheque_no,
                    'bank_ref': self.bank_ref,
                })
                payment.action_post()
                file.payment_states = 'open'
            if file.payment_type == 'lump_sum':
                file.installment_plan_ids.create({
                    'date': file.booking_date,
                    'installment_type': 'down',
                    'installment_number': 0,
                    'amount': self.file_id.ttl_sale_amount,
                    'amount_paid': invoice.amount_total - invoice.amount_residual,
                    'tax_amount': round((self.file_id.ttl_sale_amount * tax_ids[0].amount) / 100, 2) if tax_ids else 0,
                    'residual': invoice.amount_residual,
                    'payment_status': invoice.payment_state,
                    'file_id': file.id
                })
                file.payment_states = 'close'
                if file.token_id:
                    file.token_id.state = 'adjusted'
            if file.create_manually:
                for rec in file.manual_installment_plan_ids:
                    if rec.installment_number == 1 and rec.invoice_created != True:
                        rec.write({
                            'invoice_created': True,
                            'invoice_id': invoice.id,
                        })
            else:
                for rec in file.installment_plan_ids:
                    if rec[0].installment_type == 'down' and rec.invoice_created != True:
                        rec.write({
                            'invoice_created': True,
                            'invoice_id': invoice.id,
                        })
        
        return True


class InvoicePopupLine(models.TransientModel):
    _name = "invoice.popup.line"
    _description = "Invoice Popup Line"

    product_id = fields.Many2one('product.realestate', ondelete='cascade')
    payment_type = fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage')
    ])
    value = fields.Float()
    total = fields.Float()
    initial_payment = fields.Float()
    remaining_payment = fields.Float(compute='_compute_remaining_value')
    no_of_installment = fields.Integer()
    per_installment = fields.Float(compute='_compute_per_installment')
    is_fully_paid = fields.Boolean(store=True, compute='_compute_is_fully_paid')
    invoice_pop_id = fields.Many2one('invoice.popup')
    from_file_transfer = fields.Boolean(default=False)

    @api.depends('value', 'payment_type')
    def _compute_total_value(self):
        for rec in self:
            rec.total = rec.value if rec.payment_type == 'fix' else \
                [self.env['file'].browse(self._context['active_id']).sale_amount * rec.value / 100][0]

    @api.depends('total', 'initial_payment')
    def _compute_remaining_value(self):
        for rec in self:
            rec.remaining_payment = rec.total - rec.initial_payment

    @api.depends('total', 'initial_payment')
    def _compute_is_fully_paid(self):
        for rec in self:
            rec.is_fully_paid = True if rec.total != 0.00 and rec.total == rec.initial_payment else False

    @api.depends('remaining_payment', 'no_of_installment')
    def _compute_per_installment(self):
        for rec in self:
            rec.per_installment = rec.remaining_payment / rec.no_of_installment if rec.no_of_installment > 0 else 0

    @api.onchange('remaining_payment')
    def _onchanage_remainging_payment(self):
        for rec in self:
            if rec.remaining_payment:
                rec.no_of_installment = 1
            else:
                rec.no_of_installment = 0


class AdvancePopup(models.TransientModel):
    _name = "advance.popup"
    _description = "Advance Popup"

    membership_id = fields.Many2one('res.member', string="Customer")
    file_id = fields.Many2one('file')
    name = fields.Char('Name', related='file_id.name')
    date = fields.Date()
    number_of_invoices_covered = fields.Float()
    amount = fields.Float('Amount to Pay')
    journal_id = fields.Many2one('account.journal')

    # def validate_payment_data(self):

    #     return True if self.amount > 0 and round(self.amount) % round(self.env['file'].browse(self._context['active_id']).installment_plan_ids.mapped('amount')[0]) == 0 else False

    def create_payment(self):
        # if self.validate_payment_data():

        payment = self.env['account.payment'].create({
            'partner_id': self.membership_id.partner_id.id,
            'partner_type': 'customer',
            'is_advance_payment': True,
            'amount': round(self.amount),
            'payment_date': self.date,
            'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
            'payment_type': 'inbound',
            'number_of_invoices_covered': self.number_of_invoices_covered,
            'memo': self.name,
            'journal_id': self.journal_id.id,
            'file_id': self.file_id.id
        })

        payment.action_post()

        self.env['confirmation'].confirmation_popup('Advances')

        # else:
        #     raise ValidationError(_("The advance amount is not dividable on installment"))


class Confirmation(models.TransientModel):
    _name = "confirmation"
    _description = " Confirmation"

    name = fields.Char(readonly=True)

    def confirmation_popup(self, Msj):
        return {
            'name': _('Invoice Created'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'confirmation',
            'view_id': self.env.ref('real_estate.confirmation').id,
            'context': {"default_name": Msj, 'current_view': 'realestate'},
            'type': 'ir.actions.act_window',
            'target': 'new'
        }


class AccountPaymentExt(models.Model):
    _inherit = "account.payment"

    file_id = fields.Many2one('file')
    number_of_invoices_covered = fields.Float()


class NewProductLine(models.Model):
    _name = 'new.product.line'
    _description = "New Product Line"

    product_id = fields.Many2one('product.realestate', ondelete='set null')
    payment_type = fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage')
    ])
    value = fields.Float()
    total = fields.Float()
    initial_payment = fields.Float()
    remaining_payment = fields.Float()
    no_of_installment = fields.Integer()
    per_installment = fields.Float()
    is_fully_paid = fields.Boolean()
    installment_start_number = fields.Integer()
    file_id = fields.Many2one('file')
