# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta



class ChangeInstallmentPlan(models.TransientModel):
    _name = 'change.installment.plan'
    _description = "Change Installment Plan"

    file_id = fields.Many2one('file', 'File Number',domain="[('state','!=','cancel')]")
    membership_id = fields.Many2one('res.member', string='Member No')
    tracking_id = fields.Char('Tracking ID')
    member_id = fields.Char('Member ID')

    return_line = fields.One2many('change.installment.plan.line', 'return_id', 'Initial Request')

    def key(self, priority):
        priority_dict = {
            1: 'name',
            2: 'membership_id',
            3: 'tracking_id',
        }
        return priority_dict[priority]

    def value(self, priority):
        priority_dict = {
            1: self.file_id.name,
            2: self.membership_id.ref,
            3: self.tracking_id,
        }
        return priority_dict[priority].strip()


    def search_file(self):
        self.return_line.unlink()

        priority_list = [self.file_id, self.membership_id, self.tracking_id, self.member_id]
        priority = 0
        record = []

        if not any(priority_list):
            raise ValidationError(_('Must populate one of the above field for search.'))

        for rec in priority_list:
            if not rec:
                priority = priority + 1
            elif rec:
                priority = priority + 1
                break

        if priority == 4:
            member_id = self.env['res.member'].search([('cnic', '=', self.member_id)])
            if member_id:
                record = self.env['file'].search([('membership_id', '=', member_id.id)])
        else:
            record = self.env['file'].search([(self.key(priority), '=', self.value(priority))])

        if record:
            for rec in record:
                self.return_line.create({
                    'file_id': rec.id,
                    'return_id': self.id
                })

        return {
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

class ReturnLine(models.TransientModel):
    _name = 'change.installment.plan.line'
    _description = "Change Installment Plan Line"

    membership_id = fields.Many2one('res.member', string='Member No',
                                        related='file_id.membership_id', readonly=True)
    sector_id = fields.Many2one('sector', related='file_id.sector_id', readonly=True)
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id',
                                    readonly=True)
    member_name = fields.Char(related='file_id.membership_id.name', readonly=True)
    file_id = fields.Many2one('file', readonly=True)
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id', readonly=True)
    return_id = fields.Many2one('change.installment.plan')

    # Payment Plan
    plan_description = fields.Char('Plan Description')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval')
    total_installment = fields.Integer('No of Installment')
    starting_date = fields.Date('Installment Starting Date')
    balance_amount = fields.Float('Balance Amount', compute='_compute_balance_amount', store=True)
    add_product_line = fields.One2many('add.product.line', 'return_id')
    balloting_amount = fields.Float()

    @api.depends('file_id', 'balloting_amount')
    def _compute_balance_amount(self):
        for rec in self:
            records = rec.file_id.installment_plan_ids.search([('file_id', '=', rec.file_id.id), ('invoice_created', '=', False)])
            self.balance_amount = sum(amount.amount for amount in records)

    @api.onchange('balloting_amount')
    def _onchange_balloting(self):
        for rec in self:
            if rec.balloting_amount and not rec.balloting_amount > rec.balance_amount:
                rec.balance_amount = rec.balance_amount - rec.balloting_amount
            else:
                raise ValidationError(_("Balance amount can't be in negative"))

    def create_new_installment_plan(self):
        installment_number = len(self.file_id.installment_plan_ids.search([('file_id', '=', self.file_id.id),
                                                                           ('invoice_created', '=', True)]))
        if installment_number > 1:
            installment_number += 1
        else:
            installment_number = 1

        new_installment_number = 1
        records = self.file_id.installment_plan_ids.search([('file_id', '=', self.file_id.id),
                                                            ('invoice_created', '!=', True)])
        records.unlink()

        if all([self.starting_date, self.interval_id, self.total_installment]) and self.file_id.active:
            dates = [fields.Date.from_string(self.starting_date)]

            for rec in range(1, self.total_installment):
                dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

            installment_count = 1
            balance_amount = self.balance_amount - self.balloting_amount
            for rec in dates:
                if balance_amount > 0:
                    self.file_id.installment_plan_ids.create({
                        'date': rec,
                        'installment_name': 'Installment' + ' '+str(installment_count),
                        'new_installment_number': new_installment_number,
                        'installment_number': installment_number,
                        'payment_status': 'not_paid',
                        'amount_paid': 0,
                        'amount': balance_amount / self.total_installment,
                        'file_id': self.file_id.id
                    })
                    installment_number = installment_number + 1
                    new_installment_number = new_installment_number + 1
                    installment_count += 1

            if self.balloting_amount > 0:
                plan = self.env['installment.plan'].search([('file_id', '=', self.file_id.id)])
                plan.create({
                    'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                    'installment_type': 'final',
                    'payment_status': 'not_paid',
                    'installment_number': installment_number,
                    'installment_name': 'Final',
                    'amount_paid': 0,
                    'amount': self.balloting_amount,
                    'file_id': self.file_id.id
                })
                self.file_id.balloting_amount = self.balloting_amount
            del installment_number
            del new_installment_number

            self.file_id.new_product_ids.unlink()

            for rec in self.add_product_line:
                if not rec.is_fully_paid:
                    number_of_time = rec.no_of_installment
                    per_installment = rec.per_installment
                    for line in self.file_id.installment_plan_ids:
                        if not line.invoice_created and number_of_time:
                            line.amount = line.amount + per_installment
                            number_of_time = number_of_time - 1

                self.file_id.new_product_ids.create({
                    'is_fully_paid': rec.is_fully_paid,
                    'product_id': rec.product_id.id,
                    'payment_type': rec.payment_type,
                    'value': rec.value,
                    'total': rec.total,
                    'initial_payment': rec.initial_payment,
                    'remaining_payment': rec.remaining_payment,
                    'no_of_installment': rec.no_of_installment,
                    'per_installment': rec.per_installment,
                    'file_id': self.file_id.id
                    })
        else:
            raise ValidationError(
                _("Installment Starting Date,Interval and total installment should be present"))


