# -*- coding: utf-8 -*-

import base64
import random
import string
from io import BytesIO

import qrcode
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FileExtension(models.Model):
    _inherit = 'file'

    project_type = fields.Selection([('skyscraper', 'Skyscraper'), ('housing_society', 'Housing Society')],
                                    default="housing_society")
    predefine_plan_id = fields.Many2one('predefine.plan')
    custom_sale_amount = fields.Float('Sale Amount ')
    sale_amount = fields.Float('Sale Amount', store=True, readonly=False, compute='_sale_amount',
                               tracking=True)
    confirmation_invoice_created = fields.Boolean(compute="compute_confirmation_invoice")

    # Currency
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch)
    currency_id = fields.Many2one('res.currency', tracking=True, required=True,
                                  string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)
    foreign_currency = fields.Boolean()
    rate = fields.Float()
    rate_type = fields.Selection([
        ('user', 'User'),
        ('corporate', 'Corporate'),
        ('spot', 'Spot'),
    ])
    total_amount_pkr = fields.Float(string='Amount in PKR', compute="compute_pkr_total_amount", store=True)
    issuance_request_id = fields.Many2one('unit.swapping.request',
                                          string="File Issuance Request")  # File Issuance Request from which this File is being created

    # Sub Dealer
    issued_to_sub_dealer = fields.Boolean(string="Issued to Sub Dealer", tracking=True)
    sub_investor_id = fields.Many2one('res.investor', string="Sub Investor", tracking=True)
    issuance_history_ids = fields.One2many('open.file.issuance.history', 'file_id', tracking=True)
    payment_completion_percentage = fields.Float(string='Payment Completion(%)', store=True, tracking=True)
    payment_completion_date = fields.Date(string="Payment Completion Date", store=True, tracking=True)
    total_paid_amount = fields.Float(string='Total Paid Amount', store=True, tracking=True)
    e_signature_link = fields.Char(string="E Signature Link", default=False, tracking=True)
    development_charges_included = fields.Selection(
        string='Development Charges Included',
        selection=[('yes', 'Yes'), ('no', 'no')],
        default="yes",
        tracking=True)
    with_note = fields.Boolean(string='With Note', default=False, tracking=True)
    # sale_price_tye = fields.Selection([('sale_price', 'Sale Price'), ('')])


    @api.depends('installment_plan_ids.residual')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_payment = sum(rec.installment_plan_ids.mapped('residual'))
            rec.total_paid_amount = total_amount_paid = sum(rec.installment_plan_ids.mapped('amount_paid'))
            rec.payment_completion_percentage = (total_amount_paid / rec.net_sale_amount) * 100 if total_amount_paid > 0 else 0
            if rec.payment_completion_percentage == 100.00:
                rec.payment_completion_date = fields.Date.today()

    def compute_pkr_total_amount(self):
        for rec in self:
            if rec.currency_id.id != self.env.company.currency_id.id:
                rec.total_amount_pkr = rec.net_sale_amount * rec.rate
            else:
                rec.total_amount_pkr = rec.net_sale_amount

    @api.onchange('currency_id', 'rate_type')
    def onchange_currency_id(self):
        for rec in self:
            if rec.currency_id != rec.env.company.currency_id:
                rec.foreign_currency = True
                # rec.rate = self.env.company.currency_id.rate / self.currency_id.rate
            else:
                rec.foreign_currency = False
                rec.rate = 0.00

    def generate_qr_for_all_company_wise(self):
        for rec in self.search([('society_id.company_id', '!=', 1)]):
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )

            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            params = '/file/verification/%s' % (rec.id)
            url = base_url + params
            data = rec.tracking_id + '/' + rec.name
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image

    def compute_confirmation_invoice(self):
        for rec in self:
            confirmation_exist = False
            rec.confirmation_invoice_created = False
            if rec.installment_plan_ids:
                for lines in rec.installment_plan_ids:
                    # if lines.installment_name == 'Confirmation' and lines.invoice_created == True:
                    if lines.installment_name == 'Confirmation':
                        confirmation_exist = True
                        if lines.invoice_created:
                            rec.confirmation_invoice_created = True
            if not confirmation_exist:
                rec.confirmation_invoice_created = True

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
                    for rec in recs.price_list_id.pricelist_line:
                        if recs.price_list_id.price_list_type == 'unit':
                            if (rec.size_id == recs.size_id
                                    and rec.category_id == recs.category_id
                                    and rec.sector_id == recs.sector_id
                                    and rec.unit_inventory_id == recs.inventory_id
                                    and rec.starting_date <= recs.booking_date <= rec.end_date):
                                if recs.ttl_sale_amount:
                                    recs.ttl_sale_amount = recs.ttl_sale_amount
                                else:
                                    recs.sale_amount = rec.price
                                    recs.ttl_sale_amount = recs.sale_amount

                            elif (rec.size_id == recs.size_id
                                  and rec.category_id == recs.category_id
                                  and rec.sector_id == recs.sector_id
                                  and rec.unit_inventory_id == recs.inventory_id
                                  and rec.starting_date <= recs.booking_date <= rec.end_date):
                                if recs.ttl_sale_amount:
                                    recs.ttl_sale_amount = recs.ttl_sale_amount
                                else:
                                    recs.sale_amount = rec.price
                                    recs.ttl_sale_amount = recs.sale_amount

                        if recs.price_list_id.price_list_type == 'sq_ft' and recs.pricing_policy == 'area':
                            if (rec.size_id == recs.size_id and rec.category_id == recs.category_id
                                    and rec.sector_id == recs.sector_id
                                    and rec.unit_inventory_id == recs.inventory_id
                                    and rec.starting_date <= recs.booking_date <= rec.end_date):
                                if recs.rate_sq_ft:
                                    recs.sale_amount = recs.rate_sq_ft * recs.covered_area
                                    recs.ttl_sale_amount = recs.sale_amount
                                else:
                                    recs.rate_sq_ft = rec.price
                                    recs.sale_amount = recs.rate_sq_ft * rec.area
                                    recs.ttl_sale_amount = recs.sale_amount

                            elif (rec.category_id == recs.category_id
                                  and rec.sector_id == recs.sector_id
                                  and rec.unit_inventory_id == recs.inventory_id
                                  and rec.starting_date <= recs.booking_date <= rec.end_date):
                                if recs.rate_sq_ft:
                                    recs.sale_amount = recs.rate_sq_ft * recs.covered_area
                                    recs.ttl_sale_amount = recs.sale_amount
                                else:
                                    recs.rate_sq_ft = rec.price
                                    recs.sale_amount = recs.rate_sq_ft * rec.area
                                    recs.ttl_sale_amount = recs.sale_amount
                        else:
                            if (rec.category_id == recs.category_id
                                    and rec.sector_id == recs.sector_id
                                    and rec.unit_category_type_id == recs.unit_category_type_id):
                                if recs.ttl_sale_amount:
                                    recs.ttl_sale_amount = recs.ttl_sale_amount
                                    recs.sale_amount = recs.ttl_sale_amount
                                else:
                                    recs.sale_amount = rec.price
                                    recs.ttl_sale_amount = recs.sale_amount

                    factor = 0
                    for rec in recs.preference_ids:
                        if recs.crm_id or recs.token_id:
                            rec.total = (recs.sale_amount * rec.value) / 100
                            if recs.ttl_sale_amount and rec.approved:
                                recs.ttl_sale_amount = recs.ttl_sale_amount + rec.total
                            else:
                                recs.ttl_sale_amount = recs.sale_amount
                            recs.factor_amount = round(rec.total) if rec.approved else 0
                        elif rec.approved and rec.basis == 'fix':
                            factor = factor + rec.value
                            recs.factor_amount = factor
                            if recs.ttl_sale_amount:
                                recs.ttl_sale_amount = recs.ttl_sale_amount
                            else:
                                recs.ttl_sale_amount = recs.sale_amount + factor
                        elif rec.approved and rec.basis == 'percentage':
                            factor = factor + (recs.sale_amount * rec.value) / 100
                            recs.factor_amount = factor
                            if recs.ttl_sale_amount and rec.approved:
                                recs.ttl_sale_amount = recs.sale_amount + factor
                            else:
                                recs.ttl_sale_amount = recs.sale_amount
                        else:
                            recs.factor_amount = 0.0
                            recs.ttl_sale_amount = recs.sale_amount
                else:
                    recs.sale_amount = 0.0
                    recs.factor_amount = 0.0

    @api.onchange('predefine_plan_id', 'custom_sale_amount', 'sale_amount')
    def _balloon_payment(self):
        # for recs in self:
        if self.predefine_plan_id:
            # for setting the starting date of installment plan after confirmation
            # if self.env.ref('real_estate.confirmation_amount_product').id in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            #     if self.predefine_plan_id.confirmation_period_type == 'days':
            #         datee = self.booking_date + relativedelta(days=+self.predefine_plan_id.confirmation_amount_period)
            #         self.starting_date = datee.replace(day=1) + relativedelta(months=+1)
            #         # self.starting_date = self.booking_date + relativedelta(days=+self.predefine_plan_id.confirmation_amount_period + 1)
            #     if self.predefine_plan_id.confirmation_period_type == 'months':
            #         self.starting_date = self.booking_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period + 1)
            #     if self.predefine_plan_id.confirmation_period_type == 'years':
            #         self.starting_date = self.booking_date + relativedelta(years=+self.predefine_plan_id.confirmation_amount_period + 1)
            self.starting_date = self.investor_file.starting_date
            for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:

                if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    self.initial_payment = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                if self.env.ref('real_estate.installment_product').id == pre_plan.product_id.id:
                    self.installment_amount = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                if self.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                    self.balloting_amount = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                if self.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                    self.balloon_payment = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                    self.balloon_payment_interval = pre_plan.interval
                    self.balloon_payment_frequency = pre_plan.frequency
                    self.balloon_payment_start = pre_plan.start_from
                    self.include_installment = pre_plan.include_installment

                if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    self.possession_amount = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                    self.possession_amount_interval = pre_plan.interval
                    self.possession_amount_frequency = pre_plan.frequency

                if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    self.confirmation_amount = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                    self.confirmation_amount_interval = pre_plan.interval
                    self.confirmation_amount_frequency = pre_plan.frequency

                if self.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                    self.primary_amount = round(self.sale_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                    self.primary_amount_interval = pre_plan.interval
                    self.primary_amount_frequency = pre_plan.frequency

    def create_confirmation_invoice(self):
        if not self.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').invoice_created:
            confirmation_product = self.env.ref('real_estate.confirmation_amount_product')
            _conf_pp = confirmation_product.product_id if confirmation_product._name == 'product.realestate' else confirmation_product
            if self.confirmation_amount:
                prod = [(0, 0, {
                    'product_id': _conf_pp.id,
                    'name': confirmation_product.name,
                    'account_id': _conf_pp.property_account_income_id.id,
                    # 'price_unit': rec.value if rec.payment_type == 'fix' else [self.sale_amount * rec.value / 100][0]
                    'price_unit': self.confirmation_amount,
                    # 'is_fully_paid': rec.is_fully_paid
                })]
                invoice = self.env['account.move'].create({
                    # 'file_ids': self.id,
                    # this id is just for invoice create method i will extract this field from there and push remaining values
                    # 'invoice_payment_ref': self.name,
                    'move_type': 'out_invoice',
                    'user_id': self.user_id.id,
                    'partner_id': self.membership_id.id,
                    'currency_id': self.currency_id.id,
                    # 'branch_id': self.env.branch.id,
                    # 'account_id': self.membership_id.property_account_receivable_id.id,
                    'property_invoice_type': 'confirmation_amount',
                    'date': self.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').date,
                    'invoice_date': self.installment_plan_ids.filtered(
                        lambda l: l.installment_name == 'Confirmation').date,
                    # 'invoice_date_due': self.booking_date,
                    'invoice_line_ids': prod
                })
                invoice.file_ids = self.id
                invoice.action_post()
                self.installment_plan_ids.filtered(
                    lambda l: l.installment_name == 'Confirmation').invoice_id = invoice.id
                self.installment_plan_ids.filtered(
                    lambda l: l.installment_name == 'Confirmation').invoice_created = True

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
        if self.balance_amount == 0 and self.balloting_amount == 0:
            raise ValidationError('You cannot create plan with zero "Balance Amount".')

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
            """
            these variable should be true if include in installment check is true from predefine plan
            if it true then it will create two lines of installment with same date
            """
            is_balloon_included = False
            is_possession_included = False
            is_balloting_included = False

            if self.predefine_plan_id:
                for rec in self.predefine_plan_id.predefine_plan_line_ids:
                    if rec.product_id.id == self.env.ref('real_estate.balloon_payment').id:
                        interval_limit = round(self.total_installment / self.balloon_payment_interval)
                        self.balance_amount = self.balance_amount - (self.balloon_payment *
                                                                     self.balloon_payment_frequency)
                        if rec.include_installment:
                            is_balloon_included = True
                    if rec.product_id.id == self.env.ref('real_estate.possession_amount_product').id:
                        self.balance_amount = self.balance_amount - (self.possession_amount *
                                                                     self.possession_amount_frequency)
                        if rec.include_installment:
                            is_possession_included = True
                    if rec.product_id.id == self.env.ref('real_estate.confirmation_amount_product').id:
                        self.balance_amount = self.balance_amount - (self.confirmation_amount *
                                                                     self.confirmation_amount_frequency)
                    if rec.product_id.id == self.env.ref('real_estate.balloting_product').id:
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
                if self.investment_id:
                    dates = [fields.Date.from_string(
                        self.installment_plan_ids.filtered(lambda l: l.invoice_created)[-1].date + relativedelta(
                            months=+self.interval_id.nom)) if self.installment_plan_ids.filtered(
                        lambda l: l.invoice_created) else fields.Date.from_string(
                        self.starting_date)]
                    # for rec in range(1, self.investment_id.remaining_installments):
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

            balance = self.balance_amount
            amount = 0

            # Commented

            if self.initial_payment and self.type == 'normal':
                self.installment_plan_ids.create({
                    # 'date': self.booking_date + relativedelta(days=+self.grace_period),
                    'date': self.booking_date,
                    'installment_type': 'down',
                    'installment_name': 'Booking',
                    'installment_number': 1,
                    'amount': self.initial_payment,
                    'tax_amount': round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else 0,
                    'residual': self.initial_payment + round((self.initial_payment * tax_id[0].amount) / 100,
                                                             2) if tax_id else self.initial_payment,
                    'payment_status': 'not_paid',
                    'file_id': self.id
                })

            if (self.plan_type == 'predefine'
                    and self.env.ref('real_estate.confirmation_amount_product').id
                    in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                installment_number = 3
                if confirmation_interval < self.confirmation_amount_frequency:
                    confirmation_date = self.booking_date
                    if self.predefine_plan_id.confirmation_period_type == 'days':
                        confirmation_date = self.booking_date + relativedelta(
                            days=+self.predefine_plan_id.confirmation_amount_period)
                    if self.predefine_plan_id.confirmation_period_type == 'months':
                        confirmation_date = self.booking_date + relativedelta(
                            months=+self.predefine_plan_id.confirmation_amount_period)
                    if self.predefine_plan_id.confirmation_period_type == 'years':
                        confirmation_date = self.booking_date + relativedelta(
                            years=+self.predefine_plan_id.confirmation_amount_period)
                    self.installment_plan_ids.create({
                        'date': confirmation_date,
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

            installment_amount = round(
                self.balance_amount / (self.total_installment - self.balloon_payment_frequency)
            ) if not self.include_installment and self.predefine_plan_id and self.predefine_plan_id.include_in_plan == 'yes' else round(
                self.balance_amount / self.total_installment)
            i = 0
            total_dates = len(dates) - 1
            while i <= total_dates:
                # for rec in dates:
                # first balloon payment
                if self.balloon_payment_start and not start_balloon_payment:
                    if installment_number == self.balloon_payment_start:
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.installment_plan_ids.create({
                            # 'date': rec,
                            'date': dates[i] - relativedelta(months=+self.interval_id.nom) if is_balloon_included else
                            dates[i],
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
                        balloon_interval += self.balloon_payment_start
                        start_balloon_payment = True
                        installment_number = installment_number + 1
                        if is_balloon_included:
                            i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                        else:
                            i += 1
                        continue
                # for recs in self.predefine_plan_id.predefine_plan_line_ids:
                if (self.plan_type == 'predefine'
                        and self.env.ref('real_estate.possession_amount_product').id
                        in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                    if self.total_installment > 1:
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
                                    # 'date': rec,
                                    'date': dates[i] - relativedelta(
                                        months=+self.interval_id.nom) if is_possession_included else dates[i],
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
                                if is_possession_included:
                                    i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                                else:
                                    i += 1
                                continue
                    else:
                        if installment_count in (2, 3):
                            amount = self.possession_amount
                            self.installment_plan_ids.create({
                                # 'date': rec,
                                'date': dates[i] - relativedelta(
                                    months=+self.interval_id.nom) if is_possession_included else dates[i],
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
                            i += 1
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
                                # 'date': rec,
                                'date': dates[i] - relativedelta(
                                    months=+self.interval_id.nom) if is_balloting_included else dates[i],
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
                            # preparing the next date in iterator
                            if is_balloting_included:
                                i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                            else:
                                i += 1
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
                        # 'date': rec,
                        'date': dates[i],
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
                    if is_balloon_included:
                        i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                    else:
                        i += 1
                    continue
                elif self.plan_type == 'custom' and not self.investment_id:
                    self.installment_plan_ids.create({
                        # 'date': rec,
                        'date': dates[i],
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
                    i += 1
                elif self.investment_id:
                    if self.investment_id.options == 'down' and self.investment_id.remaining_installments > 0:
                        installment_number = self.installment_plan_ids[-1].installment_number + 1
                        paid_installments = (
                                                    self.total_installment - self.investment_id.remaining_installments) * round(
                            self.balance_amount / self.total_installment)
                        amount = round(
                            (self.balance_amount - paid_installments) / self.investment_id.remaining_installments)
                        self.installment_plan_ids.create({
                            # 'date': rec,
                            'date': dates[i],
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
                        i += 1
                else:
                    self.installment_plan_ids.create({
                        # 'date': rec,
                        'date': dates[i],
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
                    i += 1

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
                if total < self.net_sale_amount:
                    price = self.net_sale_amount - total
                    self.installment_plan_ids.search([])[-1].update({
                        'amount': self.installment_plan_ids.search([])[-1].amount + price,
                        'residual': self.installment_plan_ids.search([])[-1].residual + price
                    })
                elif total > self.net_sale_amount:
                    price = total - self.net_sale_amount
                    self.installment_plan_ids.search([])[-1].update({
                        'amount': self.installment_plan_ids.search([])[-1].amount - price,
                        'residual': self.installment_plan_ids.search([])[-1].amount - price
                    })
            self.installment_created = True
        #     Commented Code Ends Here
        else:
            raise ValidationError(
                _("Installment Starting Date,Interval and total installments sould be there for active files"))

    def reset_installment_plan(self):
        if len(self.installment_plan_ids.filtered(
                lambda l: l.installment_name not in ['Booking', 'Down Payment']).mapped('invoice_id.id')) > 1:
            raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        else:
            for lines in self.installment_plan_ids:
                if lines.installment_name in ('Booking', 'Down Payment'):
                    if lines.payment_status in ('not_paid', 'cancel'):
                        self.installment_plan_ids.unlink()
                        break
                if lines.installment_name not in ('Booking', 'Down Payment'):
                    lines.unlink()
        # self.installment_plan_ids.unlink()
        self.installment_created = False
        # if len(self.installment_plan_ids.mapped('invoice_id').ids) > 1:
        #     raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        # self.installment_plan_ids.unlink()
        # self.installment_created = False

    def approve(self):
        confirmation_exist = False
        confirmation_invoice_paid = False
        if self.no_of_invoices < 1 and self.type == 'normal':
            raise ValidationError("Please generate initial invoice first.")
        if self.payment_states == 'draft':
            raise ValidationError("Please pay the down payment invoice.")
        if self.installment_plan_ids:
            for lines in self.installment_plan_ids:
                if lines.installment_name == 'Confirmation':
                    confirmation_exist = True
                    if lines.payment_status == 'paid':
                        confirmation_invoice_paid = True
        if not confirmation_invoice_paid and confirmation_exist:
            raise ValidationError('Please Pay your Confirmation Invoice First..')
        self.file_status = 'approve'

    def lock(self):
        self.file_status = 'lock'
        self.inventory_id.state = 'sold'
        if not self.installment_plan_ids and self.payment_type != 'lump_sum' and self.balance_amount != 0:
            raise ValidationError("Please create installment plan first.")
        # self.file_status = 'lock'
        random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # if self.society_id.company_id.id != "New City Housing Project":
        if self.env.company.id != 1:
            self.name = random_num
            message = f"Dear {self.membership_id.name} Please note that your File No. {self.name} has been created, Category: {self.unit_category_type_id.name} {self.category_id.name} \nThank You For " \
                      f"Your Trust.\nBest Regards,\nNew City Paradise"
            number = self.membership_id.mobile
            #self.env['tools.mixin'].sudo().simple_send(message, number)
        existing_record = self.env['print.queue'].search([
            ('document_type', '=', 'file'),
            ('allotment', '=', 'new'),
            ('transaction_ref', '=', self.name),
            ('member_ids', 'in', self.membership_id.ids),
            ('files_ids', 'in', self.ids)
        ], limit=1)
        if not existing_record:
            for rec in self:
                self.env['print.queue'].create({
                    'document_type': 'file',
                    'allotment': 'new',
                    'transaction_ref': rec.name,
                    # 'transfer_application_id': self.id,
                    'member_ids': [(6, 0, rec.membership_id.ids)],
                    'files_ids': [(6, 0, rec.ids)]
                })
        # for rec in self:
        #     self.env['print.queue'].create({
        #         'document_type': 'file',
        #         'allotment': 'new',
        #         'transaction_ref': rec.name,
        #         # 'transfer_application_id': self.id,
        #         'member_ids': [(6, 0, rec.membership_id.ids)],
        #         'files_ids': [(6, 0, rec.ids)]
        #     })

    def set_installment_plan_data_residual(self):
        for rec in self.installment_plan_ids:
            rec.residual = rec.invoice_id.amount_residual if rec.invoice_id else rec.amount - rec.amount_paid

    def set_installment_plan_data_residual_for_all(self):
        installment_lines = self.env['installment.plan'].search(
            [('file_id.society_id.company_id.id', '=', 5), ('file_id', '!=', False)])
        for rec in installment_lines:
            rec.residual = rec.invoice_id.amount_residual if rec.invoice_id else rec.amount - rec.amount_paid


class AllotmentDetailsExt(models.Model):
    _inherit = 'allotment.details'
    _description = 'Allotment Details'

    transaction_type = fields.Selection(selection_add=[
        ('membership', 'File Membership Form'),
        ('installment_plan', 'File Installment Plan'),
        ('greeting_letter', 'File Greeting Letter'),
        ('booking_receipt', 'Booking Receipt'),
        ('confirmation_receipt', 'Confirmation Receipt'),
        ('return', 'Return')
    ])
    remarks = fields.Char()
    printing_request_id = fields.Many2one('print.documents')
