import qrcode
import base64
from io import BytesIO
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import dateutil.parser
from lxml import etree as ET
import random
import string


class InvestorFileExt(models.Model):
    _inherit = 'investor.file'

    type = fields.Selection([
        ('normal', 'Normal'),
        ('gift', 'Gift'),
        ('in_lieu', 'In Lieu'),
        ('investor', 'Investor'),
    ], default='normal')  # Added this field for actual file type
    include_installment = fields.Boolean()

    reset_installment_plan = fields.Selection([('yes', 'Yes'), ('no', 'No')], readonly=False, tracking=True,
                                              default='no')
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
    balance_amount = fields.Float('Balance Amount', compute='_compute_balance_amount', readonly=True)
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

    # created for product 'Additional Balloon', used in installment creation
    add_balloon_amount = fields.Float(string='Additional Balloon Amount')
    add_balloon_interval = fields.Integer(string='Additional Balloon Interval')
    add_balloon_frequency = fields.Integer(string='Additional Balloon Frequency')

    is_add_balloon_included = fields.Boolean(string='Additional Balloon')

    installment_plan_ids = fields.One2many('installment.plan', 'investor_file_id', tracking=True)
    installment_created = fields.Boolean(default=False)
    installment_tax_ids = fields.Many2many('account.tax')
    grace_period = fields.Integer()
    # Rebate Option
    rebate_amount = fields.Float()
    sale_rebate = fields.Float()
    is_sale_rebate_applied = fields.Boolean(default=False)
    # Journal Entry
    move_id = fields.Many2one('account.move', tracking=True)
    rebate_invoice_ids = fields.Many2many('account.move', tracking=True, string="Rebate Invoices")
    rebate_invoices_created = fields.Boolean(default=False, tracking=True)

    qr_code = fields.Binary("QR Code", compute='generate_qr_code', attachment=True, store=True)
    file_id = fields.Many2one('file', string="File #")  # When File is Created, It's ID will be passed in this field for cross-referencing
    state = fields.Selection([
        ('open', 'Open'),
        ('selected', 'Selected'),
        ('in_process', 'In Process'),
        ('issued', 'File Created'),
        ('file_printed', 'File Printed'),
        ('delivered', 'Delivered'),
        ('received', 'Received'),
        ('cancel', 'Cancelled'),
    ], default='open')
    # state = fields.Selection(selection_add=[('delivered', 'Delivered'), ('received', 'Received')])
    history_ids = fields.One2many('open.file.history', 'investor_file_id', tracking=True)

    issuance_request_created = fields.Boolean(string="Request Created", tracking=True)
    issuance_request_id = fields.Many2one('unit.swapping.request', string="Issuance Request #", tracking=True)

    # Sub Dealer
    issued_to_sub_dealer = fields.Boolean(string="Issued to Sub Dealer", tracking=True)
    sub_investor_id = fields.Many2one('res.investor', string="Sub Investor", tracking=True)
    issuance_history_ids = fields.One2many('open.file.issuance.history', 'investor_file_id', tracking=True)
    development_charges_included = fields.Selection(
        string='Development Charges Included',
        selection=[('yes', 'Yes'), ('no', 'no')],
        default="yes",
        tracking=True)

    @api.depends('name', 'active')
    def generate_qr_code(self):
        for rec in self:
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
            params = '/open/file/verification/%s' % rec.id
            url = base_url + params
            data = str(rec.id) + '/' + rec.name
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
            params = '/open/file/verification/%s' % (rec.id)
            url = base_url + params
            data = rec.id + '/' + rec.name
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image

    @api.depends('installment_plan_ids.residual')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_payment = sum(rec.installment_plan_ids.mapped('residual'))

    def compute_rebate_amount(self):
        for rec in self:
            for lines in rec.installment_plan_ids:
                if lines.installment_type == 'down':
                    marketing_share = 0
                    dealer_share = 0
                    if rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'marketing_company' and
                                                                                    l.transaction_type == 'booking'):
                        marketing_share = rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'marketing_company' and
                                                                                                       l.transaction_type == 'booking')
                        lines.marketing_share = (marketing_share.total_rebate / 100) * rec.net_sale_amount if marketing_share.calculation_basis == 'percentage' else\
                            marketing_share.total_rebate
                    if rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'dealer' and
                                                                                    l.transaction_type == 'booking'):
                        dealer_share = rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'dealer' and
                                                                                                    l.transaction_type == 'booking')
                        lines.dealer_share = (dealer_share.total_rebate / 100) * rec.net_sale_amount if dealer_share.calculation_basis == 'percentage' else\
                            dealer_share.total_rebate
                    lines.rebate_amount = lines.marketing_share + lines.dealer_share
                if lines.installment_type == 'confirmation_amount':
                    marketing_share = 0
                    dealer_share = 0
                    if rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'marketing_company' and
                                                                                    l.transaction_type == 'confirmation'):
                        marketing_share = rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'marketing_company' and
                                                                                                       l.transaction_type ==
                                                                                                       'confirmation')
                        lines.marketing_share = (marketing_share.total_rebate / 100) * rec.net_sale_amount if marketing_share.calculation_basis == 'percentage' else \
                            marketing_share.total_rebate
                    if rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'dealer' and
                                                                                    l.transaction_type == 'confirmation'):
                        dealer_share = rec.investment_id.rebate_on_allotment_ids.filtered(lambda l: l.agent_type == 'dealer' and
                                                                                                    l.transaction_type ==
                                                                                                    'confirmation')
                        lines.dealer_share = (dealer_share.total_rebate / 100) * rec.net_sale_amount if dealer_share.calculation_basis == 'percentage' else \
                            dealer_share.total_rebate
                    lines.rebate_amount = lines.marketing_share + lines.dealer_share

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
            if rec.plan_type == 'predefine' and rec.predefine_plan_id:
                rec.plan_description = rec.predefine_plan_id.name
                rec.interval_id = rec.predefine_plan_id.interval_id.id
                rec.total_installment = rec.predefine_plan_id.total_installment

    @api.onchange('predefine_plan_id', 'sale_amount')
    def _balloon_payment(self):
        for recs in self:
            if recs.predefine_plan_id:
                # for setting the starting date of installment plan after confirmation
                if self.env.ref('real_estate.confirmation_amount_product').id \
                        in recs.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                    pass
                    ## Commented code as it changes the start Date in investor file
                    # if recs.predefine_plan_id.confirmation_period_type == 'days':
                    #     recs.starting_date = recs.booking_date + relativedelta(days=+recs.predefine_plan_id.confirmation_amount_period + 1)
                    # if recs.predefine_plan_id.confirmation_period_type == 'months':
                    #     recs.starting_date = recs.booking_date + relativedelta(months=+recs.predefine_plan_id.confirmation_amount_period + 1)
                    # if recs.predefine_plan_id.confirmation_period_type == 'years':
                    #     recs.starting_date = recs.booking_date + relativedelta(years=+recs.predefine_plan_id.confirmation_amount_period + 1)
                for pre_plan in recs.predefine_plan_id.predefine_plan_line_ids:
                    if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                        recs.initial_payment = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if self.env.ref('real_estate.installment_product').id == pre_plan.product_id.id:
                        recs.installment_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if self.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                        recs.balloting_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if self.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                        recs.balloon_payment = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.balloon_payment_interval = pre_plan.interval
                        recs.balloon_payment_frequency = pre_plan.frequency
                        recs.balloon_payment_start = pre_plan.start_from
                        recs.include_installment = pre_plan.include_installment

                    # for product 'Additional Balloon' used in predefined plan
                    if self.env.ref("real_estate.additional_balloon").id == pre_plan.product_id.id:
                        recs.add_balloon_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.add_balloon_interval = pre_plan.interval
                        recs.add_balloon_frequency = pre_plan.frequency

                    if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                        recs.possession_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.possession_amount_interval = pre_plan.interval
                        recs.possession_amount_frequency = pre_plan.frequency

                    if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                        recs.confirmation_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.confirmation_amount_interval = pre_plan.interval
                        recs.confirmation_amount_frequency = pre_plan.frequency

                    if self.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                        recs.primary_amount = round(recs.sale_amount * (
                                pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.primary_amount_interval = pre_plan.interval
                        recs.primary_amount_frequency = pre_plan.frequency

                    if self.payment_type == 'lump_sum' and self.env.ref('real_estate.lump_sum_product').id == pre_plan.product_id.id:
                        recs.installment_amount = round(recs.sale_amount)

    # @api.onchange('total_installment')
    # def change_other_payments_intervals(self):
    #     if self.total_installment == 1:
    #         self.confirmation_amount_interval = 2
    #         if self.env.ref("real_estate.balloting_product").id in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
    #             self.primary_amount_interval = 4
    #             self.possession_amount_interval = 5
    #         else:
    #             self.primary_amount_interval = 0
    #             self.possession_amount_interval = 4

    def reset_open_file_installment_plan(self):
        if len(self.installment_plan_ids.filtered(lambda l: l.installment_name not in ['Booking']).mapped('invoice_id.id')) > 1:
            raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        else:
            for lines in self.installment_plan_ids:
                if lines.installment_name in ('Booking', 'Booking Payment'):
                    if lines.payment_status in ('not_paid', 'cancel'):
                        self.installment_plan_ids.unlink()
                        break
                if lines.installment_name not in ('Booking', 'Booking Payment'):
                    lines.unlink()
        # self.installment_plan_ids.unlink()
        self.installment_created = False

    @api.onchange('reset_installment_plan')
    def remove_installment_details(self):
        if self.reset_installment_plan == 'yes':
            self.plan_type = 'custom'
            self.predefine_plan_id = False
            self.interval_id = False
            self.balloting_amount = 0
            self.primary_amount = 0
            self.confirmation_amount = 0
            self.possession_amount = 0
            self.primary_amount_frequency = 0
            self.primary_amount_interval = 0
            self.confirmation_amount_frequency = 0
            self.confirmation_amount_interval = 0
            self.possession_amount_frequency = 0
            self.possession_amount_interval = 0
            self.add_balloon_amount = 0
            self.add_balloon_interval = 0
            self.add_balloon_frequency = 0
            self._compute_balance_amount()

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
        if self.installment_tax_ids:
            tax_id = self.installment_tax_ids
        else:
            tax_id = self.env.company.installment_tax_ids
        if self.payment_type == 'installments':
            if self.balance_amount == 0 and self.balloting_amount == 0:
                raise ValidationError('You cannot create plan with zero "Balance Amount".')

            # Clear lines that are neither invoiced nor paid before regenerating,
            # so re-running the plan does not duplicate them
            existing = self.installment_plan_ids.filtered(
                lambda l: not l.invoice_created and l.payment_status not in ('in_payment', 'paid'))
            if existing:
                existing.unlink()
            self.installment_created = False

            if all([self.starting_date, self.interval_id, self.total_installment, self.net_sale_amount]) and self.active:
                dates = [fields.Date.from_string(self.starting_date)]

                interval = 0
                possession_interval = 0
                add_balloon_interval = 0
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
                is_final_payment_included = False

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

                        # As defined for other products, also set for 'Additional Product'
                        if rec.product_id.id == self.env.ref('real_estate.additional_balloon').id:
                            self.balance_amount = self.balance_amount - (self.add_balloon_amount *
                                                                         self.add_balloon_frequency)
                            if rec.include_installment:
                                is_add_balloon_included = True

                        if rec.product_id.id == self.env.ref('real_estate.confirmation_amount_product').id:
                            self.balance_amount = self.balance_amount - (self.confirmation_amount *
                                                                         self.confirmation_amount_frequency)
                        if rec.product_id.id == self.env.ref('real_estate.balloting_product').id:
                            self.balance_amount = self.balance_amount - (self.primary_amount *
                                                                         self.primary_amount_frequency)
                            if rec.include_installment:
                                is_balloting_included = True
                    if self.predefine_plan_id.include_in_plan == 'no':
                        # Used for total installment.plan dates calculation. Also included "additional balloon" frequency
                        for rec in range(1, (self.total_installment + self.balloon_payment_frequency +
                                             self.possession_amount_frequency + self.primary_amount_frequency + self.add_balloon_frequency)):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                    else:
                        for rec in range(1, self.total_installment):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    if self.investment_id:
                        dates = [fields.Date.from_string(
                            self.installment_plan_ids.filtered(lambda l: l.invoice_created)[-1].date + relativedelta(
                                months=+self.interval_id.nom)) if self.installment_plan_ids.filtered(lambda l: l.invoice_created) else fields.Date.from_string(
                            self.starting_date)]
                        # for rec in range(1, self.investment_id.remaining_installments):
                        for rec in range(1, self.total_installment):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                    else:
                        for rec in range(1, self.total_installment):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

                balance = self.balance_amount
                amount = 0

                # if self.initial_payment and self.type == 'normal':
                #     self.installment_plan_ids.create({
                #         'date': self.booking_date + relativedelta(days=+self.grace_period),
                #         'installment_type': 'down',
                #         'installment_name': 'Booking',
                #         'installment_number': 1,
                #         'amount': self.initial_payment,
                #         'tax_amount': round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else 0,
                #         'residual': self.initial_payment + round((self.initial_payment * tax_id[0].amount) / 100,
                #                                                  2) if tax_id else self.initial_payment,
                #         'payment_status': 'not_paid',
                #         'investor_file_id': self.id
                #     })
                if self.initial_payment and self.type == 'normal':
                    if not self.installment_plan_ids or self.installment_plan_ids[0].payment_status not in ('in_payment', 'paid'):
                        if self.investment_id.investment_plan_ids and self.investment_id.investment_plan_ids[0].payment_status in ('in_payment', 'paid'):
                            self.installment_plan_ids.create({
                                'date': self.booking_date + relativedelta(days=+self.grace_period),
                                'payment_date': self.booking_date,
                                'installment_name': 'Booking',
                                'installment_type': 'down',
                                # 'invoice': 'Paid By Investor',
                                'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
                                # 'invoice_created': True,
                                # 'investor_payment': True,
                                'installment_number': 1,
                                'amount': self.initial_payment,
                                'amount_paid': self.initial_payment,
                                'residual': 0,
                                'payment_status': 'paid',
                                'investor_file_id': self.id
                            })
                            # self.installment_plan_ids.create({
                            #     'date': self.booking_date + relativedelta(days=+self.grace_period),
                            #     'payment_date': self.booking_date,
                            #     'installment_name': 'Booking',
                            #     'installment_type': 'down',
                            #     # 'invoice': 'Paid By Investor',
                            #     # 'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
                            #     # 'invoice_created': True,
                            #     # 'investor_payment': True,
                            #     'installment_number': 1,
                            #     'amount': self.initial_payment,
                            #     # 'amount_paid': self.initial_payment,
                            #     # 'residual': 0,
                            #     'payment_status': 'not_paid',
                            #     'investor_file_id': self.id
                            # })
                        else:
                            # self.installment_plan_ids.create({
                            #     'date': self.booking_date + relativedelta(days=+self.grace_period),
                            #     'installment_type': 'down',
                            #     'installment_name': 'Booking',
                            #     'installment_number': 1,
                            #     'amount': self.initial_payment,
                            #     'tax_amount': round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else 0,
                            #     'residual': self.initial_payment + round((self.initial_payment * tax_id[0].amount) / 100,
                            #                                              2) if tax_id else self.initial_payment,
                            #     'payment_status': 'not_paid',
                            #     'investor_file_id': self.id
                            # })
                            self.installment_plan_ids.create({
                                'date': self.booking_date + relativedelta(days=+self.grace_period),
                                'payment_date': self.booking_date,
                                'installment_name': 'Booking',
                                'installment_type': 'down',
                                # 'invoice': 'Paid By Investor',
                                'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
                                # 'invoice_created': True,
                                # 'investor_payment': True,
                                'installment_number': 1,
                                'amount': self.initial_payment,
                                'tax_amount': round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else 0,
                                'residual': self.initial_payment + round((self.initial_payment * tax_id[0].amount) / 100, 2) if tax_id else self.initial_payment,
                                'payment_status': 'not_paid',
                                'investor_file_id': self.id
                            })
                    # else:
                    #     pass

                if (self.plan_type == 'predefine'
                        and self.env.ref('real_estate.confirmation_amount_product').id
                        in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                    installment_number = 3
                    if confirmation_interval < self.confirmation_amount_frequency:
                        confirmation_date = self.booking_date
                        if self.predefine_plan_id.confirmation_period_type == 'days':
                            confirmation_date = self.booking_date + relativedelta(days=+self.predefine_plan_id.confirmation_amount_period)
                        if self.predefine_plan_id.confirmation_period_type == 'months':
                            confirmation_date = self.booking_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period)
                        if self.predefine_plan_id.confirmation_period_type == 'years':
                            confirmation_date = self.booking_date + relativedelta(years=+self.predefine_plan_id.confirmation_amount_period)
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
                            'investor_file_id': self.id
                        })
                        confirmation_interval += 1
                else:
                    installment_number = 2

                # balloons replace installment slots only when the plan treats them as
                # installments; treated as balloons they come on top of the regular ones
                balloon_uses_slots = (not self.include_installment and self.predefine_plan_id
                                      and self.predefine_plan_id.include_in_plan == 'yes'
                                      and self.predefine_plan_id.treat_balloon_as == 'installment')
                installment_amount = round(
                    self.balance_amount / (self.total_installment - self.balloon_payment_frequency)
                ) if balloon_uses_slots else round(
                    self.balance_amount / self.total_installment)

                expected_installments = self.total_installment
                if balloon_uses_slots:
                    expected_installments = self.total_installment - self.balloon_payment_frequency

                def _pending_plan_events():
                    # regular installments and balloon/possession/balloting lines whose
                    # slot falls beyond the generated dates still have to be scheduled
                    if self.plan_type != 'predefine' or not self.predefine_plan_id:
                        return False
                    if installment_count <= expected_installments:
                        return True
                    plan_products = self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids
                    if (self.env.ref('real_estate.balloon_payment').id in plan_products
                            and interval < self.balloon_payment_frequency):
                        return True
                    if (self.env.ref('real_estate.possession_amount_product').id in plan_products
                            and possession_interval < self.possession_amount_frequency):
                        return True
                    if (self.env.ref('real_estate.additional_balloon').id in plan_products
                            and add_balloon_interval < self.add_balloon_frequency):
                        return True
                    if (self.env.ref('real_estate.balloting_product').id in plan_products
                            and primary_interval < self.primary_amount_frequency):
                        return True
                    return False

                i = 0
                total_dates = len(dates) - 1
                while True:
                    if i > total_dates:
                        if not _pending_plan_events() or len(dates) >= self.total_installment + 120:
                            break
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                        total_dates += 1
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
                                'investor_file_id': self.id
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

                    # Same set of flow as defined for other products of predefined plan
                    if (self.plan_type == 'predefine' and self.env.ref('real_estate.additional_balloon').id in
                            self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
                        if self.total_installment > 1:
                            try:
                                installment_number % self.add_balloon_interval == 0
                            except Exception as e:
                                raise ValidationError(_('%s Additional Balloon Interval should be greater than 0:' % (e)))
                            else:
                                if installment_number % self.add_balloon_interval == 0 \
                                        and add_balloon_interval < self.add_balloon_frequency:
                                    if balance:
                                        amount = self.add_balloon_amount if balance > installment_amount else balance
                                    else:
                                        amount = 0
                                    self.installment_plan_ids.create({
                                        # 'date': rec,
                                        'date': dates[i] - relativedelta(
                                            months=+self.interval_id.nom) if is_final_payment_included else dates[i],
                                        'installment_number': installment_number,
                                        'installment_type': 'balloon',
                                        'installment_name': 'Balloon',
                                        'payment_status': 'not_paid',
                                        'residual': amount,
                                        'amount': amount,
                                        'investor_file_id': self.id
                                    })
                                    add_balloon_interval += 1
                                    installment_number = installment_number + 1
                                    if is_final_payment_included:
                                        i, total_dates, dates = self.prepare_next_iterator_value(dates, i, total_dates)
                                    else:
                                        i += 1
                                    continue

                    # for recs in self.predefine_plan_id.predefine_plan_line_ids:
                    if (self.plan_type == 'predefine' and self.env.ref('real_estate.possession_amount_product').id in
                            self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):
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
                                        'investor_file_id': self.id
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
                                    'investor_file_id': self.id
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
                                    'investor_file_id': self.id
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
                            'investor_file_id': self.id
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
                            'investor_file_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                        i += 1
                    elif self.investment_id:
                        if self.plan_type == 'predefine' and installment_count > expected_installments:
                            # all regular installment slots are filled; keep the slot
                            # numbering and dates moving so later balloon/possession
                            # slots land on their configured positions
                            installment_number = installment_number + 1
                            i += 1
                            continue
                        if self.investment_id.options == 'down' or self.investment_id.investment_plan_ids and self.investment_id.remaining_installments > 0:
                            installment_number = self.installment_plan_ids[-1].installment_number + 1
                            paid_installments = (self.total_installment - (self.investment_id.remaining_installments or 1)) * round(
                                self.balance_amount / self.total_installment)
                            amount = round((self.balance_amount - paid_installments) / (self.investment_id.remaining_installments or 1))
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
                                'investor_file_id': self.id
                            })
                            installment_count += 1
                            installment_number = installment_number + 1
                            i += 1
                    else:
                        if self.plan_type == 'predefine' and installment_count > expected_installments:
                            installment_number = installment_number + 1
                            i += 1
                            continue
                        self.installment_plan_ids.create({
                            # 'date': rec,
                            'date': dates[i].replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' ' + str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': installment_amount,
                            'tax_amount': round((installment_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                            'residual': installment_amount + round((installment_amount * tax_id[0].amount) / 100,
                                                                   2) if tax_id else installment_amount,
                            'investor_file_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                        i += 1

                plan = self.env['installment.plan'].search([('investor_file_id', '=', self.id)])
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
                        'investor_file_id': self.id
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
                    _("Installment Starting Date,Interval and total installments should be there for active files"))
        if self.payment_type == 'lump_sum':
            if self.predefine_plan_id and len(self.predefine_plan_id.predefine_plan_line_ids) or self.env.ref('real_estate.lump_sum_product').id in \
                    self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                if self.investment_id.investment_plan_ids and self.investment_id.investment_plan_ids[0].payment_status == 'paid':
                    self.installment_plan_ids.create({
                        'date': self.booking_date,
                        'payment_date': self.booking_date,
                        'installment_name': 'Lump Sum',
                        'installment_type': 'down',
                        'invoice': 'Paid By Investor',
                        # 'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
                        # 'invoice_created': True,
                        # 'investor_payment': True,
                        'installment_number': 1,
                        'amount': self.net_sale_amount,
                        'amount_paid': self.net_sale_amount,
                        'residual': 0,
                        'payment_status': 'paid',
                        'investor_file_id': self.id
                    })
                else:
                    self.installment_plan_ids.create({
                        'date': self.starting_date,
                        'payment_date': self.starting_date,
                        'installment_name': 'Lump Sum',
                        'installment_type': 'down',
                        'invoice': 'Paid By Investor',
                        # 'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
                        # 'invoice_created': True,
                        # 'investor_payment': True,
                        'installment_number': 1,
                        'amount': self.net_sale_amount,
                        'tax_amount': round((self.net_sale_amount * tax_id[0].amount) / 100, 2) if tax_id else 0,
                        'residual': self.net_sale_amount + round((self.net_sale_amount * tax_id[0].amount) / 100, 2) if tax_id else self.net_sale_amount,
                        'payment_status': 'not_paid',
                        'investor_file_id': self.id
                    })
        self.compute_rebate_amount()
        for lines in self.installment_plan_ids:
            lines.compute_net_receivable()

    @api.depends('net_sale_amount')
    def _compute_balloting_amount(self):
        self.balloting_amount = round(self.net_sale_amount * (self.env.company.balloting_percentage / 100))

    @api.depends('net_sale_amount', 'initial_payment', 'balloting_amount')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = round(rec.net_sale_amount - rec.initial_payment - rec.balloting_amount)

    @api.model_create_multi
    def create(self, vals_list):
        new_record = super().create(vals_list)
        if self.env.company.id != 1:
            random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            new_record.name = random_num
        # new_record.create_jv()
        new_record._balloon_payment()
        new_record.create_installment_plan()
        new_record.update_rebate_values_for_booking()
        return new_record

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'

    # def create_jv(self):
    #     if self.env.company.unit_booking_journal_id:
    #         if not self.env.company.unit_booking_journal_id.default_debit_account_id:
    #             raise ValidationError(_("Please select debit account in selected journal"))
    #         if not self.env.company.unit_booking_journal_id.default_credit_account_id:
    #             raise ValidationError(_("Please select credit account in selected journal"))
    #         move = {
    #             'date': fields.Date.today(),
    #             'journal_id': self.env.company.unit_booking_journal_id.id,
    #             'company_id': self.env.company.id,
    #             'type': 'entry',
    #             'state': 'draft',
    #             'ref': self.name,
    #             'investor_file_id': self.id,
    #             'line_ids': [(0, 0, {
    #                 'account_id': self.env.company.unit_booking_journal_id.default_credit_account_id.id,
    #                 'debit': self.initial_payment}),
    #                          (0, 0, {
    #                              'account_id': self.env.company.unit_booking_journal_id.default_debit_account_id.id,
    #                              'credit': self.initial_payment
    #                          })]
    #         }
    #         move_id = self.env['account.move'].create(move)
    #
    #         move_id.post()
    #         self.move_id = move_id.id
    #     else:
    #         raise ValidationError(_('Please Select Journal in configuration'))

    def check_booking_clearance(self):
        for record in self:
            booking_line = self.env['installment.plan'].search([('investor_file_id', '=', record.id), ('installment_type', '=', 'down')])
            if booking_line and booking_line.residual > 1:
                error = "Please Clear the Booking Amount for the reserved Inventory to Issue the File"
                if self.payment_type == 'lump_sum':
                    error = "Please Clear the Amount for the reserved Inventory to Issue the File"
                raise ValidationError(error)

    def create_file(self):
        if not self.transferee_partner_id:
            raise ValidationError(_('Please create member first to approve request.'))
        self.check_booking_clearance()
        correspondence_address = '%s,%s,%s,%s,%s,%s' % (
            self.transferee_partner_id.corespondence_street, self.transferee_partner_id.corespondence_street2,
            self.transferee_partner_id.corespondence_city_id.id, self.transferee_partner_id.corespondence_state_id.id,
            self.transferee_partner_id.corespondence_zip, self.transferee_partner_id.corespondence_country_id.id)
        file = self.env['file'].create({
            'project_type': self.society_id.project_type,
            'from_open_file': True,
            'add_custom_value': True,
            'investment_adjustment': False,
            'tracking_id': self.name,
            'development_charges_included': self.development_charges_included,
            'membership_id': self.transferee_partner_id.id,
            'correspondence_address': correspondence_address,
            'membership_name': self.transferee_partner_id.name,
            # 'booking_date': self.booking_date,
            'booking_date': self.issuance_request_id.appointment_date if self.issuance_request_id else fields.Date.today(),
            'investor_id': self.investor_id.id,
            'investment_id': self.investment_id.id,
            'investor_file': self.id,
            'file_type': 'new',
            'type': 'investor',
            'state': 'available',
            'society_id': self.society_id.id,
            'phase_id': self.phase_id.id,
            'sector_id': self.sector_id.id,
            'street_id': self.street_id.id,
            'category_id': self.category_id.id,
            'unit_category_type_id': self.unit_category_type_id.id,
            'size_id': self.size_id.id,
            'unit_class_id': self.unit_class_id.id,
            'inventory_id': self.inventory_id.id,
            # 'payment_type': 'installments' if self.investment_id.options == 'down' else 'lump_sum',
            'payment_type': self.payment_type,
            'plan_type': self.plan_type,
            'interval_id': self.interval_id.id,
            'predefine_plan_id': self.predefine_plan_id.id if self.plan_type == 'predefine' else None,
            'starting_date': self.starting_date,
            'total_installment': self.total_installment,
            'payment_states': 'open' if self.investment_id.options == 'down' else 'close',
            'overall_status': 'open' if self.investment_id.options == 'down' else 'close',
            'sale_amount': self.sale_amount,
            'custom_sale_amount': self.sale_amount,
            'ttl_sale_amount': self.ttl_sale_amount,
            'net_sale_amount': self.net_sale_amount,
            'initial_payment': self.initial_payment,
            'balloting_amount': self.balloting_amount,
            'issued_to_sub_dealer': self.issued_to_sub_dealer,
            'sub_investor_id': self.sub_investor_id.id if self.sub_investor_id else None
        })
        # KIN Information from FIR
        file.kin_name = self.issuance_request_id.kin_name
        file.kin_mobile = self.issuance_request_id.kin_mobile
        file.kin_cnic = self.issuance_request_id.kin_cnic
        file.kin_member_relation = self.issuance_request_id.kin_member_relation
        file.other_relation = self.issuance_request_id.other_relation
        if self.issuance_history_ids and file:
            for line in self.issuance_history_ids:
                line.file_id = file.id

        # Agent Auto Assignment Code removed: referenced 'assignment.rule.line' and file.agent_id,
        # neither of which exist anywhere in this module set — dead/never-finished feature.
        self.investment_id.amount_paid = self.investment_id.amount_paid - self.investment_id.investor_unit_price
        file.investment_adjustment = True
        # Creating down payment on file which is already paid by investor
        # journal_entry = self.env['account.move.line'].search(
        #     [('move_id.journal_id', '=', self.env.company.unit_booking_journal_id.id),
        #      ('move_id.company_id', '=', self.env.company.id),
        #      ('move_id.type', '=', 'entry'),
        #      ('move_id.ref', '=', self.name),
        #      ('move_id.investor_file_id', '=', self.id),
        #      ('account_id', '=', self.env.company.unit_booking_journal_id.default_credit_account_id.id)])
        # if journal_entry:
        #     file.installment_plan_ids.create({
        #         'date': self.booking_date,
        #         'payment_date': self.booking_date,
        #         'installment_name': 'Booking',
        #         'installment_type': 'down',
        #         'invoice': journal_entry.move_id.name,
        #         'invoice_created': True,
        #         'investor_payment': True,
        #         'installment_number': 0,
        #         'amount': self.initial_payment,
        #         'amount_paid': self.initial_payment,
        #         'residual': 0,
        #         'payment_status': 'paid',
        #         'investor_file_id': file.id
        #     })
        # else:

        # Commenteed as Open File Installment plan will be replicated by passing file id to the existing installment plan so that it will be shown on file also
        # file.installment_plan_ids.create({
        #     'date': self.booking_date,
        #     'payment_date': self.booking_date,
        #     'installment_name': 'Booking',
        #     'installment_type': 'down',
        #     # 'invoice': 'Paid By Investor',
        #     'invoice': self.env['ir.sequence'].next_by_code('files.dp.paid.sequence'),
        #     'invoice_created': True,
        #     'investor_payment': True,
        #     'installment_number': 1,
        #     'amount': self.initial_payment,
        #     'amount_paid': self.initial_payment,
        #     'residual': 0,
        #     'payment_status': 'paid',
        #     'file_id': file.id
        # })
        #
        # if self.investment_id.options == 'down':
        #     investment_history = file.investment_id.investment_history_ids.create({
        #         'installment_number': file.investment_id.investment_history_ids[-1].installment_number + 1,
        #         'date': fields.Date.today(),
        #         'transaction_type': 'customer',
        #         'file_id': file.id,
        #         'amount': round(
        #             (file.investment_id.investment_history_ids[-1].new_balance / file.investment_id.total_installment)),
        #         'new_amount': round(((file.investment_id.investment_history_ids[
        #                                   -1].new_balance - file.balance_amount) / file.investment_id.remaining_installments)),
        #         'old_balance': file.investment_id.investment_history_ids[-1].new_balance,
        #         'new_balance': file.investment_id.investment_history_ids[-1].new_balance - file.balance_amount,
        #         'investment_id': file.investment_id.id,
        #     })
        #
        #     # Creating installments on files which are already paid by investor
        #     installment_number = 1
        #     for line in file.investment_id.investment_plan_ids:
        #         if line.invoice_created and line.installment_type == 'installment':
        #             file.installment_plan_ids.create({
        #                 'date': line.date,
        #                 'payment_date': line.payment_date,
        #                 'installment_type': 'installment',
        #                 'invoice': 'Paid By Investor',
        #                 'invoice_created': True,
        #                 'investor_payment': True,
        #                 'installment_number': installment_number,
        #                 'amount': round(file.balance_amount / file.investment_id.total_installment),
        #                 'amount_paid': round(file.balance_amount / file.investment_id.total_installment),
        #                 'residual': 0,
        #                 'payment_status': 'paid',
        #                 'file_id': file.id
        #             })
        #             installment_number = installment_number + 1
        #         if not line.invoice_created and line.balance_amount > 0:
        #             line.update({'file_adjusted_amount': line.file_adjusted_amount + (
        #                     file.balance_amount / file.total_installment),
        #                          'balance_amount': line.balance_amount - (file.balance_amount / file.total_installment),
        #                          'residual': line.balance_amount - (file.balance_amount / file.total_installment)})
        #
        file._balloon_payment()
        #     file.create_installment_plan()
        # Previous Installment Plann Code Ends here

        self.state = 'issued'
        self.inventory_id.state = 'sold'
        self.file_created = True
        # Passing the New File id to the existing Installment Plan
        self.file_id = file.id
        # Changing Confirmation Date according to FIR
        confirmation_line = self.installment_plan_ids.filtered(lambda x: x.installment_type == 'confirmation_amount')
        if confirmation_line:
            confirmation_date = self.file_id.booking_date + relativedelta(days=+45)
            confirmation_line.date = confirmation_date
        current_date = self.starting_date + relativedelta(months=-1)
        for ins in self.installment_plan_ids:
            ins.file_id = file.id
            # Change Installment Dates according to Installment Starting Date
            if self.env.company.id == 5:
                if ins.installment_name not in ['Booking', 'Confirmation'] and not ins.invoice:
                    current_date = current_date + relativedelta(months=+1)
                    ins.date = current_date
        # self.create_rebate_bills()

    def create_rebate_bills(self):
        self.create_dealer_sale_rebate_bill()
        self.create_marketing_sale_rebate_bill()

    def create_dealer_sale_rebate_bill(self):
        if self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount' and ins.dealer_share > 0):
            dealer_share = self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').dealer_share
            if dealer_share > 0:
                date = fields.Date.today()
                invoice_type = 'out_refund'

                rebate_invoice = self.env['account.move'].create({
                    'partner_id': self.investor_id.id,
                    'company_id': self.society_id.company_id.id,
                    # 'branch_id': self.env.branch.id,
                    'type': invoice_type,
                    'ref': self.name + 'INV',
                    'investment_id': self.investment_id.id,
                    'investor_file_id': self.id,
                    'invoice_date': date,
                    'property_invoice_type': 'dealer_rebate',
                    # 'journal_id': self.env.company.account_journal_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                        'name': self.env.ref('unit_booking.dealer_rebate').name,
                        'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                        'price_unit': dealer_share,
                    })],
                })
                rebate_invoice.action_post()
                self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').move_ids = [(4, rebate_invoice.id)]
            self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').calculate_rebate_given()

    def create_marketing_sale_rebate_bill(self):
        if self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount' and ins.marketing_share > 0):
            marketing_share = self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').marketing_share
            if marketing_share > 0:
                date = fields.Date.today()
                invoice_type = 'out_refund'

                rebate_invoice = self.env['account.move'].create({
                    'partner_id': self.investor_id.marketing_company_id.id,
                    'company_id': self.society_id.company_id.id,
                    # 'branch_id': self.env.branch.id,
                    'type': invoice_type,
                    'ref': self.name + 'INV',
                    'investment_id': self.investment_id.id,
                    'investor_file_id': self.id,
                    'invoice_date': date,
                    'property_invoice_type': 'dealer_rebate',
                    # 'journal_id': self.env.company.account_journal_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                        'name': self.env.ref('unit_booking.dealer_rebate').name,
                        'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                        'price_unit': marketing_share,
                    })],
                })
                rebate_invoice.action_post()
                self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').move_ids = [(4, rebate_invoice.id)]
            self.installment_plan_ids.filtered(lambda ins: ins.installment_type == 'confirmation_amount').calculate_rebate_given()

    def plan_data_correction(self):
        all_files = self.env['file'].search([('society_id.company_id.id', '=', 5)])
        if all_files:
            for file in all_files:
                # Assigning File ID to Open File
                file.investor_file.file_id = file.id
                if file.investor_file:
                    # Booking
                    file.installment_plan_ids[0].marketing_share = file.investor_file.installment_plan_ids[0].marketing_share
                    file.installment_plan_ids[0].dealer_share = file.investor_file.installment_plan_ids[0].dealer_share
                    file.installment_plan_ids[0].rebate_amount = file.investor_file.installment_plan_ids[0].rebate_amount
                    file.installment_plan_ids[0].rebate_given = file.investor_file.installment_plan_ids[0].rebate_given
                    file.installment_plan_ids[0].dealer_rebate_given = file.investor_file.installment_plan_ids[0].dealer_rebate_given
                    file.installment_plan_ids[0].marketing_rebate_given = file.investor_file.installment_plan_ids[0].marketing_rebate_given
                    file.installment_plan_ids[0].move_ids = file.investor_file.installment_plan_ids[0].move_ids.ids if file.investor_file.installment_plan_ids[
                        0].move_ids else None
                    # Confirmation
                    file.installment_plan_ids[1].marketing_share = file.investor_file.installment_plan_ids[1].marketing_share
                    file.installment_plan_ids[1].dealer_share = file.investor_file.installment_plan_ids[1].dealer_share
                    file.installment_plan_ids[1].rebate_amount = file.investor_file.installment_plan_ids[1].rebate_amount
                    file.installment_plan_ids[1].rebate_given = file.investor_file.installment_plan_ids[1].rebate_given
                    file.installment_plan_ids[1].dealer_rebate_given = file.investor_file.installment_plan_ids[1].dealer_rebate_given
                    file.installment_plan_ids[1].marketing_rebate_given = file.investor_file.installment_plan_ids[1].marketing_rebate_given
                    file.installment_plan_ids[1].move_ids = file.investor_file.installment_plan_ids[1].move_ids.ids if file.investor_file.installment_plan_ids[
                        1].move_ids else None

    def delete_and_link_plan(self):
        file_ids = self.env['file'].search([('society_id.company_id.id', '=', 5)]).mapped('id')
        investor_file_ids = self.env['file'].search([('society_id.company_id.id', '=', 5)]).mapped('investor_file.id')
        plan_line_ids = self.env['installment.plan'].search([('investor_file_id', 'in', investor_file_ids)]).mapped('id')
        if plan_line_ids:
            # plan_lines.unlink()
            cr = self.env.cr
            cr.execute(f"""DELETE FROM installment_plan WHERE id IN {tuple(plan_line_ids)}""")
        plan_lines = self.env['installment.plan'].search([('file_id', 'in', file_ids)])
        if plan_lines:
            for line in plan_lines:
                line.investor_file_id = line.file_id.investor_file.id
                line.compute_net_receivable()

        plan_line = self.env['installment.plan'].search(
            [('file_id', '=', False), ('investor_file_id.state', 'not in', ['issued', 'cancel']), ('investor_file_id.society_id.company_id.id', '=', 5),
             ('installment_type', '=', 'down')])
        if plan_line:
            for ins in plan_line:
                if not ins.invoice:
                    ins.invoice = self.env['ir.sequence'].next_by_code('files.dp.paid.sequence')
                    ins.amount_paid = ins.amount
                    ins.residual = 0
                    ins.payment_status = 'paid'
        # files = self.env['file'].search([('society_id.company_id.id', '=', 5)], limit=5)
        # if files:
        #     investor_files = files.mapped('investor_file')
        #     if investor_files:
        #         for plan in investor_files.installment_plan_ids:
        #             plan.unlink()
        #     for file in files:
        #         for line in file.installment_plan_ids:
        #             line.investor_file_id = file.investor_file.id

    def set_net_payment_data(self):
        confirmation_lines = self.env['installment.plan'].search([('installment_name', '=', 'Confirmation'), ('investor_file_id.society_id.company_id.id', 'in', [5, 16])])
        if confirmation_lines:
            for line in confirmation_lines:
                line.compute_net_payment()
        booking_lines = self.env['installment.plan'].search([('installment_name', '=', 'Booking'), ('investor_file_id.society_id.company_id.id', 'in', [5, 16])])
        if booking_lines:
            for line in booking_lines:
                line.compute_net_payment()

    def update_rebate_values_for_booking(self):
        for rec in self:
            booking_lines = rec.installment_plan_ids.filtered(lambda l: l.installment_type == 'down')
            if booking_lines:
                for booking_line in booking_lines:
                    booking_line.net_payment = 0
                    booking_line.rebate_adjustment = booking_line.dealer_share
                    booking_line.compute_net_receivable()

    def open_file_status_update_query(self):
        open_files = self.env['investor.file'].search([('issuance_request_created', '=', True), ('state', '!=', 'cancel')])
        for file in open_files:
            if file.state == 'open':
                file.state = 'in_process'

    def update_confirmation_net_payment_query(self):
        confirmations = self.env['installment.plan'].search([('installment_type', '=', 'confirmation_amount'), ('company_id.id', '=', 5)])
        for rec in confirmations:
            rec.net_receivable = rec.amount - rec.dealer_share
            rec.net_payment = rec.amount_paid - rec.dealer_share if rec.amount_paid - rec.dealer_share > 0 else 0

    def update_payment_journal_on_plan_lines(self):
        payment_lines = self.env['multi.invoice.payment'].search([('payment_id.company_id', '=', 5),
                                                                  ('payment_id.payment_nature', '=', 'normal'),
                                                                  ('payment_id.payment_type', '=', 'inbound'),
                                                                  ('payment_id.state', '=', 'posted'),
                                                                  ('payment_id.file_id', '!=', False),
                                                                  ('invoice_id.property_invoice_type', '=', 'installment'),
                                                                  ], order='create_date asc')
        for line in payment_lines:
            installment_line = self.env['installment.plan'].search([('invoice_created', '=', True), ('invoice_id', '=', line.invoice_id.id)], limit=1)
            if installment_line:
                installment_line.payment_journal_id = line.payment_id.journal_id.id


