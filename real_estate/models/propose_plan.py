from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from lxml import etree as ET


class ProposePlan(models.Model):
    _name = 'propose.plan'
    _rec_name = 'total_installment'
    _description = 'Propose Plan'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('lock', 'Lock'),
        ('approve', 'Approve')
    ], default='draft')

    booking_date = fields.Date(default=fields.Date.today())
    include_installment = fields.Boolean()
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ])
    predefine_plan_id = fields.Many2one('predefine.plan')
    balloon_payment = fields.Float()
    balloon_payment_interval = fields.Integer()
    balloon_payment_frequency = fields.Integer()

    plan_description = fields.Char('Plan Description', store=True, readonly=False, related='predefine_plan_id.name')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', store=True, readonly=False, related='predefine_plan_id.interval_id')
    total_installment = fields.Integer('No of Installment', store=True, readonly=False, related='predefine_plan_id.total_installment')
    starting_date = fields.Date()
    initial_payment = fields.Float(store=True, readonly=False)
    final_payment = fields.Float(readonly=False)
    balance_amount = fields.Float(compute='_compute_payments')
    amount = fields.Float()
    custom_sale_amount = fields.Float(readonly=False)
    factor_id = fields.Many2many('factor')
    factor_perc = fields.Float(store=True)
    factor_amount = fields.Float(store=True, compute='_compute_factor')
    include_in_plan = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ])

    discount_amount = fields.Float(store=True, compute='_sale_amount', readonly=False)
    installment_created = fields.Boolean()
    add_custom_value = fields.Boolean()
    create_manually = fields.Boolean()

    price_list_id = fields.Many2one('price.list', store=True)
    crm_id = fields.Many2one('crm.lead', readonly=True)
    token_id = fields.Many2one('token.money')
    propose_installment_plan_ids = fields.One2many('propose.installment.plan', 'plan_id', readonly=True)
    manual_installment_plan_ids = fields.One2many('propose.installment.plan', 'plan_id')

    @api.constrains('starting_date')
    def _check_date_validity(self):
        if self.starting_date < fields.Date.today():
            raise ValidationError(_("Please give a valid date :)"))

    def lock(self):
        if not self.propose_installment_plan_ids:
            raise ValidationError('Please create installment plan first.')
        self.state = 'lock'
        if self.crm_id:
            self.crm_id.plan_locked = True
        if self.token_id:
            self.token_id.plan_locked = True

    def approve(self):
        self.state = 'approve'

    @api.depends('factor_id')
    def _compute_factor(self):
        for rec in self:
            if rec.factor_id:
                factor = list(rec.factor_id)
                for record in factor:
                    rec.factor_perc = record[-1].percentage + rec.factor_perc
                rec.factor_amount = rec.amount * (rec.factor_perc / 100)
                rec.factor_perc = 0
            else:
                rec.factor_amount = ''

    @api.onchange('add_custom_value')
    def _custom_amount(self):
        for rec in self:
            if rec.add_custom_value:
                rec.custom_sale_amount = ''
                rec.amount = ''
                rec.initial_payment = ''
                rec.final_payment = ''
                rec.balance_amount = ''
                rec.factor_id = False
                rec.factor_amount = ''
                if rec.add_custom_value == True and rec.custom_sale_amount:
                    rec.amount = rec.custom_sale_amount
            else:
                if rec.price_list_id:
                    rec._price_list()

    @api.onchange('create_manually')
    def _onchange_create_manually(self):
        for rec in self:
            rec.initial_payment = ''
            rec.final_payment = ''
            rec.balance_amount = ''
            if rec.create_manually == True:
                rec.balance_amount = rec.amount

    @api.onchange('predefine_plan_id')
    def _balloon_payment(self):
        for recs in self:
            if recs.predefine_plan_id:
                for pre_plan in recs.predefine_plan_id.predefine_plan_line_ids:
                    if recs.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                        recs.initial_payment = round(recs.amount * (
                                    pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                    if recs.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                        recs.final_payment = round(recs.amount * (
                                    pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)

                    if recs.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                        recs.balloon_payment = round(recs.amount * (
                                    pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        recs.balloon_payment_interval = pre_plan.interval
                        recs.balloon_payment_frequency = pre_plan.frequency
                        recs.include_installment = pre_plan.include_installment

    @api.depends('price_list_id', 'custom_sale_amount', 'add_custom_value', 'token_id.token_line_ids.category_id', 'token_id.token_line_ids.unit_category_type_id')
    def _sale_amount(self):
        for recs in self:
            factor = 0
            if recs.price_list_id and not recs.add_custom_value:
                for rec in recs.price_list_id.pricelist_line:
                    for inv_details in recs.token_id.token_line_ids or recs.crm_id.crm_lead_line:
                        if recs.price_list_id.price_list_type == 'generic':
                            if rec.unit_category_type_id == inv_details.unit_category_type_id \
                                    and rec.category_id == inv_details.category_id \
                                    and rec.sector_id == inv_details.sector_id:
                                recs.amount = rec.price
                                recs.balance_amount = recs.amount - recs.initial_payment - recs.final_payment
                                if recs.factor_id and recs.include_in_plan == 'yes':
                                    recs.amount = recs.amount + recs.factor_amount
                        if recs.price_list_id.price_list_type == 'unit':
                            if rec.size_id == inv_details.size_id \
                                    and rec.category_id == inv_details.category_id \
                                    and rec.sector_id == inv_details.sector_id \
                                    and rec.unit_inventory_id == inv_details.inventory_id \
                                    and rec.starting_date <= recs.booking_date \
                                    and rec.end_date >= recs.booking_date:
                                recs.amount = rec.price
                                recs.balance_amount = rec.price - recs.initial_payment - recs.final_payment
                                if recs.factor_id and recs.include_in_plan == 'yes':
                                    recs.amount = recs.amount + recs.factor_amount
                            elif rec.size_id == inv_details.size_id \
                                    and rec.category_id == inv_details.category_id \
                                    and rec.sector_id == inv_details.sector_id \
                                    and rec.unit_inventory_id == inv_details.inventory_id \
                                    and rec.starting_date <= recs.booking_date \
                                    and rec.end_date >= recs.booking_date:
                                recs.amount = rec.total_price
                                recs.balance_amount = recs.amount - recs.initial_payment - recs.final_payment
                                if recs.factor_id and recs.include_in_plan == 'yes':
                                    recs.amount = recs.amount + recs.factor_amount
            if recs.add_custom_value and recs.factor_id and recs.include_in_plan == 'yes':
                recs.amount = recs.amount + recs.factor_amount

                # for rec in recs.preference_ids:
                #     if rec.approved and rec.basis == 'fix':
                #         factor = factor + rec.value
                #     if rec.approved and rec.basis == 'percentage':
                #         factor = factor + (recs.sale_amount * rec.value) / 100
                # recs.factor_amount = factor
                # recs.ttl_sale_amount = round(recs.sale_amount + recs.factor_amount)
                # self._net_sale_amount()

    @api.onchange('booking_date')
    def _price_list(self, check=True):
        for rec in self:
            if rec.token_id:
                for recs in rec.token_id:
                    if recs.token_line_ids.unit_category_type_id and recs.token_line_ids.category_id and not rec.add_custom_value:
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
                            ('society_id', '=', recs.society_id.id),
                            ('phase_id', '=', recs.token_line_ids.phase_id.id),
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
            if rec.crm_id:
                for recs in rec.crm_id:
                    if recs.crm_lead_line.unit_category_type_id and recs.crm_lead_line.category_id and not rec.add_custom_value:
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
                            ('society_id', '=', recs.society_id.id),
                            ('phase_id', '=', recs.crm_lead_line.phase_id.id),
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

    @api.depends('initial_payment','final_payment', 'amount', 'discount_type','discount_amount')
    def _compute_payments(self):
        for rec in self:
            rec.balance_amount = rec.amount - rec.initial_payment - rec.final_payment
            rec.balance_amount = rec.balance_amount - [round(
                rec.amount * rec.discount_amount / 100) if rec.discount_type == 'percentage' else rec.discount_amount][0]
            if rec.balance_amount and rec.balance_amount < 0:
                raise ValidationError('Balance Amount cannot be less than zero')

    def reset_propose_installment_plan(self):
        self.propose_installment_plan_ids.unlink()
        self.installment_created = False

    def propose_installment_plan(self):
        if all([self.starting_date, self.interval_id, self.total_installment, self.amount]):
            dates = [fields.Date.from_string(self.starting_date)]

            interval = 0
            if self.plan_type == 'predefine' and self.predefine_plan_id:
                for rec in self.predefine_plan_id.predefine_plan_line_ids:
                    if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
                        interval_limit = round(self.total_installment / self.balloon_payment_interval)
                        self.balance_amount = self.balance_amount - (self.balloon_payment * interval_limit)
                if self.predefine_plan_id.include_in_plan == 'no':
                    for rec in range(1, self.total_installment + self.balloon_payment_frequency):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                else:
                    for rec in range(1, self.total_installment):
                        dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
            else:
                for rec in range(1, self.total_installment):
                    dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

            balance = self.balance_amount

            if self.initial_payment:
                self.propose_installment_plan_ids.create({
                    'date': self.booking_date,
                    'installment_type': 'down',
                    'installment_number': 0,
                    'amount': self.initial_payment,
                    'plan_id': self.id
                })

            installment_number = 1
            if self.factor_id and self.include_in_plan == 'yes':
                balance = balance + self.factor_amount
                installment_amount = round(balance / (self.total_installment - self.balloon_payment_frequency)) if not self.include_installment else round(balance / self.total_installment)
            else:
                installment_amount = round(balance / (self.total_installment - self.balloon_payment_frequency)) if not self.include_installment and self.predefine_plan_id.include_in_plan == 'yes' else round(balance / self.total_installment)

            for rec in dates:
                if self.plan_type == 'predefine' and self.env.ref('real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                    if installment_number % self.balloon_payment_interval != 0 or interval > self.balloon_payment_frequency:
                        print(rec)
                        if balance > 0:
                            amount = installment_amount if balance > installment_amount else balance
                        else:
                            amount = 0

                        self.propose_installment_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'amount': amount,
                            'plan_id': self.id
                        })

                    if installment_number % self.balloon_payment_interval == 0 and interval < self.balloon_payment_frequency:
                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.propose_installment_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'balloon' if  self.predefine_plan_id.include_in_plan == 'no' else 'installment',
                            'amount': amount + installment_amount if self.include_installment else amount,
                            'plan_id': self.id
                        })
                        interval = interval + 1

                    installment_number = installment_number + 1

                elif self.plan_type == 'custom':
                    self.propose_installment_plan_ids.create({
                        'date': rec,
                        'installment_number': installment_number,
                        'installment_type': 'installment',
                        'amount': round(balance / self.total_installment),
                        'plan_id': self.id
                    })
                    installment_number = installment_number + 1
                else:
                    self.propose_installment_plan_ids.create({
                        'date': rec,
                        'installment_number': installment_number,
                        'installment_type': 'installment',
                        'amount': round(self.balance_amount / self.total_installment),
                        'plan_id': self.id
                    })
                    installment_number = installment_number + 1

            plan = self.env['propose.installment.plan'].search([('plan_id','=',self.id)])
            if self.final_payment:
                plan.create({
                    'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                    'installment_type': 'final',
                    'installment_number': installment_number,
                    'amount': self.final_payment,
                    'plan_id': self.id
                })
            total_amount = 0
            if self.plan_type == 'predefine' and self.include_in_plan == 'no' or self.include_in_plan == False:
                total_amount = self.initial_payment + self.final_payment + self.balance_amount + (self.balloon_payment * interval)
            elif self.plan_type == 'predefine' and self.factor_id and self.include_in_plan == 'yes':
                total_amount = self.initial_payment + self.final_payment + self.balance_amount + (self.balloon_payment * interval) + self.factor_amount
            elif self.plan_type == 'custom' and self.factor_id and self.include_in_plan == 'yes':
                total_amount = self.initial_payment + self.final_payment + self.balance_amount + self.factor_amount
            else:
                total_amount = self.initial_payment + self.final_payment + self.balance_amount
            plan_total = sum(self.propose_installment_plan_ids.mapped('amount'))
            if plan_total < total_amount:
                price = total_amount - plan_total
                self.propose_installment_plan_ids.search([])[-1].update({
                    'amount': self.propose_installment_plan_ids.search([])[-1].amount + price
                })
            elif plan_total > total_amount:
                price = plan_total - total_amount
                self.propose_installment_plan_ids.search([])[-1].update({
                    'amount': self.propose_installment_plan_ids.search([])[-1].amount - price
                })

            del installment_number

            self.installment_created = True
        else:
            raise ValidationError(_("Installment Starting Date,Interval and total installments sould be there for active files"))

    @api.onchange('manual_installment_plan_ids')
    def _sale_amount_manually_cal(self):
        serial_number = 1
        for rec in self.manual_installment_plan_ids:
            rec.installment_number = serial_number
            if not rec.line_calculated:
                rec.percentage = 100 - sum(
                    [x.percentage for x in self.manual_installment_plan_ids if x.line_calculated])
                rec.line_calculated = True

                # total_amount = sum(self.manual_installment_plan_ids.mapped('amount_manual'))
                # if total_amount > self.net_sale_amount:
                #     raise ValidationError('Amount cannot exceed Net Sale Amount')
            serial_number = serial_number + 1

    @api.constrains('manual_installment_plan_ids')
    def _check_manual_installment_plan_ids(self):
        total_percentage = sum(self.manual_installment_plan_ids.mapped('percentage'))
        if total_percentage < 100 or total_percentage > 100:
            raise UserError(_('You cannot save record when installment is less than or greater than hundred ;)'))

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        res = super(ProposePlan, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

        id = self._context.get('active_id')
        crm_id = self.env['crm.lead'].browse(id)
        token_id = self.env['token.money'].browse(id)
        if crm_id or token_id:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='propose_plan_form']")
                doc.set('edit', 'true')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

        return res

    def unlink(self):
        for rec in self:
            if rec.state in ('lock','approve'):
                raise ValidationError("You cannot delete a plan once it is locked.")
        return super(ProposePlan, self).unlink()

class ProposeInstallmentPlan(models.Model):
    _name = 'propose.installment.plan'

    _rec_name = 'date'
    _description = "Propose Installment Plan"

    # serial_no = fields.Integer()
    line_calculated = fields.Boolean(default=False)
    installment_type = fields.Selection([
        ('down','Initial Payment'),
        ('installment','Installment'),
        ('balloon','Balloon'),
        ('final','Final Payment'),
    ], default='installment')
    product_id = fields.Many2one('product.product',
                                 default=lambda self: self.env.ref('real_estate.installment_product').id,
                                 domain="[('is_include_property_system','=', True)]"
                                 )
    date = fields.Date(required=True)
    percentage = fields.Float(digits=(2, 6))
    amount = fields.Float()
    amount_manual = fields.Float(string='Amount ', store=True, compute='_compute_amount')
    installment_number = fields.Integer(readonly=True)
    new_installment_number = fields.Integer()
    plan_id = fields.Many2one('propose.plan')

    @api.depends('plan_id.balance_amount', 'plan_id.create_manually', 'percentage')
    def _compute_amount(self):
        for rec in self:
            if rec.plan_id.create_manually == True:
                rec.amount_manual = round(rec.plan_id.balance_amount * (rec.percentage / 100))