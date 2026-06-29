from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import qrcode
import base64
from io import BytesIO
from dateutil.relativedelta import relativedelta
from lxml import etree as ET
import string
import random
import PIL
from PIL import Image
import os
import requests


class UnitsBooking(models.Model):
    _name = 'units.booking'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Units Booking'

    # Selection Fieldp

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('assignment', 'Assignment'),
        ('print', 'Print'),
        ('allotment', 'Allotment'),
        ('issued', 'Issued'),
        ('file_created', 'File Created'),
        ('balloting', 'Balloting')
    ], default="draft", tracking=True)

    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')
    ], string='Payment Type')

    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', readonly=False)

    # Char field
    name = fields.Char(tracking=True)
    sequence_number = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                                  default=lambda self: _('New'))
    transferee_cnic_number = fields.Char('CNIC Number', store=True, related='transferee_partner_id.cnic',
                                         readonly=False)
    transferee_relation_name = fields.Char(store=True, related='transferee_partner_id.relation_name', readonly=False,
                                           string="Transferee Relation Name:")
    prefix = fields.Char(string='Prefix')

    plan_description = fields.Char('Plan Description', store=True, readonly=False)
    transferee_name = fields.Char('Transferee Name')

    # Date field
    booking_date = fields.Date('Booking date', tracking=True)
    date = fields.Date(tracking=True, default=fields.Date.today())
    print_date = fields.Date(tracking=True)
    starting_date = fields.Date(tracking=True)

    # boolean fields
    is_printed = fields.Boolean(default=False, compute='_check_print_state', store=True)
    is_assigned = fields.Boolean(default=False)
    is_transferee_partner = fields.Boolean('Is Member ?')
    is_qr_printed = fields.Boolean(default=False)
    is_receipt_printed = fields.Boolean(default=False)
    is_ledger_printed = fields.Boolean(default=False)
    file_issuance_request_created = fields.Boolean(default=False)
    added_in_platter = fields.Boolean(default=False)

    # Property Details
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector', readonly=False)
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    history_ids = fields.One2many('unit.booking.history', 'unit_booking_id')

    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', store=True, readonly=False)
    transferee_partner_id = fields.Many2one('res.member', 'Name ')
    unit_booking_plan_ids = fields.One2many('unit.booking.plan', 'units_booking_id', readonly=True)
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment')
    agent_id = fields.Many2one('res.partner', string="Dealer")
    sub_agent_id = fields.Many2one('res.partner', string='Sub Dealer')
    deal_pack_id = fields.Many2one('deal.pack')
    jv_id = fields.Many2one('account.move', 'Ref')
    prefix_id = fields.Many2one('unit.batch.generation.line')

    # computed field
    qr_code = fields.Binary("QR Code", compute='generate_qr_code', attachment=True)

    # Numerical fields
    number = fields.Integer(string='Number')
    total_installment = fields.Integer('No of Installment', store=True, readonly=False)
    sale_amount = fields.Float('Sale Amount', store=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', readonly=False, store=True)
    net_sale_amount = fields.Float('Net Sale Amount', store=True, readonly=False)
    balloting_amount = fields.Float(readonly=False, )
    initial_payment = fields.Float('Initial Payment', readonly=False)
    balance_amount = fields.Float('Balance Amount', compute='_compute_balance_amount')

    # installment and payment details
    include_installment = fields.Boolean()
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ], default='custom')
    predefine_plan_id = fields.Many2one('predefine.plan')
    installment_created = fields.Boolean(default=False)

    create_manually = fields.Boolean(default=False)
    custom_sale_amount = fields.Float('Sale Amount')
    add_custom_value = fields.Boolean()
    factor_amount = fields.Float()
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage')
    reset_installment_plan = fields.Selection([('yes', 'Yes'),
                                               ('no', 'No')], tracking=True)
    initial_calculation_basis = fields.Selection([('percentage', 'Percentage'),
                                                  ('fix', 'Fix')], default='percentage', tracking=True)
    balloting_calculation_basis = fields.Selection([('percentage', 'Percentage'), ('fix', 'Fix')],
                                                   default='percentage', string='Final Calculation Basis',
                                                   tracking=True)
    discount_amount = fields.Float(store=True, readonly=False, tracking=True)
    balloting_amount_percentage = fields.Float(string='Final Payment Percentage', readonly=False,
                                               tracking=True)
    initial_payment_percentage = fields.Float('Initial Payment Percentage', readonly=False, tracking=True)
    # remaining_payment = fields.Float(compute='_compute_remaining_amount', store=True, readonly=False)
    installment_amount = fields.Float(tracking=True)
    balloon_payment = fields.Float(tracking=True)
    balloon_payment_interval = fields.Integer(tracking=True)
    balloon_payment_frequency = fields.Integer(tracking=True)
    balloon_payment_start = fields.Integer(tracking=True)
    primary_amount = fields.Float(tracking=True)
    primary_amount_interval = fields.Integer(tracking=True)
    primary_amount_frequency = fields.Integer(tracking=True)
    possession_amount = fields.Float(tracking=True)
    possession_amount_interval = fields.Integer(tracking=True)
    possession_amount_frequency = fields.Integer(tracking=True)
    confirmation_amount = fields.Float(tracking=True)
    confirmation_amount_interval = fields.Integer(tracking=True)
    confirmation_amount_frequency = fields.Integer(tracking=True)
    processing_fee = fields.Float(tracking=True)
    rebate_amount = fields.Float()
    sale_rebate = fields.Float()
    is_sale_rebate_applied = fields.Boolean(default=False)
    unit_size_id = fields.Many2one('unit.size', 'Size')

    def set_predefine_value(self):
        for rec in self:
            rec.confirmation_amount = 0
            rec. confirmation_amount_interval = 0
            rec.confirmation_amount_frequency = 0
            rec.possession_amount = 0
            rec.possession_amount_interval = 0
            rec.possession_amount_frequency = 0
            rec.primary_amount = 0
            rec.primary_amount_interval = 0
            rec.primary_amount_frequency = 0
            rec.balloon_payment = 0
            rec.balloon_payment_interval = 0
            rec.balloon_payment_frequency = 0
            rec.balloon_payment_start = 0

    # plan functions
    @api.onchange('plan_type', 'predefine_plan_id')
    def onchange_plan_type(self):
        for rec in self:
            if rec.plan_type == 'predefine' and rec.predefine_plan_id:
                rec.plan_description = rec.predefine_plan_id.name
                rec.interval_id = rec.predefine_plan_id.interval_id.id
                rec.total_installment = rec.predefine_plan_id.total_installment

    @api.onchange('predefine_plan_id')
    def _balloon_payment(self):
        for recs in self:
            if recs.predefine_plan_id:
                for pre_plan in recs.predefine_plan_id.predefine_plan_line_ids:

                    if recs.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                        recs.initial_payment = round(recs.sale_amount * (
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

    @api.depends('net_sale_amount', 'initial_payment', 'balloting_amount')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = round(rec.net_sale_amount -
                                       rec.initial_payment - rec.balloting_amount - rec.discount_amount)

    @api.depends('is_qr_printed', 'is_receipt_printed', 'is_ledger_printed')
    def _check_print_state(self):
        for rec in self:
            if rec.is_qr_printed and rec.is_receipt_printed and rec.is_ledger_printed:
                rec.is_printed = True
                if rec.is_printed and rec.state == 'assignment':
                    rec.write({
                        'state': 'print',
                        'history_ids': [(0, 0, {
                            'state': 'print',
                            'print_state': '',
                            'date': fields.Date.today(),
                        })]
                    })
            else:
                rec.is_printed = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence_number', _('New')) == _('New'):
                # vals['sequence_number'] = self.env['ir.sequence'].next_by_code('unit.booking') or _('New')
                random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
                vals['sequence_number'] = random_num or _('New')
        return super().create(vals_list)
    

    def create_partner(self):
        return {
            'name': _('Transferee Member'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'view_id': self.env.ref('real_estate.view_partner_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                        'default_relation_name': self.transferee_relation_name,
                        'default_cnic': self.transferee_cnic_number, 'default_project_type': self.project_type,
                        'default_company_type': 'person'},
            'target': 'new'
        }

    def reset_installment_plan11(self):
        self.unit_booking_plan_ids.unlink()
        self.set_predefine_value()
        self._balloon_payment()
        self.installment_created = False

    @api.depends('name', 'category_id', 'unit_category_type_id')
    def generate_qr_code(self):
        for rec in self:
            if rec.name and rec.category_id and rec.unit_category_type_id:
                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=9,
                    border=1,
                )
                base_url = rec.env["ir.config_parameter"].get_param("web.base.url")
                '''url_params = {
                    'id': self.id,
                    'view_type': 'form',
                    'model': 'units.booking',
                    # 'menu_id': self.env.ref('module_name.menu_record_id').id,
                    'action': self.env.ref('unit_booking.action_units_booking').id,
                }'''
                params = '/booking/verification/%s' % rec.id
                url = base_url + params
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_image = base64.b64encode(temp.getvalue())
                rec.qr_code = qr_image
            else:
                rec.qr_code = False

    def prepare_next_iterator_value(self, dates, i, total_dates):
        # find the index of current date from list
        current_date_index = dates.index(dates[i])
        temp_date_list = [dates[cd] - relativedelta(months=+self.interval_id.nom) for cd in
                          range(current_date_index, len(dates))]
        # copying into original list from temporary list
        del dates
        dates = temp_date_list[1:]
        del temp_date_list[:]
        total_dates = len(dates) - 1
        i = 0
        return i, total_dates, dates

    def create_installment_plan(self):
        """
        Creating down_payment line
        """
        if not self.initial_payment:
            raise ValidationError('Please enter down payment amount.')

        self.unit_booking_plan_ids.create({
            'date': self.booking_date,
            'installment_type': 'down',
            'installment_name': 'Booking',
            'installment_number': 1,
            'amount': self.initial_payment,
            'invoice': 'Paid by Agent',
            'invoice_created': True,
            'amount_paid': self.initial_payment,
            # 'balance_amount': self.initial_payment,
            'residual': 0,
            'payment_status': 'paid',
            'units_booking_id': self.id
        })

        """ 
        confirmation payment line
        """

        if self.plan_type == 'predefine' \
                and self.env.ref('real_estate.confirmation_amount_product').id \
                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            """
            if confirmation amount is included in predefine plan than installment starting date of open file plan will 
            will be calculated from these line and if its not included then installment starting is selected from batch
            """
            confirmation_date = ((self.booking_date + relativedelta(
                months=+self.predefine_plan_id.confirmation_amount_period) - relativedelta(
                days=+self.booking_date.day)) + relativedelta(days=+1))

            self.starting_date = confirmation_date + relativedelta(months=+1)

            installment_number = 3
            self.unit_booking_plan_ids.create({
                'date': confirmation_date,
                'installment_number': 2,
                'installment_type': 'confirmation_amount',
                'installment_name': 'Confirmation',
                'payment_status': 'not_paid',
                'amount': self.confirmation_amount,
                'residual': self.confirmation_amount,
                'units_booking_id': self.id
            })
        else:
            installment_number = 2

        if self.balance_amount > 0:
            if all([self.starting_date, self.interval_id, self.total_installment]):
                start_date = self.starting_date
                dates = [fields.Date.from_string(start_date)]

                """
                temp variable for controlling conditional structure of predefine plan
                """
                interval = 0
                possession_interval = 0
                primary_interval = 0
                start_balloon_payment = False
                installment_count = 1
                balloon_interval = self.balloon_payment_interval
                """
                these variable should be true if include in installment check is true from predefine plan
                if it true then it will create two lines of installment with same date
                """
                is_balloon_included = False
                is_possession_included = False
                is_balloting_included = False

                if self.predefine_plan_id:
                    for rec in self.predefine_plan_id.predefine_plan_line_ids:
                        if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
                            self.balance_amount = self.balance_amount - (self.balloon_payment *
                                                                         self.balloon_payment_frequency)
                            if rec.include_installment:
                                is_balloon_included = True

                        if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
                            self.balance_amount = self.balance_amount - (self.possession_amount *
                                                                         self.possession_amount_frequency)
                            if rec.include_installment:
                                is_possession_included = True

                        if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
                            self.balance_amount = self.balance_amount - (self.confirmation_amount *
                                                                         self.confirmation_amount_frequency)

                        if rec.product_id.id == rec.env.ref('real_estate.balloting_product').id:
                            self.balance_amount = self.balance_amount - (self.primary_amount *
                                                                         self.primary_amount_frequency)
                            if rec.include_installment:
                                is_balloting_included = True

                    if self.predefine_plan_id.include_in_plan == 'no':
                        for rec in range(1, (self.total_installment + self.balloon_payment_frequency +
                                             self.possession_amount_frequency + self.primary_amount_frequency)):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                    else:
                        for rec in range(1, self.total_installment):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

                balance = self.balance_amount
                installment_amount = round(self.balance_amount / (
                        self.total_installment - self.balloon_payment_frequency)) if not self.include_installment and self.predefine_plan_id and self.predefine_plan_id.include_in_plan == 'yes' else round(
                    self.balance_amount / self.total_installment)

                i = 0
                total_dates = len(dates)-1
                while i <= total_dates:
                # for rec in dates:

                    if (self.balloon_payment_start and not start_balloon_payment
                            and installment_number == self.balloon_payment_start):
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.unit_booking_plan_ids.create({
                            'date': dates[i] - relativedelta(months=+self.interval_id.nom) if is_balloon_included else dates[i],
                            'installment_number': installment_number,
                            'installment_type': 'balloon',
                            'installment_name': 'Installment' + ' '+str(installment_count) if
                            self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                            'payment_status': 'not_paid',
                            'residual': amount,
                            'amount': amount,
                            'units_booking_id': self.id
                        })
                        if self.predefine_plan_id.treat_balloon_as == 'installment':
                            installment_count += 1
                        interval = interval + 1
                        balloon_interval += self.balloon_payment_start
                        start_balloon_payment = True
                        installment_number = installment_number + 1
                        if is_balloon_included:
                            i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                        else:
                            i += 1
                        continue

                    if self.plan_type == 'predefine' \
                            and self.env.ref('real_estate.possession_amount_product').id \
                            in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
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
                                self.unit_booking_plan_ids.create({
                                    'date': dates[i] - relativedelta(months=+self.interval_id.nom) if is_possession_included else dates[i],
                                    'installment_number': installment_number,
                                    'installment_type': 'possession_amount',
                                    'installment_name': 'Possession',
                                    'payment_status': 'not_paid',
                                    'residual': amount,
                                    'amount': amount,
                                    'units_booking_id': self.id
                                })
                                if is_possession_included:
                                    i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                                else:
                                    i += 1
                                possession_interval += 1
                                installment_number = installment_number + 1
                                continue

                    if self.plan_type == 'predefine' \
                            and self.env.ref('real_estate.balloting_product').id \
                            in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
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
                                self.unit_booking_plan_ids.create({
                                    'date': dates[i] - relativedelta(months=+self.interval_id.nom) if is_balloting_included else dates[i],
                                    'installment_number': installment_number,
                                    'installment_type': 'balloting_amount',
                                    'installment_name': 'Balloting',
                                    'payment_status': 'not_paid',
                                    'residual': amount,
                                    'amount': amount,
                                    'units_booking_id': self.id
                                })
                                # preparing the next date in iterator
                                if is_balloting_included:
                                    i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                                else:
                                    i += 1
                                primary_interval += 1
                                installment_number = installment_number + 1
                                continue

                    if self.plan_type == 'predefine' and self.env.ref(
                            'real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped(
                        'product_id').ids and (installment_number % balloon_interval == 0
                                and interval < self.balloon_payment_frequency and start_balloon_payment):
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.unit_booking_plan_ids.create({
                            'date': dates[i],
                            'installment_number': installment_number,
                            'installment_type': 'balloon',
                            'installment_name': 'Installment' + ' '+str(installment_count) if
                            self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                            'payment_status': 'not_paid',
                            'residual': amount,
                            'amount': amount,
                            'units_booking_id': self.id
                        })
                        # balloon payment
                        if self.predefine_plan_id.treat_balloon_as == 'installment':
                            installment_count += 1
                        interval = interval + 1
                        balloon_interval += self.balloon_payment_interval
                        installment_number = installment_number + 1
                        if is_balloon_included:
                            i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                        else:
                            i += 1
                        continue

                    elif self.plan_type == 'custom':
                        self.unit_booking_plan_ids.create({
                            'date': dates[i],
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' '+str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': installment_amount,
                            'tax_amount': 0,
                            'residual': installment_amount,
                            'units_booking_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                        i += 1

                    else:
                        self.unit_booking_plan_ids.create({
                            'date': dates[i],
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' '+str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': installment_amount,
                            'tax_amount': 0,
                            'residual': installment_amount,
                            'units_booking_id': self.id
                        })
                        # installment
                        installment_count += 1
                        installment_number = installment_number + 1
                        i += 1

                plan = self.env['unit.booking.plan'].search([('units_booking_id', '=', self.id)])
                if self.balloting_amount:
                    plan.create({
                        'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                        'installment_type': 'final',
                        'payment_status': 'not_paid',
                        'installment_number': installment_number,
                        'installment_name': 'Final',
                        'amount': self.balloting_amount,
                        'tax_amount': 0,
                        'residual': self.balloting_amount,
                        'units_booking_id': self.id
                    })
                #     final payment

                total = sum(self.unit_booking_plan_ids.mapped('amount'))
                if total < self.ttl_sale_amount:
                    price = self.ttl_sale_amount - total
                    self.unit_booking_plan_ids.search([])[-1].update({
                        'amount': round(self.balloting_amount) + price,
                        # 'balance_amount': round(self.balance_amount / self.total_installment) + price,
                        'residual': round(self.balloting_amount) + price,
                    })
                elif total > self.ttl_sale_amount:
                    price = total - self.ttl_sale_amount
                    self.unit_booking_plan_ids.search([])[-1].update({
                        'amount': round(self.balloting_amount) - price,
                        # 'balance_amount': round(self.balance_amount / self.total_installment) - price,
                        'residual': round(self.balloting_amount) - price,
                    })
                del installment_number

                self.installment_created = True
            else:
                raise ValidationError(
                    _("Installment Starting Date,Interval and total installments should be there."))

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(UnitsBooking, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                         submenu=submenu)
        is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')

        if is_user:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.set('edit', 'true')
                doc.set('create', 'false')
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


class UnitBookingHistory(models.Model):
    _name = 'unit.booking.history'
    _description = 'Open File History'

    # selection fields
    state = fields.Selection([('open', 'Open'),
                              ('assignment', 'Assignment'),
                              ('print', 'Print'),
                              ('issued', 'Issued'),
                              ('allotment', 'Allotment'),
                              ('file_created', 'File Created'),
                              ('balloting', 'Balloting')])
    print_state = fields.Selection([
        ('draft', 'Draft'),
        ('open_file', 'File'),
        ('receipt', 'Receipt'),
        ('ledger', 'Ledger')], default='draft', readonly=False)
    # date fields
    date = fields.Date()
    # relational fields
    partner_id = fields.Many2one('res.partner')
    unit_booking_id = fields.Many2one('units.booking')
    batch_id = fields.Many2one('unit.batch.generation')


class UnitBookingPlan(models.Model):
    _name = 'unit.booking.plan'

    _rec_name = 'date'
    _description = "Unit Booking Plan"

    # serial_no = fields.Integer()
    line_calculated = fields.Boolean(default=False)
    product_id = fields.Many2one('product.product',
                                 default=lambda self: self.env.ref('real_estate.installment_product').id,
                                 domain="[('is_include_property_system','=', True)]"
                                 )
    date = fields.Date(required=True)
    percentage = fields.Float(digits=(2, 6))
    amount = fields.Float()
    amount_manual = fields.Float(string='Amount ')
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
    units_booking_id = fields.Many2one('units.booking')

    # New Fields

    file_type = fields.Selection([
        ('new', 'New'),
        ('legacy', 'Legacy')
    ], default='new')
    invoice = fields.Char(related='invoice_id.name', store=True, readonly=False)

    payment_date = fields.Date('Payment Date', store=True, readonly=False)
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('installment', 'Installment'),
        ('transfer_application', 'Transfer Application'),
        ('others', 'Others'),
    ], related='invoice_id.property_invoice_type', readonly=False, string='Invoice Type')
    amount_paid = fields.Float('Amount Paid', store=True, readonly=False)
    residual = fields.Float('Amount Due', store=True, readonly=False)
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=False, copy=False, tracking=True,
        related='invoice_id.payment_state')
    double_check_paid_amount = fields.Boolean()
    investor_payment = fields.Boolean()
    tax_amount = fields.Float()
    installment_name = fields.Char()