class AddProductLine(models.TransientModel):
    _name = 'add.product.line'
    _description = "Add Product Line"

    product_id = fields.Many2one('product.product', required=True, domain="[('is_include_property_system','=', True)]")
    payment_type = fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage')
    ], required=True)
    value = fields.Float()
    total = fields.Float(compute='_compute_total_value')
    initial_payment = fields.Float()
    remaining_payment = fields.Float(compute='_compute_remaining_value')
    no_of_installment = fields.Integer()
    per_installment = fields.Float(compute='_compute_per_installment')
    is_fully_paid = fields.Boolean(compute='_compute_remaining_value')
    return_id = fields.Many2one('change.installment.plan.line')

    @api.depends('initial_payment', 'total')
    def _compute_remaining_value(self):
        for rec in self:
            rec.remaining_payment = rec.total - rec.initial_payment
            rec.is_fully_paid = True if rec.total != 0.00 and rec.total == rec.initial_payment else False

    @api.depends('value', 'payment_type')
    def _compute_total_value(self):
        for rec in self:
            rec.total = rec.value if rec.payment_type == 'fix' else \
            [rec.return_id.file_id.sale_amount * rec.value / 100][0]

    @api.constrains('initial_payment', 'remaining_payment')
    def _check_percentage(self):
        if self.initial_payment > self.total:
            raise ValidationError(
                _("Initial Payment could not exceed the total payment of product."))

        if self.remaining_payment and not self.no_of_installment:
            raise ValidationError(
                _("No of Installment could not be zero if There is a remaining_payment unpaid."))

    @api.depends('remaining_payment','no_of_installment')
    def _compute_per_installment(self):
        for rec in self:
            rec.per_installment = rec.remaining_payment/rec.no_of_installment if rec.no_of_installment > 0 else 0

    @api.onchange('remaining_payment')
    def _onchanage_remaining_payment(self):
        for rec in self:
            if rec.remaining_payment:
                rec.no_of_installment = 1
            else:
                rec.no_of_installment = 0 
