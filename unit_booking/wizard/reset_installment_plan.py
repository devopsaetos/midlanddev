from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class ResetInstallmentPlan(models.TransientModel):
    _name = 'reset.installment.plan'
    _description = 'Reset Installment Plan'

    # selection fields
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine')], readonly=True)

    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')], string='Payment Type', readonly=True)

    # relational fields
    units_booking_id = fields.Many2one('units.booking', readonly=True)

    predefine_plan_id = fields.Many2one('predefine.plan', readonly=True)

    interval_id = fields.Many2one('payment.interval', 'Payment Interval')
    starting_date = fields.Date()

    # Numerical field
    total_installment = fields.Integer('No of Installment')
    sale_amount = fields.Float('Sale Amount')

    ttl_sale_amount = fields.Float('Total Sale Amount')
    net_sale_amount = fields.Float('Net Sale Amount')
    balloting_amount = fields.Float(string='Final Payment')

    initial_payment = fields.Float('Initial Payment')

    balance_amount = fields.Float('Balance Amount')

    discount_amount = fields.Float()
    balloon_payment = fields.Float()
    balloon_payment_start = fields.Integer()
    balloon_payment_interval = fields.Integer()
    balloon_payment_frequency = fields.Integer()
    primary_amount = fields.Float()
    primary_amount_interval = fields.Integer()
    primary_amount_frequency = fields.Integer()
    possession_amount = fields.Float()
    possession_amount_interval = fields.Integer()
    possession_amount_frequency = fields.Integer()
    confirmation_amount = fields.Float()
    confirmation_amount_interval = fields.Integer()
    confirmation_amount_frequency = fields.Integer()

    @api.onchange('discount_amount', 'confirmation_amount',
                  'possession_amount', 'primary_amount', 'balloon_payment', 'balloting_amount')
    def calculate_balance_amount(self):
        self.balance_amount = self.sale_amount
        self.balance_amount = self.balance_amount - self.initial_payment

        if self.discount_amount:
            self.balance_amount = self.balance_amount - self.discount_amount
            if self.sale_amount < self.discount_amount:
                raise ValidationError(_("Confirmation can't be greater than sale amount"))

        if self.confirmation_amount:
            self.balance_amount = self.balance_amount - self.confirmation_amount
            if self.sale_amount < self.confirmation_amount:
                raise ValidationError(_("Confirmation can't be greater than sale amount"))

        if self.possession_amount:
            self.balance_amount = self.balance_amount - self.possession_amount
            if self.sale_amount < self.possession_amount:
                raise ValidationError(_("Possession can't be greater than sale amount"))

        if self.primary_amount:
            self.balance_amount = self.balance_amount - self.primary_amount
            if self.sale_amount < self.primary_amount:
                raise ValidationError(_("Balloting can't be greater than sale amount"))

        if self.balloon_payment:
            self.balance_amount = self.balance_amount - (self.balloon_payment * self.balloon_payment_frequency)
            if (self.balloon_payment * self.balloon_payment_frequency) > self.sale_amount:
                raise ValidationError(_('Balloon Payment should not be greater than sale amount'))

        if self.balloting_amount:
            self.balance_amount = self.balance_amount - self.balloting_amount
            if self.sale_amount < self.balloting_amount:
                raise ValidationError(_('Final Payment should not be greater than sale amount'))

        if self.balance_amount <= 0:
            raise ValidationError(_('Balance amount should not be less than or equal to zero '))

    def reset_installment_plan(self):
        # Creating downpayment line
        if not self.initial_payment:
            raise ValidationError('Please enter down payment amount.')
        self.units_booking_id.unit_booking_plan_ids = [(5,)]

        self.units_booking_id.unit_booking_plan_ids.create({
            'date': self.units_booking_id.booking_date,
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
            'units_booking_id': self.units_booking_id.id
        })
        if self.confirmation_amount:
            installment_number = 3
            self.units_booking_id.unit_booking_plan_ids.create({
                'date': self.starting_date,
                'installment_number': 2,
                'installment_type': 'confirmation_amount',
                'installment_name': 'Confirmation',
                'payment_status': 'not_paid',
                'amount': self.confirmation_amount,
                'residual': self.confirmation_amount,
                'units_booking_id': self.units_booking_id.id
            })
        else:
            installment_number = 2

        if self.balance_amount > 0:
            if all([self.starting_date, self.interval_id, self.total_installment]):
                start_date = self.starting_date + relativedelta(months=+self.interval_id.nom)
                dates = [fields.Date.from_string(start_date)]

                interval = 0
                possession_interval = 0
                primary_interval = 0
                start_balloon_payment = False
                installment_count = 1
                balloon_interval = self.balloon_payment_interval

                for rec in range(1, self.total_installment
                                    + self.balloon_payment_frequency
                                    + self.possession_amount_frequency + self.primary_amount_frequency):
                    dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

                balance = self.balance_amount
                installment_amount = round(self.balance_amount / self.total_installment)

                for rec in dates:
                    if self.balloon_payment_start and not start_balloon_payment:
                        if installment_number == self.balloon_payment_start:
                            if balance:
                                amount = self.balloon_payment if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.units_booking_id.unit_booking_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloon',
                                'installment_name': 'Installment' + ' '+str(installment_count) if
                                self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'units_booking_id': self.units_booking_id.id
                            })
                            if self.predefine_plan_id.treat_balloon_as == 'installment':
                                installment_count += 1
                            interval = interval + 1
                            balloon_interval += self.balloon_payment_start
                            start_balloon_payment = True
                            installment_number = installment_number + 1
                            continue
                    if self.possession_amount:
                        if installment_number % self.possession_amount_interval == 0 \
                                and possession_interval < self.possession_amount_frequency:
                            if balance:
                                amount = self.possession_amount if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.units_booking_id.unit_booking_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'possession_amount',
                                'installment_name': 'Possession',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'units_booking_id': self.units_booking_id.id
                            })
                            possession_interval += 1
                            installment_number = installment_number + 1
                            continue

                    if self.balloon_payment:
                        if (installment_number % balloon_interval == 0
                                and interval < self.balloon_payment_frequency and start_balloon_payment):
                            if balance:
                                amount = self.balloon_payment if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.units_booking_id.unit_booking_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloon',
                                'installment_name':  'Installment' + ' '+str(installment_count) if
                                self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'units_booking_id': self.units_booking_id.id
                            })
                            if self.predefine_plan_id.treat_balloon_as == 'installment':
                                installment_count += 1
                            interval = interval + 1
                            balloon_interval += self.balloon_payment_interval
                            installment_number = installment_number + 1
                            continue

                    if self.primary_amount:
                        if installment_number % self.primary_amount_interval == 0 \
                                and primary_interval < self.primary_amount_frequency:
                            if balance:
                                amount = self.primary_amount if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.units_booking_id.unit_booking_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloting_amount',
                                'installment_name': 'Balloting',
                                'payment_status': 'not_paid',
                                'residual': amount,
                                'amount': amount,
                                'units_booking_id': self.units_booking_id.id
                            })
                            primary_interval += 1
                            installment_number = installment_number + 1
                            continue
                    if self.plan_type == 'custom':
                        self.units_booking_id.unit_booking_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' '+str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': installment_amount,
                            'tax_amount': 0,
                            'residual': installment_amount,
                            'units_booking_id': self.units_booking_id.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                    # regular installment line
                    else:
                        self.units_booking_id.unit_booking_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'installment',
                            'installment_name': 'Installment' + ' '+str(installment_count),
                            'payment_status': 'not_paid',
                            'amount': installment_amount,
                            'tax_amount': 0,
                            'residual': installment_amount,
                            'units_booking_id': self.units_booking_id.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                # final payment
                plan = self.env['unit.booking.plan'].search([('units_booking_id', '=', self.units_booking_id.id)])
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
                        'units_booking_id': self.units_booking_id.id
                    })

                # total = sum(self.units_booking_id.unit_booking_plan_ids.mapped('amount'))
                # if total < self.ttl_sale_amount:
                #     price = self.ttl_sale_amount - total
                #     self.units_booking_id.unit_booking_plan_ids.search([])[-1].update({
                #         'amount': round(self.balloting_amount) + price,
                #         # 'balance_amount': round(self.balance_amount / self.total_installment) + price,
                #         'residual': round(self.balloting_amount) + price,
                #     })
                # elif total > self.ttl_sale_amount:
                #     price = total - self.ttl_sale_amount
                #     self.units_booking_id.unit_booking_plan_ids.search([])[-1].update({
                #         'amount': round(self.balloting_amount) - price,
                #         # 'balance_amount': round(self.balance_amount / self.total_installment) - price,
                #         'residual': round(self.balloting_amount) - price,
                #     })
                del installment_number

                self.units_booking_id.installment_created = True
                self.units_booking_id.write({
                    'discount_amount': self.discount_amount,
                    'balloon_payment': self.balloon_payment,
                    ''
                    'balloting_amount': self.balloting_amount,
                    'primary_amount': self.primary_amount,
                    'possession_amount': self.possession_amount,
                    'confirmation_amount': self.confirmation_amount,
                    'balance_amount': self.balance_amount,
                    'interval_id': self.interval_id.id,
                    'starting_date': self.starting_date,
                    'total_installment': self.total_installment,
                    'balloon_payment_interval': self.balloon_payment_interval,
                    'balloon_payment_frequency': self.balloon_payment_frequency,
                    'primary_amount_interval': self.primary_amount_interval,
                    'primary_amount_frequency': self.primary_amount_frequency,
                    'possession_amount_interval': self.possession_amount_interval,
                    'possession_amount_frequency': self.possession_amount_frequency,
                    'reset_installment_plan': 'yes',
                    'balloon_payment_start': self.balloon_payment_start,
                })
            else:
                raise ValidationError(
                    _("Installment Starting Date,Interval and total installments should be there."))