class InstallmentPlanExt(models.Model):
    _inherit = 'installment.plan'

    investor_file_id = fields.Many2one('investor.file')
    marketing_share = fields.Float(string="Marketing Rebate")
    dealer_share = fields.Float(string="Dealer Rebate")
    rebate_amount = fields.Float(string="Total Rebate Amount")
    rebate_given = fields.Float(string="Total Rebate Given")
    dealer_rebate_given = fields.Float(string="Dealer Rebate Given")
    marketing_rebate_given = fields.Float(string="Marketing Rebate Given")
    move_ids = fields.Many2many('account.move')
    net_receivable = fields.Float(string="Net Receivable", compute="compute_net_receivable", store=True)
    net_payment = fields.Float(string="Net Payment")
    rebate_adjustment = fields.Float(string="Rebate Adjustment")

    payment_journal_id = fields.Many2one('account.journal', string="Payment Journal", tracking=True)
    # Fields for Amount Revision
    price_revised = fields.Boolean(default=False)
    previous_amount = fields.Float(string="Prev. Amount")
    amount_difference = fields.Float(string="Amount Difference")
    previous_dealer_rebate = fields.Float(string="Prev. Dealer Rebate")
    previous_marketing_rebate = fields.Float(string="Prev. Marketing Rebate")
    previous_total_rebate = fields.Float(string="Prev. Total Rebate")
    dealer_rebate_difference = fields.Float(string="Dealer Rebate Difference")
    marketing_rebate_difference = fields.Float(string="Marketing Rebate Difference")
    total_rebate_difference = fields.Float(string="Total Rebate Difference")

    account_status = fields.Selection([('accepted', 'Accepted'), ('rejected', 'Rejected')], string="Account Status")
    reason = fields.Text()

    def compute_net_receivable(self):
        for rec in self:
            rec.net_receivable = rec.amount - rec.dealer_share

    def compute_lps(self):
        # LPS recompute is not implemented in this branch; no-op so the
        # price-revision flow does not crash
        pass

    def compute_net_payment(self):
        for rec in self:
            confirmation_paid = 0
            confirmation_rebate_adjusted = 0
            if rec.installment_name == 'Confirmation' and rec.invoice_id and rec.investor_file_id.society_id.company_id.id in [5, 16]:
                payment_lines = self.env['multi.invoice.payment'].search([('invoice_id', '=', rec.invoice_id.id), ('payment_id.state', '=', 'posted')])
                if payment_lines:
                    confirmation_paid = sum(x.payment_amount for x in payment_lines)
                    confirmation_rebate_adjusted = sum(
                        x.payment_difference for x in
                        payment_lines.filtered(lambda l: l.payment_difference_handling == 'commission_adjustment' or l.payment_difference_handling ==
                                                         'reconcile'))
                rec.rebate_adjustment = confirmation_rebate_adjusted
                rec.net_payment = confirmation_paid
            if rec.installment_name == 'Booking' and rec.payment_status == 'paid' and rec.investor_file_id.society_id.company_id.id in [5, 16]:
                rec.rebate_adjustment = rec.dealer_share
                rec.net_payment = rec.amount_paid - rec.dealer_share if rec.amount_paid - rec.dealer_share > 0 else 0

    def calculate_rebate_given(self):
        for rec in self:
            if rec.investor_file_id and rec.installment_type == 'confirmation_amount' and rec.move_ids:
                dealer_rebate = 0
                marketing_rebate = 0
                total_rebate = 0
                if rec.move_ids:
                    dealer_rebate = sum(x.amount_total for x in rec.move_ids.filtered(lambda move: move.partner_id.id == rec.investor_file_id.investor_id.partner_id.id))
                    marketing_rebate = sum(x.amount_total for x in rec.move_ids.filtered(lambda move: move.partner_id.id ==
                                                                                                      rec.investor_file_id.investor_id.marketing_company_id.id))
                    total_rebate = dealer_rebate + marketing_rebate
                rec.rebate_given = total_rebate
                rec.dealer_rebate_given = dealer_rebate
                rec.marketing_rebate_given = marketing_rebate

    @api.depends('invoice_id', 'invoice_id.amount_residual', 'file_id.token_id', 'installment_type')
    def _invoice_id_data(self):
        for rec in self:
            token_amount = 0
            if rec.file_id.token_id and rec.invoice_created and rec.installment_type == 'down':
                token = rec.file_id.token_id
                token_amount = token.token_fees
                token.state = 'adjusted'
            if rec.invoice_id:
                rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual + token_amount
            rec.residual = rec.invoice_id.amount_residual if rec.invoice_id else rec.amount - rec.amount_paid


class OpenFileHistory(models.Model):
    _name = 'open.file.history'
    _description = 'Open File History'

    investor_file_id = fields.Many2one('investor.file')
    net_sale_amount = fields.Float(string="Net Sale Amount")
    predefine_plan_id = fields.Many2one('predefine.plan')
    no_of_installments = fields.Integer(string="No. of Installments")
    discount = fields.Float(string="Discount")
    booking_marketing_share = fields.Float(string="Booking Marketing Rebate")
    booking_dealer_share = fields.Float(string="Booking Dealer Rebate")
    booking_rebate_amount = fields.Float(string="Booking Total Rebate")
    confirmation_marketing_share = fields.Float(string="Confirmation Marketing Rebate")
    confirmation_dealer_share = fields.Float(string="Confirmation Dealer Rebate")
    confirmation_rebate_amount = fields.Float(string="Confirmation Total Rebate")
