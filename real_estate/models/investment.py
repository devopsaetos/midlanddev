import json
import base64
import logging

import random
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser

_logger = logging.getLogger(__name__)


class AccountMoveExt(models.Model):
    _inherit = 'account.move'

    investment_id = fields.Many2one('investment')


class AccountPaymentExt(models.Model):
    _inherit = 'account.payment'

    investment_id = fields.Many2one('investment')


class Investment(models.Model):
    _name = 'investment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Investment'
    _rec_name = 'sequence_no'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reserved', 'Reserved'),
        ('payment', 'Payment Received'),
        ('closed', 'Closed'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', tracking=True)
    sequence_no = fields.Char('Investment Sequence', required=True, copy=False, readonly=True, index=True,
                              default=lambda self: _('New'))
    name = fields.Char(compute='get_default_value')
    society_id = fields.Many2one('society', 'Society', required=True, domain=[('is_society', '=', True)],
                                 tracking=True)
    phase_id = fields.Many2one('society', 'Phase', required=True, tracking=True)
    sector_id = fields.Many2one('sector', 'Sector', tracking=True)
    category_id = fields.Many2one('plot.category', 'Category', tracking=True)
    partner_id = fields.Many2one('res.investor', string='Investor', required=True, tracking=True)
    booking_date = fields.Date('Booking date', required=True, tracking=True)
    start_date = fields.Date('Start date', required=True, tracking=True)
    total_amount = fields.Float('Total amount', compute='compute_deal_price', store=True, readonly=True,
                                tracking=True)
    down_payment = fields.Float('Down Payment', required=True, tracking=True)
    balance_amount = fields.Float(compute='_compute_balance_amount', store=True, tracking=True)
    amount_paid = fields.Float()
    total_installment = fields.Integer('No. of Installments', related='predefine_plan_id.total_installment', store=True)
    remaining_installments = fields.Integer('Remaining Installments', compute='_compute_remaining_installments')
    interval_id = fields.Many2one('payment.interval', required=True)
    grace_period = fields.Integer()
    grace_period_type = fields.Selection([
        ('days', 'Day(s)'),
        ('months', 'Month(s)'),
        ('years', 'Year(s)'),
    ], default='days', tracking=True, required=True)
    no_of_units = fields.Integer(compute='_compute_total_units', store=True)
    no_of_files = fields.Integer(compute='_compute_total_files')
    no_of_issued_files = fields.Integer(compute='_compute_total_issued_files')
    investor_unit_price = fields.Float()
    amount_received = fields.Boolean()
    installment_created = fields.Boolean()
    options = fields.Selection([
        ('full', 'Full Payment'),
        ('down', 'Down Payment')
    ], tracking=True)
    reservation_type = fields.Selection([
        ('unit', 'Unit Reservation'),
        ('bulk', 'Bulk Reservation')
    ], tracking=True)
    files_created = fields.Boolean(default=False)
    journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ('cash', 'bank'))],
                                 tracking=True)
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default="cash")
    allowed_credit = fields.Boolean(string="Allow Credit")
    payment_date = fields.Date()
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms',
                                      readonly=True, states={'draft': [('readonly', False)]})
    mode_of_payment = fields.One2many('investment.payment.mode', 'investment_id')

    notes = fields.Text('Internal Notes')
    inventory_ids = fields.Many2many('plot.inventory')
    investment_line_ids = fields.One2many('investment.line', 'investment_id')
    investment_plan_ids = fields.One2many('investment.plan', 'investment_id')
    investment_history_ids = fields.One2many('investment.history', 'investment_id')
    unit_cancel_swap_ids = fields.One2many('unit.cancel.swap.history', 'investment_id')
    investment_payment_view_ids = fields.One2many('investment.payment.view', 'investment_id')
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    plan_type = fields.Selection([('custom', 'Custom'), ('predefine', 'Predefine')], default='custom',
                                 tracking=True)
    predefine_plan_id = fields.Many2one('predefine.plan')
    installment_starting_date = fields.Date('Plan Starting Date', tracking=True)

    # Predefine plan related field for calculation
    # Boolean fields
    include_installment = fields.Boolean()
    generate_invoices_for_installment = fields.Boolean(default=False)
    balloting_amount = fields.Float()
    balloon_payment = fields.Float()
    balloon_payment_interval = fields.Integer()
    balloon_payment_frequency = fields.Integer()
    balloon_payment_start = fields.Integer()
    primary_amount = fields.Float()
    primary_amount_interval = fields.Integer()
    primary_amount_frequency = fields.Integer()
    possession_amount = fields.Float()
    possession_amount_interval = fields.Integer()
    possession_amount_frequency = fields.Integer()
    confirmation_amount = fields.Float()
    confirmation_amount_interval = fields.Integer()
    confirmation_amount_frequency = fields.Integer()

    # created for product 'Additional Balloon', used in installment creation
    add_balloon_amount = fields.Float(string='Additional Balloon Amount')
    add_balloon_interval = fields.Integer(string='Additional Balloon Interval')
    add_balloon_frequency = fields.Integer(string='Additional Balloon Frequency')

    @api.onchange('predefine_plan_id', 'total_amount')
    def _onchange_total_amount(self):
        if self.predefine_plan_id:
            self.interval_id = self.predefine_plan_id.interval_id.id
            self.grace_period = self.predefine_plan_id.confirmation_amount_period
            self.grace_period_type = self.predefine_plan_id.confirmation_period_type
            for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:
                if self.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    self.down_payment = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                              else pre_plan.value * self.no_of_units)

                if self.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                    self.balloting_amount = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                  else pre_plan.value * self.no_of_units)

                if self.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                    self.balloon_payment = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                 else pre_plan.value * self.no_of_units)
                    self.balloon_payment_interval = pre_plan.interval
                    self.balloon_payment_frequency = pre_plan.frequency
                    self.balloon_payment_start = pre_plan.start_from
                    self.include_installment = pre_plan.include_installment

                # for product 'Additional Balloon' used in predefined plan
                if self.env.ref('real_estate.additional_balloon').id == pre_plan.product_id.id:
                    self.add_balloon_amount = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                 else pre_plan.value * self.no_of_units)
                    self.add_balloon_interval = pre_plan.interval
                    self.add_balloon_frequency = pre_plan.frequency

                if self.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    self.possession_amount = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                   else pre_plan.value * self.no_of_units)
                    self.possession_amount_interval = pre_plan.interval
                    self.possession_amount_frequency = pre_plan.frequency

                if self.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    self.confirmation_amount = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                     else pre_plan.value * self.no_of_units)
                    self.confirmation_amount_interval = pre_plan.interval
                    self.confirmation_amount_frequency = pre_plan.frequency

                if self.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                    self.primary_amount = round(self.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                else pre_plan.value * self.no_of_units)
                    self.primary_amount_interval = pre_plan.interval
                    self.primary_amount_frequency = pre_plan.frequency

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(
            self.env['account.move'].search([('investment_id', '=', self.id), ('move_type', '=', 'out_invoice')]))

    @api.depends('investment_plan_ids')
    def _compute_remaining_installments(self):
        for rec in self:
            rec.remaining_installments = len(rec.investment_plan_ids.search(
                [('investment_id', '=', rec.id), ('installment_type', '=', 'installment'),
                 ('invoice_created', '!=', True)]))

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Investment Invoices'),
            'res_model': 'account.move',
            'domain': [('investment_id', '=', self.id), ('move_type', '=', 'out_invoice')],
            'context': {'default_partner_id': self.partner_id.id},
        }

    def get_default_value(self):
        for rec in self:
            rec.name = rec.sequence_no

    @api.depends('investment_line_ids', 'inventory_ids')
    def compute_deal_price(self):
        for rec in self:
            rec.total_amount = 0
            if rec.investment_line_ids:
                rec.total_amount = sum(rec.investment_line_ids.mapped('deal_price')) if rec.investment_line_ids else 0
            if rec.inventory_ids:
                rec.total_amount = sum(rec.inventory_ids.mapped('deal_price')) if rec.inventory_ids else 0

    @api.constrains('balance_amount')
    def check_balance_amount(self):
        if self.balance_amount < 0:
            raise ValidationError(_('Balance amount cannot be less than 0.'))

    @api.depends('investment_line_ids', 'inventory_ids')
    def _compute_total_units(self):
        self.no_of_units = 0
        if self.investment_line_ids:
            self.no_of_units = sum(self.investment_line_ids.mapped('no_of_units'))
        if self.inventory_ids:
            self.no_of_units = len(self.inventory_ids.mapped('id'))

    @api.depends('total_amount', 'down_payment')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = rec.total_amount - rec.down_payment

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        inventory_domain = [('phase_id', '=', self.phase_id.id), ('state', '=', 'avalible_for_sale')]
        if self.sector_id:
            inventory_domain.append(('sector_id', '=', self.sector_id.id))
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'inventory_ids': inventory_domain
            }
        }

    @api.onchange('inventory_ids')
    def _onchange_inventory_ids(self):
        for rec in self.inventory_ids:
            if rec.investor_unit_price == 0.0:
                rec.investor_unit_price = self.investor_unit_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence_no', _('New')) == _('New'):
                vals['sequence_no'] = self.env['ir.sequence'].next_by_code('investment.sequence') or _('New')
        result = super(Investment, self).create(vals_list)
        return result

    def reserve_inventory(self):
        for rec in self:
            # if rec.investment_line_ids:
            #     for line in rec.investment_line_ids:
            #         for unit in range(0, line.no_of_units):
            #             inventory = rec.env['plot.inventory'].search([
            #                 ('society_id', '=', rec.society_id.id),
            #                 ('phase_id', '=', rec.phase_id.id),
            #                 ('sector_id', '=', line.sector_id.id),
            #                 ('category_id', '=', line.category_id.id),
            #                 ('unit_category_type_id', '=', line.unit_category_type_id.id),
            #                 ('state', '=', 'avalible_for_sale'),
            #             ], limit=1)
            #             if inventory:
            #                 inventory.state = 'investor'
            #                 inventory.investment_id = self.id
            #                 inventory.partner_id = self.partner_id.id
            #                 inventory.investor_unit_price = line.investor_price
            #             else:
            #                 raise ValidationError("Inventory you are trying to reserve is not available.")
            # elif rec.inventory_ids:
            if rec.inventory_ids:
                for line in rec.inventory_ids:
                    if line:
                        line.state = 'investor'
                        line.investment_id = self.id
                        line.partner_id = self.partner_id.id
                        # line.deal_price = line.deal_price
            else:
                if not rec.inventory_ids and not rec.investment_line_ids:
                    raise ValidationError('Please add inventory details.')
        self.state = 'reserved'

    def receive_payment(self):
        if not self.investment_plan_ids:
            raise ValidationError(_('Create Installment Plan first.'))
        if self.total_amount:
            prod = [(0, 0, {
                'product_id': self.env.ref('real_estate.investment').product_id.id,
                'name': self.env.ref('real_estate.investment').name,
                'account_id': self.env.ref('real_estate.investment').product_id.property_account_income_id.id,
                'price_unit': self.down_payment
            })]
            invoice = self.env['account.move'].create({

                'partner_id': self.partner_id.id,
                'move_type': 'out_invoice',
                'investment_id': self.id,
                'invoice_date': self.booking_date,
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
                'property_invoice_type': 'investment',
            })
            invoice.action_post()

            payment_type = self.env.company.payment_type
            if payment_type:
                if payment_type == 'osp':
                    Payment = self.env['account.payment'].with_context(default_invoice_ids=[(4, invoice.id, False)])
                    payment = Payment.create({
                        'payment_date': fields.Date.today(),
                        # 'payment_method_id': self.inbound_payment_method.id,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'partner_id': self.partner_id.id,
                        'amount': self.down_payment,
                        'journal_id': self.journal_id.id,
                        'company_id': self.env.company.id,
                        'currency_id': self.env.company.currency_id.id,
                        'memo': invoice.name,
                    })
                    payment.post()

            for rec in self.investment_plan_ids:
                if rec.installment_number == 1 and rec.invoice_created != True:
                    rec.write({
                        'invoice_created': True,
                        'invoice_id': invoice.id,
                    })

            self.amount_received = True
            for rec in self:
                # if rec.investment_line_ids and rec.state != 'reserved':
                #     for line in rec.investment_line_ids:
                #         for unit in range(0, line.no_of_units):
                #             inventory = rec.env['plot.inventory'].search([
                #                 ('society_id', '=', rec.society_id.id),
                #                 ('phase_id', '=', rec.phase_id.id),
                #                 ('sector_id', '=', line.sector_id.id),
                #                 ('category_id', '=', line.category_id.id),
                #                 ('unit_category_type_id', '=', line.unit_category_type_id.id),
                #                 ('state', '=', 'avalible_for_sale'),
                #             ], limit=1)
                #             if inventory:
                #                 inventory.state = 'investor'
                #                 inventory.investment_id = self.id
                #                 inventory.partner_id = self.partner_id.id
                #                 inventory.investor_unit_price = line.investor_price
                #             else:
                #                 raise ValidationError("Inventory you are trying to reserve is not available.")
                if rec.inventory_ids and rec.state != 'reserved':
                    for line in rec.inventory_ids:
                        if line:
                            line.state = 'investor'
                            line.investment_id = self.id
                            line.partner_id = self.partner_id.id
                            # line.deal_price = line.deal_price
                if rec.reservation_type != 'unit' and not rec.investment_line_ids:
                    raise ValidationError('Please add inventory details.')
                if rec.reservation_type == 'unit' and not rec.inventory_ids:
                    raise ValidationError('Please add inventory details.')

            self.investment_history_ids.create({
                'installment_number': 1,
                'date': fields.Date.today(),
                'transaction_type': 'investor',
                'amount': 0,
                'new_amount': round(self.balance_amount / self.total_installment) if self.total_installment > 0 else 0,
                'old_balance': self.total_amount,
                'new_balance': round(self.balance_amount),
                'payment_received': 0,
                'investment_id': self.id,
            })
            self.state = 'payment'
            self.payment_states = 'open'

    def investor_inventory(self):
        tree_view = (self.env.ref('real_estate.plot_inventory_tree').id, 'list')
        form_view = (self.env.ref('real_estate.plot_inventory_form').id, 'form')
        return {
            'name': _('Unit'),
            'res_model': 'plot.inventory',
            'type': 'ir.actions.act_window',
            'context': {},
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('investment_id', '=', self.id)],
            'target': 'self'
        }

    def reset_installment_plan(self):
        if len(self.investment_plan_ids.mapped('invoice_id').ids) > 1:
            raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        self.investment_plan_ids.unlink()
        self.installment_created = False

    def generate_invoice_for_plan(self):
        for rec in self:
            if rec.state == 'payment':
                if rec.investment_plan_ids and rec.payment_states == 'open' and rec.society_id.company_id == self.env.company:
                    due_invoices = rec.investment_plan_ids.search([('date', '<=', fields.Date.today()),
                                                                   ('invoice_created', '!=', True),
                                                                   ('investment_id', '=', rec.id)])
                    if not due_invoices:
                        raise ValidationError(_("No invoice available for generation till date"))
                    for invoices in due_invoices:
                        try:
                            prod = [(0, 0, {
                                'product_id': self.env.ref('unit_booking.booking_allotment_installment').id,
                                'name': self.env.ref('unit_booking.booking_allotment_installment').name,
                                'account_id': self.env.ref(
                                    'unit_booking.booking_allotment_installment').property_account_income_id.id,
                                'price_unit': invoices.balance_amount
                            })]

                            invoice = self.env['account.move'].create({
                                'investment_id': rec.id,
                                # 'invoice_payment_ref': rec.sequence_no,
                                'partner_id': rec.partner_id.id,
                                'move_type': 'out_invoice',
                                'journal_id': self.env.company.account_journal_id.id,
                                'property_invoice_type': 'allotment_installment',
                                'invoice_date': invoices.date,
                                'invoice_date_due': invoices.date,
                            })
                            invoice.invoice_line_ids = prod

                            invoice.action_post()

                            invoices.invoice_id = invoice.id

                            invoices.invoice_created = True
                        except Exception as e:
                            raise UserError('There is some error: %s in auto invoice creation for installment' % (e))

                    rec.generate_invoices_for_installment = True
                if len(rec.investment_plan_ids.mapped('invoice_id')) == len(
                        rec.investment_plan_ids.filtered(
                            lambda l: l.investment_id == rec.id and l.invoice_created).mapped(
                            'invoice_created')):
                    rec.payment_states = 'close'
            else:
                raise ValidationError(_("Down Payment invoice is not generated"))

    def create_installment_plan(self):
        if not self.down_payment:
            raise ValidationError('Please enter down payment amount.')

        self.investment_plan_ids.create({
            'date': self.booking_date,
            'installment_type': 'down',
            'installment_name': 'Booking',
            'installment_number': 1,
            'amount': self.down_payment,
            'amount_paid': 0,
            'balance_amount': self.down_payment,
            'residual': self.down_payment,
            'payment_status': 'not_paid',
            'investment_id': self.id
        })

        # confirmation payment line

        if self.plan_type == 'predefine' \
                and self.env.ref('real_estate.confirmation_amount_product').id \
                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            installment_number = 3
            # confirmation_date = self.start_date
            confirmation_date = self.booking_date
            if self.grace_period_type == 'days':
                confirmation_date = self.booking_date + relativedelta(days=+self.grace_period)
            if self.grace_period_type == 'months':
                confirmation_date = self.booking_date + relativedelta(months=+self.grace_period)
            if self.grace_period_type == 'years':
                confirmation_date = self.booking_date + relativedelta(years=+self.grace_period)
            self.investment_plan_ids.create({
                # 'date': self.start_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period),
                'date': confirmation_date,
                'installment_number': 2,
                'installment_type': 'confirmation_amount',
                'installment_name': 'Confirmation',
                'payment_status': 'not_paid',
                'amount_paid': 0,
                'balance_amount': self.confirmation_amount,
                'amount': self.confirmation_amount,
                'residual': self.confirmation_amount,
                'investment_id': self.id
            })
        else:
            installment_number = 2

        if self.balance_amount > 0:
            # if all([self.installment_starting_date, self.interval_id, self.total_installment]):
            #     start_date = self.installment_starting_date
            if all([self.start_date, self.interval_id, self.total_installment]):
                start_date = self.start_date
                dates = [fields.Date.from_string(start_date)]

                interval = 0
                possession_interval = 0
                primary_interval = 0
                start_balloon_payment = False
                installment_count = 1
                balloon_interval = self.balloon_payment_interval
                balance = self.balance_amount - self.balloting_amount

                if self.predefine_plan_id:
                    for rec in self.predefine_plan_id.predefine_plan_line_ids:
                        if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
                            balance = balance - (self.balloon_payment *
                                                 self.balloon_payment_frequency)

                        if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
                            balance = balance - (self.possession_amount * self.possession_amount_frequency)

                        if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
                            balance = balance - (self.confirmation_amount *
                                                 self.confirmation_amount_frequency)

                        if rec.product_id.id == rec.env.ref('real_estate.balloting_product').id:
                            balance = balance - (self.primary_amount *
                                                 self.primary_amount_frequency)

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

                installment_amount = round(balance / (
                        self.total_installment - self.balloon_payment_frequency)) if not self.include_installment and self.predefine_plan_id and self.predefine_plan_id.include_in_plan == 'yes' else round(
                    balance / self.total_installment)

                for rec in dates:
                    if self.balloon_payment_start and not start_balloon_payment:
                        if installment_number == self.balloon_payment_start:
                            if balance:
                                amount = self.balloon_payment if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.investment_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloon',
                                'installment_name': 'Installment' + ' ' + str(
                                    installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                'payment_status': 'not_paid',
                                'balance_amount': amount + installment_amount if self.include_installment else amount,
                                'residual': amount + installment_amount if self.include_installment else amount,
                                'amount': amount + installment_amount if self.include_installment else amount,
                                'investment_id': self.id
                            })
                            if self.predefine_plan_id.treat_balloon_as == 'installment':
                                installment_count += 1
                            interval = interval + 1
                            balloon_interval += self.balloon_payment_start
                            start_balloon_payment = True
                            installment_number = installment_number + 1
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
                                self.investment_plan_ids.create({
                                    'date': rec,
                                    'installment_number': installment_number,
                                    'installment_type': 'possession_amount',
                                    'installment_name': 'Possession',
                                    'payment_status': 'not_paid',
                                    'amount_paid': 0,
                                    'balance_amount': amount,
                                    'residual': amount,
                                    'amount': amount,
                                    'investment_id': self.id
                                })
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
                                self.investment_plan_ids.create({
                                    'date': rec,
                                    'installment_number': installment_number,
                                    'installment_type': 'balloting_amount',
                                    'installment_name': 'Balloting',
                                    'payment_status': 'not_paid',
                                    'amount_paid': 0,
                                    'balance_amount': amount,
                                    'residual': amount,
                                    'amount': amount,
                                    'investment_id': self.id
                                })
                                primary_interval += 1
                                installment_number = installment_number + 1
                                continue

                    if (self.plan_type == 'predefine' and self.env.ref(
                            'real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped(
                        'product_id').ids and (installment_number % balloon_interval == 0
                                               and interval < self.balloon_payment_frequency and start_balloon_payment)):
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.investment_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'balloon',
                            'installment_name': 'Installment' + ' ' + str(
                                installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                            'payment_status': 'not_paid',
                            'amount_paid': 0,
                            'balance_amount': amount + installment_amount if self.include_installment else amount,
                            'residual': amount + installment_amount if self.include_installment else amount,
                            'amount': amount + installment_amount if self.include_installment else amount,
                            'investment_id': self.id
                        })
                        if self.predefine_plan_id.treat_balloon_as == 'installment':
                            installment_count += 1
                        interval = interval + 1
                        balloon_interval += self.balloon_payment_interval
                        installment_number = installment_number + 1
                        continue
                    else:
                        self.investment_plan_ids.create({
                            'date': rec,
                            'installment_type': 'installment',
                            'installment_number': installment_number,
                            'installment_name': 'Installment' + ' ' + str(installment_count),
                            'amount': installment_amount,
                            'balance_amount': installment_amount,
                            'amount_paid': 0,
                            'residual': installment_amount,
                            'payment_status': 'not_paid',
                            'investment_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                # total = sum(self.investment_plan_ids.mapped('amount'))
                # if total < self.total_amount:
                #     price = self.total_amount - total
                #     self.investment_plan_ids.search([])[-1].update({
                #         'amount': round(self.balance_amount / self.total_installment) + price,
                #         'balance_amount': round(self.balance_amount / self.total_installment) + price,
                #         'residual': round(self.balance_amount / self.total_installment) + price,
                #     })
                # elif total > self.total_amount:
                #     price = total - self.total_amount
                #     self.investment_plan_ids.search([])[-1].update({
                #         'amount': round(self.balance_amount / self.total_installment) - price,
                #         'balance_amount': round(self.balance_amount / self.total_installment) - price,
                #         'residual': round(self.balance_amount / self.total_installment) - price,
                #     })
                # del installment_number

                plan = self.env['investment.plan'].search([('investment_id', '=', self.id)])
                if self.balloting_amount:
                    plan.create({
                        'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                        'installment_type': 'final',
                        'payment_status': 'not_paid',
                        'installment_number': installment_number,
                        'installment_name': 'Final',
                        'amount_paid': 0,
                        'amount': self.balloting_amount,
                        'residual': self.balloting_amount,
                        'balance_amount': self.balloting_amount,
                        'investment_id': self.id
                    })
                    installment_count += 1

                total = sum(self.investment_plan_ids.mapped('amount'))
                if total < self.total_amount:
                    price = self.total_amount - total
                    self.investment_plan_ids.search([])[-1].update({
                        'amount': self.investment_plan_ids.search([])[-1].amount + price,
                        'residual': self.investment_plan_ids.search([])[-1].residual + price,
                        'balance_amount': self.investment_plan_ids.search([])[-1].balance_amount + price,
                    })
                elif total > self.total_amount:
                    price = total - self.total_amount
                    self.investment_plan_ids.search([])[-1].update({
                        'amount': self.investment_plan_ids.search([])[-1].amount - price,
                        'residual': self.investment_plan_ids.search([])[-1].residual - price,
                        'balance_amount': self.investment_plan_ids.search([])[-1].balance_amount - price,
                    })
                del installment_number

                self.installment_created = True
            else:
                raise ValidationError(
                    _("Installment Starting Date,Interval and total installments should be there."))

    # def create_installment_plan(self):
    #     # Creating downpayment line
    #     self.investment_plan_ids.create({
    #         'date': self.booking_date,
    #         'installment_type': 'down',
    #         'installment_number': 0,
    #         'amount': self.down_payment,
    #         'amount_paid': 0,
    #         'balance_amount': self.down_payment,
    #         'residual': self.down_payment,
    #         'payment_status': 'not_paid',
    #         'investment_id': self.id
    #     })
    #
    #     if self.balance_amount > 0:
    #         if all([self.start_date, self.interval_id, self.total_installment]):
    #
    #             start_date = self.start_date + relativedelta(months=+self.grace_period)
    #             dates = [fields.Date.from_string(start_date)]
    #
    #             for rec in range(1, self.total_installment):
    #                 dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
    #
    #             installment_number = 1
    #             balance = self.balance_amount
    #             if self.investment_history_ids:
    #                 balance = self.investment_history_ids[-1].new_balance
    #             for rec in dates:
    #                 self.investment_plan_ids.create({
    #                     'date': rec,
    #                     'installment_type': 'installment',
    #                     'installment_number': installment_number,
    #                     'amount': round(balance / self.total_installment),
    #                     'balance_amount': round(balance / self.total_installment),
    #                     'amount_paid': 0,
    #                     'residual': round(balance / self.total_installment),
    #                     'payment_status': 'not_paid',
    #                     'investment_id': self.id
    #                 })
    #                 installment_number = installment_number + 1
    #             total = sum(self.investment_plan_ids.mapped('amount'))
    #             if total < self.total_amount:
    #                 price = self.total_amount - total
    #                 self.investment_plan_ids.search([])[-1].update({
    #                     'amount': round(self.balance_amount / self.total_installment) + price,
    #                     'balance_amount': round(self.balance_amount / self.total_installment) + price,
    #                     'residual': round(self.balance_amount / self.total_installment) + price,
    #                 })
    #             elif total > self.total_amount:
    #                 price = total - self.total_amount
    #                 self.investment_plan_ids.search([])[-1].update({
    #                     'amount': round(self.balance_amount / self.total_installment) - price,
    #                     'balance_amount': round(self.balance_amount / self.total_installment) - price,
    #                     'residual': round(self.balance_amount / self.total_installment) - price,
    #                 })
    #             del installment_number
    #
    #             self.installment_created = True
    #         else:
    #             raise ValidationError(
    #                 _("Installment Starting Date,Interval and total installments should be there."))

    @api.model
    def investor_installment_invoices(self):
        # --------------------------------------
        date = self.env.ref('real_estate.ir_cron_investor_invoices').till_date or fields.Date.today()
        # -----------------------------------------
        for rec in self.search([('state', '=', 'payment')]):
            no_of_installment = []
            if rec.investment_plan_ids and rec.payment_states == 'open' and rec.society_id.company_id == self.env.company:
                for installment in rec.investment_plan_ids:

                    if installment.date <= date and not installment.invoice_created:
                        try:
                            prod = [(0, 0, {
                                'product_id': self.env.ref('real_estate.investment_installment').product_id.id,
                                'name': self.env.ref('real_estate.investment_installment').name,
                                'account_id': self.env.ref(
                                    'real_estate.investment_installment').product_id.property_account_income_id.id,
                                'price_unit': installment.balance_amount
                            })]

                            invoice = self.env['account.move'].create({
                                'investment_id': rec.id,
                                # 'invoice_payment_ref': rec.sequence_no,
                                'partner_id': rec.partner_id.id,
                                'move_type': 'out_invoice',
                                'journal_id': self.env.company.account_journal_id.id,
                                'property_invoice_type': 'investment_installment',
                                'invoice_date': installment.date,
                                'invoice_date_due': installment.date,
                            })
                            invoice.invoice_line_ids = prod

                            invoice.action_post()

                            installment.invoice_id = invoice.id

                            installment.invoice_created = True
                        except Exception as e:
                            raise UserError('There is some error: %s in auto invoice creation for installment' % (e))

                    no_of_installment.append(installment.invoice_created)
            else:
                no_of_installment.append(False)

            if all(no_of_installment):
                rec.payment_states = 'close'

    def create_open_file(self):
        inventory = self.env['plot.inventory'].search([('investment_id', '=', self.id)])
        prorate = self.down_payment / self.total_amount
        investor_file = self.env['investor.file']
        if self.reservation_type == 'bulk':
            for lines in self.investment_line_ids:
                for open_files in range(lines.no_of_units):
                    vals = {
                        'investor_id': self.partner_id.id,
                        'investment_id': self.id,
                        'state': 'open',
                        'society_id': self.society_id.id,
                        'phase_id': self.phase_id.id,
                        'sector_id': lines.sector_id.id,
                        'street_id': lines.street_id.id,
                        'category_id': lines.category_id.id,
                        'unit_category_type_id': lines.unit_category_type_id.id,
                        'size_id': lines.size_id.id,
                        # 'unit_class_id': inv.unit_class_id.id,
                        # 'inventory_id': inv.id,
                        # 'unit_number': inv.name,
                        'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                        'plan_type': self.plan_type,
                        'predefine_plan_id': self.predefine_plan_id.id,
                        'interval_id': self.interval_id.id if self.options == 'down' else False,
                        # 'starting_date': self.start_date,
                        'starting_date': self.installment_starting_date,
                        'total_installment': self.total_installment if self.options == 'down' else 0,
                        'payment_states': 'open',
                        'sale_amount': lines.investor_price,
                        'ttl_sale_amount': lines.investor_price,
                        'net_sale_amount': lines.investor_price,
                        'initial_payment': round(
                            lines.investor_price * prorate) if self.options == 'down' else lines.investor_price,
                        'balance_amount': lines.investor_price - round(
                            lines.investor_price * prorate) if self.options == 'down' else 0,
                    }
                    investor_file.create(vals)
        else:
            for inv in inventory:
                vals = {
                    'investor_id': self.partner_id.id,
                    'investment_id': self.id,
                    'state': 'open',
                    'society_id': self.society_id.id,
                    'phase_id': self.phase_id.id,
                    'sector_id': inv.sector_id.id,
                    'street_id': inv.street_id.id,
                    'category_id': inv.category_id.id,
                    'unit_category_type_id': inv.unit_category_type_id.id,
                    'size_id': inv.size_id.id,
                    'unit_class_id': inv.unit_class_id.id,
                    'inventory_id': inv.id,
                    'unit_number': inv.name,
                    'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                    'interval_id': self.interval_id.id if self.options == 'down' else False,
                    'starting_date': self.start_date,
                    'total_installment': self.total_installment if self.options == 'down' else 0,
                    'payment_states': 'open',
                    'sale_amount': inv.investor_unit_price,
                    'ttl_sale_amount': inv.investor_unit_price,
                    'net_sale_amount': inv.investor_unit_price,
                    'initial_payment': round(
                        inv.investor_unit_price * prorate) if self.options == 'down' else inv.investor_unit_price,
                    'balance_amount': inv.investor_unit_price - round(
                        inv.investor_unit_price * prorate) if self.options == 'down' else 0,
                }
                investor_file.create(vals)
        self.files_created = True

    def _compute_total_files(self):
        for rec in self:
            rec.no_of_files = len(rec.env['investor.file'].search([('investment_id', '=', rec.id)]))

    def investor_files(self):
        obj = self._context.get('current_view')
        if obj == 'building' or self.project_type == 'skyscraper':
            tree_view = (self.env.ref('land_development.investor_file_tree').id, 'list')
            form_view = (self.env.ref('land_development.investor_file_form').id, 'form')
            return {
                'name': _('Investor Files'),
                'res_model': 'investor.file',
                'type': 'ir.actions.act_window',
                'context': {},
                'views': [tree_view, form_view],
                'view_mode': 'list,form',
                'domain': [('investment_id', '=', self.id)],
                'target': 'self'
            }
        if obj == 'realestate' or self.project_type == 'housing_society':
            tree_view = (self.env.ref('real_estate.investor_file_tree').id, 'list')
            form_view = (self.env.ref('real_estate.investor_file_form').id, 'form')
            return {
                'name': _('Investor Files'),
                'res_model': 'investor.file',
                'type': 'ir.actions.act_window',
                'context': {},
                'views': [tree_view, form_view],
                'view_mode': 'list,form',
                'domain': [('investment_id', '=', self.id)],
                'target': 'self'
            }

    def _compute_total_issued_files(self):
        for rec in self:
            rec.no_of_issued_files = len(self.env['file'].search([('investment_id', '=', rec.id)]))

    def issued_files(self):
        obj = self._context.get('current_view')
        if obj == 'building' or self.project_type == 'skyscraper':
            tree_view = (self.env.ref('land_development.file_tree').id, 'list')
            form_view = (self.env.ref('land_development.file_form').id, 'form')
            return {
                'name': _('File'),
                'res_model': 'file',
                'type': 'ir.actions.act_window',
                'context': {},
                'views': [tree_view, form_view],
                'view_mode': 'list,form',
                'domain': [('investment_id', '=', self.id)],
                'target': 'self'
            }
        if obj == 'realestate' or self.project_type == 'housing_society':
            tree_view = (self.env.ref('real_estate.file_tree').id, 'list')
            form_view = (self.env.ref('real_estate.file_form').id, 'form')
            return {
                'name': _('File'),
                'res_model': 'file',
                'type': 'ir.actions.act_window',
                'context': {},
                'views': [tree_view, form_view],
                'view_mode': 'list,form',
                'domain': [('investment_id', '=', self.id)],
                'target': 'self'
            }

    @api.depends('sequence_no', 'partner_id')
    def name_get(self):
        result = []
        for record in self:
            name = record.sequence_no
            if record.sequence_no and record.sequence_no != 'New':
                name = "%s / %s" % (record.sequence_no, record.partner_id.investor_id)
            result.append((record.id, name))
        return result

    def unlink(self):
        for rec in self:
            if rec.state in ('reserved', 'payment'):
                raise ValidationError("You cannot delete a record once it is Reserved or Payment has been received.")

        return super(Investment, self).unlink()

    # These methods get called on api requests
    @api.model
    def get_investments(self):
        # partner = self.env['res.partner'].browse(self.env.user.partner_id.id)
        investments = self.env['investment'].sudo().search([('partner_id.partner_id', '=', self.env.user.partner_id.id)])
        data = []
        issued = []
        open = []
        in_process = []
        for inv in investments:
            issued_files = self.env['investor.file'].sudo().search(
                [('investment_id', '=', inv.id), ('state', '=', 'issued')])
            open_files = self.env['investor.file'].sudo().search(
                [('investment_id', '=', inv.id), ('state', '=', 'open')])
            in_process_files = self.env['investor.file'].sudo().search(
                [('investment_id', '=', inv.id), ('state', '=', 'in_process')])
            if issued_files:
                for rec in issued_files:
                    vals = {
                        'transaction_type': 'open_file',
                        'investment_id': inv.id,
                        'booking_date': str(rec.booking_date),
                        'sector_id': rec.sector_id.name,
                        'category_id': rec.category_id.name,
                        'unit_category_type_id': rec.unit_category_type_id.name,
                        'size_id': rec.size_id.name,
                        'unit_class_id': rec.unit_class_id.name,
                        'inventory_id': rec.inventory_id.name,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'investor_file_no': rec.name
                    }
                    issued.append(vals)

            if open_files:
                for rec in open_files:
                    vals = {
                        'transaction_type': 'open_file',
                        'investment_id': inv.id,
                        'booking_date': str(rec.booking_date),
                        'sector_id': rec.sector_id.name,
                        'category_id': rec.category_id.name,
                        'unit_category_type_id': rec.unit_category_type_id.name,
                        'size_id': rec.size_id.name,
                        'unit_class_id': rec.unit_class_id.name,
                        'inventory_id': rec.inventory_id.name,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'investor_file_no': rec.name
                    }
                    open.append(vals)

            if in_process_files:
                for rec in in_process_files:
                    vals = {
                        'transaction_type': 'open_file',
                        'investment_id': inv.id,
                        'booking_date': str(rec.booking_date),
                        'sector_id': rec.sector_id.name,
                        'category_id': rec.category_id.name,
                        'unit_category_type_id': rec.unit_category_type_id.name,
                        'size_id': rec.size_id.name,
                        'unit_class_id': rec.unit_class_id.name,
                        'inventory_id': rec.inventory_id.name,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'investor_file_no': rec.name
                    }
                    in_process.append(vals)

            investment = {'investment_name': inv.name,
                          'investment_id': inv.id,
                          'total_deal_amount': inv.total_amount,
                          'paid_amount': sum(inv.investment_plan_ids.mapped('amount_paid')),
                          'due_amount': sum(inv.investment_plan_ids.mapped('residual')),
                          'investor_name': inv.partner_id.investor_id,
                          'investor_id': inv.partner_id.id,
                          'sector_id': inv.sector_id.id,
                          'sector_name': inv.sector_id.name,
                          'no_of_issued_files': len(issued_files),
                          'no_of_open_files': len(open_files),
                          'no_of_in_process_files': len(in_process_files),
                          'issued_files': issued,
                          'open_files': open,
                          'in_process_files': in_process
                          }
            data.append(investment)

            issued = []
            open = []
            in_process = []

        return json.dumps(data)

    @api.model
    def search_open_files(self, **kwargs):
        # partner = self.env['res.partner'].browse(self.env.user.partner_id.id)
        investment = self.env['investment'].sudo().browse(kwargs['investment_id'])
        if investment:
            data = []
            open_files = self.env['investor.file'].sudo().search(
                [('investment_id', '=', investment.id), ('state', '=', 'open')])
            if open_files:
                for rec in open_files:
                    open_file = {
                        'total_open_files': len(open_files),
                        'transaction_type': 'open_file',
                        'investment_id': investment.id,
                        'sector_id': rec.sector_id.name,
                        'category_id': rec.category_id.name,
                        'unit_category_type_id': rec.unit_category_type_id.name,
                        'size_id': rec.size_id.name,
                        'unit_class_id': rec.unit_class_id.name,
                        'inventory_id': rec.inventory_id.name,
                        'investor_unit_price': rec.net_sale_amount,
                        'investor_file_id': rec.id,
                        'investor_file_no': rec.name
                    }
                    data.append(open_file)

                return data
            else:
                return json.dumps({'error': "No open files found against this investment", 'status': 400})

    @api.model
    def investment_details(self, **kwargs):
        # partner = self.env['res.partner'].browse(self.env.user.partner_id.id)
        investment = self.env['investment'].sudo().browse(kwargs['investment_id'])
        open_files = self.env['investor.file'].sudo().search([('investment_id', '=', investment.id)])
        if investment:
            investment_data = []
            inventory_data = []
            for file in open_files:
                if file.state == 'open':
                    state = 'Available'
                elif file.state == 'issued':
                    state = 'Issued'
                else:
                    state = 'In Process'

                inventory = {'state': state,
                             'investor_file_id': file.id,
                             'booking_date': file.booking_date,
                             'sector': file.sector_id.name,
                             'street': file.street_id.name,
                             'category': file.category_id.name,
                             'size': file.size_id.name,
                             'product': file.unit_category_type_id.name,
                             'plot_no': file.inventory_id.name,
                             'net_sale_amount': file.net_sale_amount,
                             }
                inventory_data.append(inventory)

            option = ''
            reservation_type = ''
            if investment.options == 'full':
                option = 'Full Payment'
            elif investment.options == 'down':
                option = 'Down Payment'

            if investment.reservation_type == 'unit':
                reservation_type = 'Unit Reservation'
            elif investment.reservation_type == 'bulk':
                reservation_type = 'Unit Reservation'

            investment = {
                'investment_id': investment.id,
                'investment_no': investment.name,
                'grace_period': investment.grace_period,
                'interval': investment.interval_id.nom,
                'total_installment': investment.total_installment,
                'options': option,
                'reservation_type': reservation_type,
                'society': investment.society_id.name or '',
                'phase': investment.phase_id.name or '',
                'sector': investment.sector_id.name or '',
                'category_id': investment.category_id.name or '',
                'booking_date': investment.booking_date or '',
                'start_date': investment.start_date or '',
                'total_amount': investment.total_amount,
                'down_payment': investment.down_payment,
                'balance_amount': investment.balance_amount,
                'paid_amount': sum(investment.investment_plan_ids.mapped('amount_paid')),
                'due_amount': sum(investment.investment_plan_ids.mapped('residual')),
                'no_of_units': investment.no_of_units,
                'investor_unit_price': investment.investor_unit_price,
                'inventory_data': inventory_data
            }
            investment_data.append(investment)

            return investment_data
        else:
            return json.dumps({'error': "No data found against this investment", 'status': 400})

    def _return_response(self, request, response, message):
        _logger.error(message)
        response['request'] = request
        response['message'] = message
        return json.dumps(response)

    @api.model
    def create_investment_request(self, **kwargs):
        qcontext = kwargs
        response = {}
        if qcontext.get('otp', False) and qcontext.get('request_id', False):
            application = self.env['investor.request.data'].browse(int(qcontext['request_id']))
            investment_request = self.env['unit.swapping.request'].sudo()
            data = []
            if application:
                if application.auth_otp == qcontext['otp']:
                    partner = self.env['res.member'].sudo().browse(application.partner_id.id)
                    investment = application.sudo().investment_id
                    for investor_file in application.sudo().investor_file_ids:
                        open_file = {'check': True,
                                     'transaction_type': 'open_file',
                                     'investment_id': investor_file.investment_id.id,
                                     'investor_file_id': investor_file.id,
                                     'sector_id': investor_file.sector_id.id,
                                     'category_id': investor_file.category_id.id,
                                     'unit_category_type_id': investor_file.unit_category_type_id.id,
                                     'unit_class_id': investor_file.unit_class_id.id,
                                     'size_id': investor_file.size_id.id,
                                     'inventory_id': investor_file.inventory_id.id,
                                     }
                        data.append((0, 0, open_file))
                        investor_file.state = 'in_process'

                    if investment:
                        investment_request = investment_request.create({
                            'from_app': True,
                            'project_type': investment.project_type,
                            'transaction_type': 'open_file',
                            'applicable_on': 'investment',
                            'investment_id': investment.id,
                            'investor_id': investment.partner_id.id,
                            'is_transferee_partner': True if partner else False,
                            'transferee_partner_id': partner.id if partner else False,
                            'transferee_name': partner.name if partner else application.member_name,
                            'transferee_company_type': partner.company_type if partner else application.member_type,
                            'transferee_mobile': partner.mobile if partner else application.mobile,
                            'transferee_email': partner.email if partner else application.email,
                            'transferee_gender': partner.gender if partner else application.gender,
                            'transferee_relation_name': partner.relation_name if partner else application.father_name,
                            'transferee_cnic_number': partner.cnic if partner else application.cnic,
                            # addition fields to write if existing member
                            'transferee_street': partner.street if partner else '',
                            'transferee_street2': partner.street2 if partner else '',
                            'transferee_city_id': partner.city_id.id if partner else False,
                            'transferee_zip': partner.zip if partner else '',
                            'transferee_state_id': partner.state_id.id if partner else False,
                            'transferee_country_id': partner.country_id.id if partner else False,
                            'kin_name': partner.kin_name if partner else '',
                            'kin_cnic': partner.kin_cnic if partner else '',
                            'kin_member_relation': partner.kin_member_relation if partner else '',
                            'kin_mobile': partner.kin_mobile if partner else '',
                            'other_relation': partner.other_relation if partner else '',

                            'unit_swapping_request_lines': data
                        })

                    response['request'] = "Success"
                    response['file_request_id'] = investment_request.id
                    return json.dumps(response)

                else:
                    try:
                        attempts = int(qcontext.get('attempts'))
                    except:
                        attempts = 0

                    qcontext['attempts'] = attempts + 1
                    if qcontext['attempts'] < 3:
                        response['attempts']
                        response['is_otp'] = True
                        response['request_id'] = application.id
                        return self._return_response("Fails", response,
                                                     f"Wrong OTP attempt. {qcontext['attempts']}/3")
                    else:
                        application.unlink()
                        return self._return_response("Fails", response,
                                                     f"Three consecutive wrong attempts.Terminating Process.")
            else:
                return self._return_response("Fails", response,
                                             "Your request is maybe expired.Please Try again.")

        if qcontext.get('transaction_type', False) == 'open_file':
            member_data = kwargs['member_data']
            partner = self.env['res.member'].sudo().search([('cnic', '=', member_data[0].get('cnic'))], limit=1)
            investment = self.env['investment'].sudo().browse(kwargs['investment_id'])
            investor_files_ids = []
            for rec in kwargs['open_files']:
                if rec['check'] == True:
                    investor_file = self.env['investor.file'].sudo().browse(rec['investor_file_id'])
                    if investment == investor_file.investment_id:
                        investor_files_ids.append(investor_file.id)
                    else:
                        raise ValidationError('Please select valid investor files to create request.')

            if self.env.user.partner_id.mobile:
                number = self.env.user.partner_id.mobile.replace(' ', '').replace('-', '').replace('+', '')
                if number.startswith("92"):
                    number = number.replace("92", "0")
                elif number.startswith("0092"):
                    number = number.replace("0092", "0", 1)

                try:
                    otp = str(random.randint(10000, 99999))
                    partner.env['investor.request.data'].search([('partner_id', '=', partner.id)]).unlink()
                    request_id = self.env['investor.request.data'].create({
                        'partner_id': partner.id,
                        'investment_id': investment.id,
                        'investor_file_ids': investor_files_ids,
                        'is_member': True if partner else False,
                        'member_name': partner.name if partner else member_data[0].get('member_name'),
                        'member_type': partner.company_type if partner else member_data[0].get('member_type'),
                        'mobile': partner.mobile if partner else member_data[0].get('mobile'),
                        'email': partner.email if partner else member_data[0].get('email'),
                        'gender': partner.gender if partner else member_data[0].get('gender'),
                        'father_name': partner.relation_name if partner else member_data[0].get('father_name'),
                        'cnic': partner.cnic if partner else member_data[0].get('cnic'),
                        'auth_otp': otp
                    })
                    # self.env.user.partner_id.env['tools.mixin'].sudo().simple_send(
                        # f"Your four digit otp number is : {otp}", number)
                    # self.env.user.partner_id.env['tools.mixin'].sudo().cequens_otp_send(
                        # f"Your four digit otp number is : {otp}", number)


                except:
                    return self._return_response("Fails", response,
                                                 f"We are not able to send OTP on your Mobile number.Please contact with Helpline.")

                response['is_otp'] = True
                response['request_id'] = request_id.id
                return self._return_response("Success", response, f"OTP has sent to mobile # {number}")

            else:
                return self._return_response("Fails", response,
                                             f"Your Mobile number is not register.Please contact with Helpline.")

        # for rec in record:
        #     for line in rec.unit_swapping_request_lines.filtered(lambda l: l.check == True):
        #         if rec.transaction_type == line.transaction_type and rec.state != 'approve':
        #             raise ValidationError(
        #                 _("Request already generated of Investment and is in 'Draft' state : %s" % (record.investment_id.name)))

    @api.model
    def request_history(self):
        investments = self.env['investment'].sudo().search([('partner_id.partner_id', '=', self.env.user.partner_id.id)])
        requests_history = self.env['unit.swapping.request'].sudo().search(
            [('investment_id', 'in', investments.ids), ('transaction_type', '=', 'open_file')])
        data = []
        for req in requests_history:
            inventory_details = []
            for line in req.unit_swapping_request_lines:
                vals = {'plot_no': line.inventory_id.name,
                        'sector': line.sector_id.name,
                        'product': line.unit_category_type_id.name,
                        'category': line.category_id.name,
                        'size': line.size_id.name,
                        }
                inventory_details.append(vals)

            if req.transaction_type == 'open_file':
                transaction_type = 'File Issuance'
            else:
                transaction_type = 'N/A'
            requests = {'request_no': req.name,
                        'request_id': req.id,
                        'transaction_type': transaction_type,
                        'appointment_date': str(req.appointment_date) if req.appointment_date else '',
                        'request_state': req.state,
                        'investment_name': req.investment_id.name,
                        'investment_id': req.investment_id.id,
                        'investor_name': req.investor_id.display_name,
                        'investor_id': req.investor_id.id,
                        'inventory_details': inventory_details,
                        }
            data.append(requests)
        if data:
            return json.dumps(data)
        else:
            return json.dumps({'error': "No request history.", 'status': 400})

    @api.model
    def payment_history(self):
        investments = self.env['investment'].sudo().search([('partner_id.partner_id', '=', self.env.user.partner_id.id)])
        investment_data = []
        for inv in investments:
            if inv.investment_payment_view_ids:
                data = []
                for line in inv.investment_payment_view_ids:
                    payment = {
                        'investment_id': line.investment_id.id,
                        'investment_no': line.investment_id.name,
                        'payment_date': str(line.payment_date),
                        'payment_id': line.payment_id.id,
                        'payment_no': line.payment_id.name,
                        'mode_of_payment': line.payment_id.mode_of_payments,
                        'invoice_id': line.move_id.id,
                        'invoice_no': line.move_id.name,
                        'payment_amount': line.payment_amount,
                    }
                    data.append(payment)
                investment = {'investment_name': inv.name,
                              'investment_id': inv.id,
                              'total_deal_amount': inv.total_amount,
                              'paid_amount': sum(inv.investment_plan_ids.mapped('amount_paid')),
                              'due_amount': sum(inv.investment_plan_ids.mapped('residual')),
                              'investor_name': inv.partner_id.investor_id,
                              'investor_id': inv.partner_id.id,
                              'sector_id': inv.sector_id.id,
                              'sector_name': inv.sector_id.name,
                              'payments': data
                              }
                investment_data.append(investment)
        if investment_data:
            return json.dumps(investment_data)
        else:
            return json.dumps({'error': "No payment history.", 'status': 400})

    def get_authorised_person(self):
        partner = self.env['res.member']._from_login_partner()
        if partner.authorised_representative_ids:
            for line in partner.authorised_representative_ids.filtered(lambda l: l.status == 'active')[-1]:
                authorised_person = [{
                    'name': line.name,
                    'mobile': line.mobile,
                    'cnic': line.cnic,
                    'street': line.street,
                    'city': line.city,
                    'state': line.state,
                    'country': line.country,
                    'document': base64.encodebytes(line.document).decode('utf-8') if line.document else ''
                }]
                if authorised_person:
                    return json.dumps(authorised_person)
                else:
                    return json.dumps({'error': "No data found for authorised person.", 'status': 400})


class InvestmentLine(models.Model):
    _name = 'investment.line'
    _description = 'Investment Line'

    sector_id = fields.Many2one('sector')
    street_id = fields.Many2one('street')
    size_id = fields.Many2one('unit.size', 'Size', store=True, related="inventory_id.size_id", readonly=False)
    unit_category_type_id = fields.Many2one('unit.category.type', store=True,
                                            related="inventory_id.unit_category_type_id", readonly=False)
    unit_class_id = fields.Many2one('unit.class', store=True, related="inventory_id.unit_class_id", readonly=False)
    category_id = fields.Many2one('plot.category', 'Category', store=True, related="inventory_id.category_id",
                                  readonly=False)
    inventory_id = fields.Many2one('plot.inventory')
    no_of_units = fields.Integer('No. of Units', default=1)
    list_price = fields.Float(store=True, compute='_sale_amount')
    price_list_id = fields.Many2one('price.list', compute='_price_list', store=True, readonly=False)
    investor_price = fields.Float(store=True, readonly=False)
    deal_price = fields.Float(compute='_compute_deal_price', store=True, readonly=False)
    reservation_type = fields.Selection([
        ('unit', 'Unit Reservation'),
        ('bulk', 'Bulk Reservation'),
        ('both', 'Both')
    ], related='investment_id.reservation_type', store=True)

    investment_id = fields.Many2one('investment')

    @api.onchange('sector_id', 'street_id', 'category_id', 'unit_category_type_id')
    def _phase_domain(self):
        if self.street_id:
            return {'domain': {
                'inventory_id': [('street_id', '=', self.street_id.id),
                                 ('state', '=', 'avalible_for_sale')]
            }
            }
        elif self.category_id and not self.unit_category_type_id:
            return {'domain': {
                'inventory_id': [('sector_id', '=', self.sector_id.id),
                                 ('category_id', '=', self.category_id.id),
                                 ('state', '=', 'avalible_for_sale')]
            }
            }
        elif self.category_id and self.unit_category_type_id:
            return {'domain': {
                'inventory_id': [('sector_id', '=', self.sector_id.id),
                                 ('category_id', '=', self.category_id.id),
                                 ('unit_category_type_id', '=', self.unit_category_type_id.id),
                                 ('state', '=', 'avalible_for_sale')]
            }
            }
        else:
            return {'domain': {
                'sector_id': [('phase_id', '=', self.investment_id.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'inventory_id': [('sector_id', '=', self.sector_id.id),
                                 ('state', '=', 'avalible_for_sale')]
            }
            }

    @api.depends('no_of_units', 'investor_price')
    def _compute_deal_price(self):
        for rec in self:
            rec.deal_price = rec.no_of_units * rec.investor_price

    @api.depends('unit_category_type_id', 'category_id', 'investment_id.booking_date')
    def _price_list(self, check=True):
        for rec in self:
            if rec.unit_category_type_id and rec.category_id:
                record = rec.env['price.list'].search([
                    '|',
                    '&',
                    ('starting_date', '<=', rec.investment_id.booking_date),
                    ('end_date', '=', False),
                    '&',
                    ('starting_date', '<=', rec.investment_id.booking_date),
                    ('end_date', '>=', rec.investment_id.booking_date),
                ])
                record = record.search([
                    ('society_id', '=', rec.investment_id.society_id.id),
                    ('phase_id', '=', rec.investment_id.phase_id.id),
                    ('id', 'in', record.ids)
                ])

                record = record.mapped('id')

                if not record:
                    pass
                    # raise ValidationError(_("Price List of relevant date does not exist"))
                if len(record) > 1:
                    pass
                    # raise ValidationError(_("Our date is falling between to active price lists ,Something is going wrong"))
                if check:
                    if len(record) == 1:
                        rec.price_list_id = record[0]
                    else:
                        rec.price_list_id = False
            else:
                rec.price_list_id = False

    @api.depends('investment_id.society_id', 'investment_id.phase_id', 'category_id', 'unit_category_type_id',
                 'inventory_id', 'price_list_id')
    def _sale_amount(self):
        for recs in self:
            recs.list_price = 0
            if recs.price_list_id:
                for rec in recs.price_list_id.pricelist_line:
                    if recs.price_list_id.price_list_type == 'unit':
                        if (rec.size_id == recs.size_id
                                and rec.category_id == recs.category_id
                                and rec.sector_id == recs.sector_id
                                and rec.unit_inventory_id == recs.inventory_id
                                and rec.starting_date <= recs.investment_id.booking_date <= rec.end_date
                        ):
                            recs.list_price = rec.price
                    else:
                        if (rec.category_id == recs.category_id
                                and rec.sector_id == recs.sector_id
                                and rec.unit_category_type_id == recs.unit_category_type_id
                        ):
                            recs.list_price = rec.price


class InvestmentPlan(models.Model):
    _name = 'investment.plan'
    _description = 'Investment Plan'

    date = fields.Date(required=True)
    amount = fields.Float()
    installment_number = fields.Integer(readonly=False)
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', 'Ref')
    state = fields.Char(string='Status', readonly=False, related='invoice_id.invoice_way_type')
    # installment_type = fields.Selection([
    #     ('down', 'Down Payment'),
    #     ('installment', 'Investment Installment'),
    #     ('adjustment', 'Investment Adjustment'),
    # ])
    installment_type = fields.Selection([
        ('down', 'Down Payment'),
        ('installment', 'Investment Installment'),
        ('adjustment', 'Investment Adjustment'),
        ('balloon', 'Balloon'),
        ('final', 'Final Payment'),
        ('possession_amount', 'Possession'),
        ('balloting_amount', 'Balloting'),
        ('confirmation_amount', 'Confirmation')
    ])
    invoice = fields.Char(related='invoice_id.name', store=True, readonly=False)

    payment_date = fields.Date('Payment Date', store=True, compute='_payment_date', readonly=False)
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('installment', 'Installment'),
        ('transfer_application', 'Transfer Application'),
        ('others', 'Others'),
    ], related='invoice_id.property_invoice_type', store=True, readonly=False, string='Invoice Type')
    amount_paid = fields.Float('Amount Paid', store=True, compute='_invoice_id_data', readonly=False)
    residual = fields.Float('Amount Due', store=True, compute='_invoice_id_data', readonly=False)
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=False, copy=False, tracking=True,
        related='invoice_id.payment_state')
    file_adjusted_amount = fields.Float()
    adjustment_amount = fields.Float()
    balance_amount = fields.Float()
    double_check_paid_amount = fields.Boolean(compute="_double_check_paid_amount")
    installment_name = fields.Char()
    investment_id = fields.Many2one('investment')

    @api.depends('invoice_created', 'invoice_id', 'amount_paid')
    def _payment_date(self):
        for rec in self:
            if rec.invoice_created:
                date = rec.env['account.payment'].search([
                    # ('id', 'in', rec.invoice_id.payment_ids.ids),
                    ('state', '=', 'paid'),
                    ('invoice_ids.name', '=', rec.invoice_id.name)
                ], limit=1, order='id desc')

                rec.payment_date = dateutil.parser.parse(str(date.date)) if date else ''
            else:
                rec.payment_date = ''

    @api.depends('invoice_id', 'invoice_id.amount_residual')
    def _invoice_id_data(self):
        for rec in self:
            rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
            rec.residual = rec.invoice_id.amount_residual

    def _double_check_paid_amount(self):
        for rec in self:
            if rec.invoice_id and rec.amount_paid != rec.invoice_id.amount_total - rec.invoice_id.amount_residual:
                rec._invoice_id_data()
            rec.double_check_paid_amount = True

    def unlink(self):
        for rec in self:
            if rec.invoice_created:
                raise UserError(_('You cannot delete record when invoice is created!'))

        return super(InvestmentPlan, self).unlink()


class InvestmentHistory(models.Model):
    _name = 'investment.history'
    _description = 'Investment History'

    date = fields.Date()
    transaction_type = fields.Selection([
        ('investor', 'Investor Settlement'),
        ('customer', 'File Adjustment'),
        ('cancel', 'Cancel'),
    ])
    payment_date = fields.Date()
    old_balance = fields.Float()
    new_balance = fields.Float()
    amount = fields.Float('Old Installment')
    new_amount = fields.Float()
    payment_received = fields.Float()
    installment_number = fields.Integer()
    file_id = fields.Many2one('file')

    investment_id = fields.Many2one('investment')


class InvestmentPaymentMode(models.Model):
    _name = 'investment.payment.mode'
    _description = "Investment Payment Mode"

    type = fields.Selection([('cash', 'Cash'),
                             ('cheque', "Cheque"),
                             ('adjustment', "Adjustment"),
                             ('other', "Others"), ('credit_sale', 'Credit Sales')], default='cash', required=True)
    check_date = fields.Date('Cheque Date')
    amount = fields.Float()
    calculation_done = fields.Boolean()

    investment_id = fields.Many2one('investment')

    # def populate_payment_field(self):
    #     payment = self.env['account.payment'].search([
    #         ('mode_of_payment', '!=', False),
    #         ('state', '=', 'draft')]).filtered(lambda s: self.id in s.mode_of_payment.ids)
    #
    #     if len(payment) > 1:
    #         raise ValidationError(_("Registration must attach with only one payment in draft mode."))
    #     if not payment.multi_invoice_ids.payment_amount:
    #         raise ValidationError(_("Please select the invoice first."))
    #
    #     payment.amount = self.amount
    #     payment.multi_invoice_ids.payment_amount = self.amount

    # @api.onchange('type')
    # def _onchange_product_line(self):
    #     if not self.calculation_done:
    #         total_to_adjust = sum(self.investment_id.investment_line_ids.mapped('total'))
    #         total_to_subtract = sum(self.investment_id.mode_of_payment.mapped('amount'))
    #         self.amount = total_to_adjust - total_to_subtract
    #         self.calculation_done = True


class InvestmentPayment(models.TransientModel):
    _name = "investment.payment"
    _description = "Investment Payment"

    investment_id = fields.Many2one('investment', string="Investment No.", required=True)
    partner_id = fields.Many2one('res.investor', string="Investor", related='investment_id.partner_id', store=True)
    date = fields.Date(required=True)
    total_amount = fields.Float(related='investment_id.total_amount')
    payment_amount = fields.Float(required=True)

    def create_payment(self):
        payment = self.env['account.payment'].create({
            'partner_id': self.partner_id.partner_id.id,
            'partner_type': 'customer',
            'amount': round(self.payment_amount),
            'payment_date': self.date,
            'mode_of_payments': 'cash',
            'payment_category': 'inv_payment',
            'payment_type': 'inbound',
            'memo': self.investment_id.sequence_no,
            'journal_id': self.investment_id.journal_id.id,
            'investment_id': self.investment_id.id,
            'company_id': self.env.company.id,
        })

        payment.post()

        investment_plan = self.investment_id
        if not investment_plan.investment_plan_ids:
            raise ValidationError("Installment plan does not exist.")
        if investment_plan and self.date < investment_plan.investment_plan_ids[0].date:
            investment_plan.investment_history_ids = [(0, 0, {
                'installment_number': investment_plan.investment_history_ids[
                                          -1].installment_number + 1 if investment_plan.investment_history_ids else 1,
                'date': self.date,
                'transaction_type': 'investor',
                'amount': round(investment_plan.balance_amount / investment_plan.total_installment),
                'new_amount': round(
                    (investment_plan.balance_amount - payment.amount) / investment_plan.total_installment),
                'old_balance': investment_plan.balance_amount,
                'new_balance': round(investment_plan.balance_amount - payment.amount),
                'payment_received': round(self.payment_amount),
                'payment_date': self.date,
                'investment_id': self.investment_id.id,
            })]

            investment_plan.balance_amount = round(investment_plan.balance_amount - payment.amount)
            if investment_plan.balance_amount < 0:
                raise ValidationError("Payment amount should be equal to or less than balance amount.")
            if investment_plan.balance_amount == 0:
                investment_plan.investment_plan_ids.unlink()
            if investment_plan.balance_amount > 0:
                investment_plan.investment_plan_ids.unlink()
                investment_plan.create_installment_plan()
        else:
            raise ValidationError('Advance payment date should be less than the installment date.')


class UnitCancelSwapHistory(models.Model):
    _name = 'unit.cancel.swap.history'
    _description = 'Unit Cancel Swap History'

    date = fields.Date()
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Plot Category')
    inventory_id = fields.Many2one('plot.inventory', default=False)
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size')
    unit_category_type_id = fields.Many2one('unit.category.type')
    unit_class_id = fields.Many2one('unit.class')
    investment_id = fields.Many2one('investment')

    new_inventory_id = fields.Many2one('plot.inventory')
    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation')
    ], default='swap')
    investor_unit_price = fields.Float()


class InvestorRequestData(models.TransientModel):
    _name = "investor.request.data"
    _description = "Investor Request Data"

    partner_id = fields.Many2one('res.member')
    auth_otp = fields.Char()
    resend = fields.Integer(default=0)
    investment_id = fields.Many2one('investment')
    investor_file_ids = fields.Many2many('investor.file')

    # member fields
    is_member = fields.Boolean()
    member_name = fields.Char()
    member_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owner'),
    ])
    mobile = fields.Char()
    email = fields.Char()
    gender = fields.Char()
    father_name = fields.Char()
    cnic = fields.Char()
