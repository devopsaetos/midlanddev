from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class UnitBookingAllotment(models.Model):
    _name = 'unit.booking.allotment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Unit Booking Allotment'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    unit_selection_option = fields.Selection([
        ('scanning', 'Scanning'), ('range', 'Range')
    ])
    name = fields.Char(copy=False, readonly=True, index=True, tracking=True, default=lambda self: _('New'))

    # models relational fields
    unit_batch_id = fields.Many2one('unit.batch.generation')
    unit_booking_allotment_line_ids = fields.One2many('unit.booking.allotment.line', 'unit_booking_allotment_id')
    units_booking_id = fields.Many2one('units.booking')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoice', 'Invoice Generated'),
        ('closed', 'Closed'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', tracking=True)
    launch_type = fields.Selection([
        ('pre_launch', 'Pre Launch'),
        ('on_launch', 'On Launch'),
        ('post_launch', 'Post Launch'),
    ], related='unit_batch_id.launch_type', store=True)
    issue_to_subagent = fields.Boolean()
    society_id = fields.Many2one('society', domain=[('is_society', '=', True)],
                                 tracking=True, related='unit_batch_id.society_id', readonly=False,
                                 store=True)
    phase_id = fields.Many2one('society', tracking=True, related='unit_batch_id.phase_id', readonly=False,
                               store=True)
    sector_id = fields.Many2one('sector', tracking=True)
    category_id = fields.Many2one('plot.category', 'Category', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Dealer', tracking=True)
    partner_subagent_id = fields.Many2one('res.partner', string='Sub Dealer', tracking=True)
    main_dealer = fields.Many2one('res.partner', string='Dealer', tracking=True)
    booking_date = fields.Date('Allotment Date', tracking=True, default=fields.Date.today())
    installment_starting_date = fields.Date('Plan Starting Date', tracking=True)
    start_date = fields.Date('Start date', tracking=True, store=True)
    end_date = fields.Date('End date', tracking=True, store=True)
    total_amount = fields.Float('Total amount', compute='compute_deal_price', store=True, readonly=True,
                                tracking=True)
    down_payment = fields.Float('Down Payment', required=True, tracking=True)
    balance_amount = fields.Float(compute='_compute_balance_amount', store=True, tracking=True)
    amount_paid = fields.Float()
    total_installment = fields.Integer('No. of Installments', related='predefine_plan_id.total_installment', store=True)
    remaining_installments = fields.Integer('Remaining Installments', compute='_compute_remaining_installments')
    predefine_plan_id = fields.Many2one('predefine.plan', related='unit_batch_id.predefine_plan_id', readonly=False,
                                        store=True)
    interval_id = fields.Many2one('payment.interval', related='unit_batch_id.interval_id', store=True)
    no_of_units = fields.Integer(compute='_compute_total_units', store=True)
    no_of_files = fields.Integer(compute='_compute_no_of_files')
    no_of_issued_files = fields.Integer(compute='_compute_no_of_issued_files')
    amount_received = fields.Boolean()
    installment_created = fields.Boolean()
    options = fields.Selection([
        ('full', 'Full Payment'),
        ('down', 'Down Payment')
    ], tracking=True, default='down')
    journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ('cash', 'bank'))],
                                 tracking=True)

    notes = fields.Text('Internal Notes')
    booking_plan_ids = fields.One2many('booking.allotment.plan', 'booking_allotment_id')
    unit_swap_history = fields.One2many('unit.booking.swap.request.line', 'unit_booking_allotment_id')
    booking_allotment_history_ids = fields.One2many('booking.allotment.history', 'booking_allotment_id')
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')
    deal_pack_id = fields.Many2one('deal.pack', related='unit_batch_id.deal_pack_id', store=True, readonly=False)

    # Boolean fields
    include_installment = fields.Boolean()
    generate_invoices_for_installment = fields.Boolean(default=False)

    # predefine plan related field for calculation
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

    # rebate portion
    rebate_id = fields.Many2one('dealer.rebate')
    rebate_on_allotment_ids = fields.One2many('rebate.on.allotment', 'unit_booking_allotment_id')
    rebate_amount = fields.Float(tracking=True)
    separate_rebate = fields.Float(tracking=True)
    net_of_rebate = fields.Float(tracking=True)
    settlement_date = fields.Date()
    rebate_generated = fields.Boolean(default=False, tracking=True)
    rebate_settlement = fields.Selection([
        ('on_deal_start', 'Deal Start'),
        ('on_deal_close', 'Deal Close')
    ], tracking=True)

    def close_deal(self):
        for rec in self:
            rec.state = 'closed'

    @api.constrains('rebate_on_allotment_ids')
    def category_constrains(self):
        # for category in self.rebate_on_allotment_ids:
        #     record = self.rebate_on_allotment_ids.filtered(lambda s: s.category_id.id == category.category_id.id)
        #     if len(record) > 1:
        #         raise ValidationError(
        #             _(f"You can't have multiple lines with same Category '{record[1].category_id.name}'"))
        for rec in self:
            net_off_data = self.rebate_on_allotment_ids.filtered(lambda s: s.settlement_option == 'net_off')
            if rec.rebate_settlement == 'on_deal_close' and len(net_off_data) >= 1:
                raise ValidationError(
                    _(f"You can't apply 'NET OFF' rebate in line when settlement type is Deal Close"))

    @api.onchange('issue_to_subagent')
    def _dealer_sub_dealer_domain(self):
        if self.issue_to_subagent:
            return {'domain': {
                'partner_id': [('is_unit_booking_agent', '=', True), ('unit_booking_agent_type', '=', 'sub_agent'),
                               ('state', '=', 'approve')],
            }
            }
        elif not self.issue_to_subagent:
            return {'domain': {
                'partner_id': [('is_unit_booking_agent', '=', True), ('unit_booking_agent_type', '=', 'main_agent'),
                               ('state', '=', 'approve')],
            }
            }

    @api.onchange('rebate_id')
    def onchange_rebate(self):
        self.rebate_on_allotment_ids = [(5,)]
        if self.rebate_id:
            self.rebate_on_allotment_ids = [(0, 0, {
                'settlement_option': rec.settlement_option,
                'calculation_basis': rec.calculation_basis,
                'rate_calculation': rec.rate_calculation,
                'total_rebate': rec.total_rebate,
                'rebate_at_deal': rec.rebate_at_deal,
                'rebate_at_sale': rec.rebate_at_sale,
                'category_id': rec.category_id,
                'sector_id': rec.sector_id,
            }) for rec in self.rebate_id.rebate_line_ids]

    @api.onchange('partner_id')
    def onchange_issue_to_sub_agent(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.unit_booking_agent_type == 'sub_agent':
                rec.main_dealer = rec.partner_id.unit_booking_agent_id.id

    @api.constrains('start_date', 'end_date')
    def check_date_from_batch(self):
        for rec in self:
            if rec.start_date:
                if rec.unit_batch_id.open_date > rec.start_date or rec.start_date > rec.unit_batch_id.close_date:
                    raise ValidationError(
                        _(f'Start date should not smaller than ({rec.unit_batch_id.open_date}) and not greater to close date '
                          f'({rec.unit_batch_id.close_date})'))
            if rec.end_date:
                if rec.unit_batch_id.open_date > rec.end_date or rec.end_date > rec.unit_batch_id.close_date:
                    raise ValidationError(
                        _(f'End date should not be smaller than ({rec.unit_batch_id.open_date}) and not greater than batch close date '
                          f'({rec.unit_batch_id.close_date})'))

    @api.onchange('unit_batch_id')
    def onchange_batch(self):
        for rec in self:
            if rec.unit_batch_id:
                rec.start_date = rec.unit_batch_id.open_date
                rec.end_date = rec.unit_batch_id.close_date
                if (rec.unit_batch_id.plan_type == 'predefine' and rec.predefine_plan_id
                        and rec.env.ref('real_estate.confirmation_amount_product').id
                        in rec.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids):

                    rec.installment_starting_date = rec.start_date + \
                                                    relativedelta(
                                                        months=+rec.predefine_plan_id.confirmation_amount_period + 1)
                else:
                    rec.installment_starting_date = rec.start_date

    @api.depends('name', 'partner_id')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.name and record.name != 'New':
                name = "%s - %s" % (record.name, record.partner_id.name)
            result.append((record.id, name))
        return result

    def view_open_file(self):
        tree_view = (self.env.ref('unit_booking.units_booking_view_tree').id, 'list')
        form_view = (self.env.ref('unit_booking.units_booking_view_form').id, 'form')
        return {
            'name': _('Open Files'),
            'res_model': 'units.booking',
            'type': 'ir.actions.act_window',
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('unit_booking_allotment_id', '=', self.id)],
            'target': 'self'
        }

    def view_issued_file_to_customer(self):
        tree_view = (self.env.ref('unit_booking.units_booking_view_tree').id, 'list')
        form_view = (self.env.ref('unit_booking.units_booking_view_form').id, 'form')
        return {
            'name': _('Issued Files'),
            'res_model': 'units.booking',
            'type': 'ir.actions.act_window',
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('unit_booking_allotment_id', '=', self.id), ('state', '=', 'file_created')],
            'target': 'self'
        }

    def open_file_allotment(self):
        return {
            'name': _('QR') if self.unit_selection_option == 'scanning' else _('Range'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'open.file.qr.reading',
            'type': 'ir.actions.act_window',
            'context': {
                'default_batch_id': self.unit_batch_id.id,
                'default_allotment_id': self.id,
                'default_unit_selection_option': self.unit_selection_option,
                'from_allotment': True,
            },
            'target': 'new'
        }

    def open_file_issuance_to_agent(self):
        tree_view = (self.env.ref('unit_booking.booking_issuance_view_tree').id, 'list')
        form_view = (self.env.ref('unit_booking.booking_issuance_view_form').id, 'form')
        return {
            'name': _('File Issuance'),
            'res_model': 'unit.booking.issuance',
            'type': 'ir.actions.act_window',
            'context': {'default_unit_batch_id': self.unit_batch_id.id,
                        'default_unit_booking_allotment_id': self.id,
                        'default_partner_id': self.partner_id.id if self.partner_id.unit_booking_agent_type == 'main_agent' else self.main_dealer.id,
                        'default_partner_subagent_id': self.partner_id.id if self.partner_id.unit_booking_agent_type == 'sub_agent' else False,
                        'default_issue_to_subagent': self.issue_to_subagent,
                        'from_allotment_to_issuance': True},
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'domain': [('unit_batch_id', '=', self.unit_batch_id.id), ('unit_booking_allotment_id', '=', self.id)],
            'target': 'self'
        }

    @api.onchange('predefine_plan_id', 'total_amount')
    def _onchange_total_amount(self):
        for recs in self:
            for pre_plan in recs.predefine_plan_id.predefine_plan_line_ids:

                if recs.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                    recs.down_payment = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                              else pre_plan.value * recs.no_of_units)

                if recs.env.ref('real_estate.final_product').id == pre_plan.product_id.id:
                    recs.balloting_amount = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                  else pre_plan.value * recs.no_of_units)

                if recs.env.ref('real_estate.balloon_payment').id == pre_plan.product_id.id:
                    recs.balloon_payment = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                 else pre_plan.value * recs.no_of_units)
                    recs.balloon_payment_interval = pre_plan.interval
                    recs.balloon_payment_frequency = pre_plan.frequency
                    recs.balloon_payment_start = pre_plan.start_from
                    recs.include_installment = pre_plan.include_installment

                if recs.env.ref("real_estate.possession_amount_product").id == pre_plan.product_id.id:
                    recs.possession_amount = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                   else pre_plan.value * recs.no_of_units)
                    recs.possession_amount_interval = pre_plan.interval
                    recs.possession_amount_frequency = pre_plan.frequency

                if recs.env.ref("real_estate.confirmation_amount_product").id == pre_plan.product_id.id:
                    recs.confirmation_amount = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                     else pre_plan.value * recs.no_of_units)
                    recs.confirmation_amount_interval = pre_plan.interval
                    recs.confirmation_amount_frequency = pre_plan.frequency

                if recs.env.ref("real_estate.balloting_product").id == pre_plan.product_id.id:
                    recs.primary_amount = round(recs.total_amount * (
                            pre_plan.value / 100) if pre_plan.basis == 'percentage'
                                                else pre_plan.value * recs.no_of_units)
                    recs.primary_amount_interval = pre_plan.interval
                    recs.primary_amount_frequency = pre_plan.frequency
            if recs.unit_batch_id.plan_type == 'custom':
                recs.down_payment = round(recs.total_amount * (
                        recs.unit_batch_id.value / 100) if recs.unit_batch_id.initial_payment_basis == 'percentage' else recs.unit_batch_id.value)

    @api.depends('unit_booking_allotment_line_ids')
    def _compute_total_units(self):
        for rec in self:
            rec.no_of_units = len(rec.unit_booking_allotment_line_ids.mapped('units_booking_id'))

    def _compute_no_of_files(self):
        for rec in self:
            rec.no_of_files = len(rec.env['units.booking'].search([('unit_booking_allotment_id', '=', rec.id)]))

    def _compute_no_of_issued_files(self):
        for rec in self:
            rec.no_of_issued_files = len(rec.env['units.booking'].search([('unit_booking_allotment_id', '=', rec.id),
                                                                          ('state', '=', 'file_created')]))

    @api.depends('unit_booking_allotment_line_ids')
    def compute_deal_price(self):
        if self.unit_booking_allotment_line_ids:
            self.total_amount = sum(self.unit_booking_allotment_line_ids.mapped('price'))
            self._onchange_total_amount()

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(
            self.env['account.move'].search([('booking_allotment_id', '=', self.id),
                                             ('move_type', 'in', ['out_invoice', 'in_invoice'])]))

    @api.depends('booking_plan_ids')
    def _compute_remaining_installments(self):
        for rec in self:
            rec.remaining_installments = len(rec.booking_plan_ids.search(
                [('booking_allotment_id', '=', rec.id), ('installment_type', '=', 'installment'),
                 ('invoice_created', '!=', True)]))

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Booking Allotment Invoices'),
            'res_model': 'account.move',
            'domain': [('booking_allotment_id', '=', self.id)],
            'context': {'default_partner_id': self.partner_id.id},
        }

    @api.constrains('balance_amount')
    def check_balance_amount(self):
        if self.balance_amount < 0:
            raise ValidationError(_('Balance amount cannot be less than 0.'))

    # @api.constrains('rebate_amount')
    # def check_balance_amount(self):
    #     for rec in self:
    #         if rec.rebate_amount >= rec.down_payment:
    #             raise ValidationError(_(f'Rebate amount cannot be greater or equal to down payment'))

    @api.depends('total_amount', 'down_payment')
    def _compute_balance_amount(self):
        for rec in self:
            if rec.total_amount and rec.down_payment:
                rec.balance_amount = rec.total_amount - rec.down_payment
            else:
                rec.balance_amount = 0.0

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('booking.allotment') or _('New')
        result = super().create(vals_list)
        return result

    def rebate_credit_note(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner_id.id,
            'company_id': self.env.company.id,
            # 'branch_id': self.env.branch.id,
            'booking_allotment_id': self.id,
            'invoice_date': fields.Date.today(),
            'property_invoice_type': 'dealer_rebate',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                'name': self.env.ref('unit_booking.dealer_rebate').name,
                'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                'price_unit': self.net_of_rebate
            })],
        })
        invoice.action_post()

    def rebate_bill(self):
        rebate_invoice = self.env['account.move'].create({
            'partner_id': self.partner_id.id,
            # 'branch_id': self.env.branch.id,
            'move_type': 'in_invoice',
            'booking_allotment_id': self.id,
            'invoice_date': self.booking_date,
            'property_invoice_type': 'dealer_rebate',
            # 'journal_id': self.env.company.account_journal_id.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                'name': self.env.ref('unit_booking.dealer_rebate').name,
                'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                'price_unit': self.separate_rebate,
            })],
        })
        rebate_invoice.action_post()

    def generate_invoice(self):
        if self.rebate_settlement == 'on_deal_start':
            if self.rebate_amount == 0.00:
                raise ValidationError(_('Calculate rebate first'))
        if not self.booking_plan_ids:
            raise ValidationError(_('Create Installment Plan first.'))
        if not self.down_payment:
            raise ValidationError(_('Please enter down payment to generate invoice.'))
        if self.total_amount:
            prod = [(0, 0, {
                'product_id': self.env.ref('unit_booking.booking_allotment').id,
                'name': self.env.ref('unit_booking.booking_allotment').name,
                'account_id': self.env.ref('unit_booking.booking_allotment').property_account_income_id.id,
                'price_unit': self.down_payment
            })]
            invoice = self.env['account.move'].create({

                'partner_id': self.partner_id.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'out_invoice',
                'booking_allotment_id': self.id,
                'invoice_date': self.booking_date,
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
                'property_invoice_type': 'booking_allotment',
            })
            if self.net_of_rebate > 0 and self.rebate_settlement == 'on_deal_start':
                self.rebate_credit_note()
                self.rebate_generated = True
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
                        # 'branch_id': self.env.branch.id,
                        'currency_id': self.env.company.currency_id.id,
                        'payment_difference_handling': 'reconcile',
                        'communication': invoice.name,
                    })
                    payment.action_post()
            if self.separate_rebate > 0 and self.rebate_settlement == 'on_deal_start':
                self.rebate_bill()
                self.rebate_generated = True
            if self.booking_plan_ids[0].installment_type == 'down':
                self.booking_plan_ids[0].write({
                    'invoice_created': True,
                    'invoice_id': invoice.id,
                })
            # for rec in self.booking_plan_ids:
            #     if rec.installment_number == 0 and rec.invoice_created != True:
            #         rec.write({
            #             'invoice_created': True,
            #             'invoice_id': invoice.id,
            #         })
            initial_payment = 0
            prorate = self.down_payment / self.total_amount
            for rec in self:
                if rec.unit_booking_allotment_line_ids and rec.state != 'invoice':
                    for line in rec.unit_booking_allotment_line_ids:
                        if rec.unit_batch_id.plan_type == 'predefine' and rec.predefine_plan_id:
                            for pre_plan in rec.predefine_plan_id.predefine_plan_line_ids:
                                if rec.env.ref('real_estate.downpayment_product').id == pre_plan.product_id.id:
                                    initial_payment = round(line.price * (
                                            pre_plan.value / 100) if pre_plan.basis == 'percentage' else pre_plan.value)
                        if rec.unit_batch_id.plan_type == 'custom':
                            initial_payment = round(line.price * (
                                    rec.unit_batch_id.value / 100) if rec.unit_batch_id.initial_payment_basis == 'percentage' else rec.unit_batch_id.value)
                        line.units_booking_id.state = 'allotment'
                        line.units_booking_id.unit_booking_allotment_id = rec.id
                        line.units_booking_id.agent_id = rec.partner_id.id if rec.partner_id.unit_booking_agent_type == 'main_agent' else rec.main_dealer.id
                        line.units_booking_id.sub_agent_id = rec.partner_id.id if rec.partner_id.unit_booking_agent_type == 'sub_agent' else False,
                        line.units_booking_id.deal_pack_id = rec.deal_pack_id.id
                        line.units_booking_id.payment_type = 'installments' if self.options == 'down' else 'lump_sum'
                        line.units_booking_id.plan_type = 'predefine' if rec.predefine_plan_id else 'custom'
                        line.units_booking_id.booking_date = rec.start_date
                        line.units_booking_id.predefine_plan_id = rec.predefine_plan_id.id
                        line.units_booking_id.total_installment = rec.total_installment
                        line.units_booking_id.interval_id = rec.interval_id.id
                        line.units_booking_id.payment_states = 'open'
                        line.units_booking_id.sale_amount = line.price
                        line.units_booking_id.ttl_sale_amount = line.price
                        line.units_booking_id.net_sale_amount = line.price
                        line.units_booking_id.initial_payment = initial_payment
                        line.units_booking_id.balance_amount = line.price - initial_payment if self.options == 'down' else 0
                        line.units_booking_id.unit_booking_plan_ids.unlink()
                        line.units_booking_id.create_installment_plan()
                        line.units_booking_id.history_ids = [(0, 0, {
                            'state': 'allotment',
                            'print_state': '',
                            'date': fields.Date.today(),
                        })]
                        self.create_jv(line)

                if not rec.unit_booking_allotment_line_ids:
                    raise ValidationError('Please add inventory details.')

            self.booking_allotment_history_ids.create({
                'installment_number': 1,
                'date': fields.Date.today(),
                'transaction_type': 'investor',
                'amount': 0,
                'new_amount': round(self.balance_amount / self.total_installment) if self.total_installment > 0 else 0,
                'old_balance': self.total_amount,
                'new_balance': round(self.balance_amount),
                'payment_received': 0,
                'booking_allotment_id': self.id,
            })
            self.state = 'invoice'
            self.payment_states = 'open'

    def create_jv(self, line):
        if self.env.company.unit_booking_journal_id:
            if not self.env.company.unit_booking_journal_id.default_debit_account_id:
                raise ValidationError(_("Please select debit account in selected journal"))
            if not self.env.company.unit_booking_journal_id.default_credit_account_id:
                raise ValidationError(_("Please select credit account in selected journal"))
            move = {
                'date': fields.Date.today(),
                'journal_id': self.env.company.unit_booking_journal_id.id,
                'company_id': self.env.company.id,
                'move_type': 'entry',
                'state': 'draft',
                'ref': line.units_booking_id.sequence_number + '- ' + line.units_booking_id.name,
                'units_booking_id': line.units_booking_id.id,
                'line_ids': [(0, 0, {
                    'account_id': self.env.company.unit_booking_journal_id.default_credit_account_id.id,
                    'debit': line.units_booking_id.initial_payment}),
                             (0, 0, {
                                 'account_id': self.env.company.unit_booking_journal_id.default_debit_account_id.id,
                                 'credit': line.units_booking_id.initial_payment
                             })]
            }
            move_id = self.env['account.move'].create(move)

            move_id.action_post()
        else:
            raise ValidationError(_('Please Select Journal in configuration'))

    def set_predefine_value(self):
        for rec in self:
            rec.confirmation_amount = 0
            rec.confirmation_amount_interval = 0
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

    def reset_installment_plan(self):
        if len(self.booking_plan_ids.mapped('invoice_id').ids) > 1:
            raise ValidationError(_('You can not reset plan.Once, invoice created!'))
        self.booking_plan_ids.unlink()
        self.set_predefine_value()
        self._onchange_total_amount()
        self.installment_created = False

    def create_installment_plan(self):
        # Creating downpayment line
        if not self.down_payment:
            raise ValidationError('Please enter down payment amount.')

        self.booking_plan_ids.create({
            'date': self.booking_date,
            'installment_type': 'down',
            'installment_name': 'Booking',
            'installment_number': 1,
            'amount': self.down_payment,
            'amount_paid': 0,
            'balance_amount': self.down_payment,
            'residual': self.down_payment,
            'payment_status': 'not_paid',
            'booking_allotment_id': self.id
        })

        # confirmation payment line

        if self.unit_batch_id.plan_type == 'predefine' \
                and self.env.ref('real_estate.confirmation_amount_product').id \
                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            installment_number = 3
            self.booking_plan_ids.create({
                'date': self.start_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period),
                'installment_number': 2,
                'installment_type': 'confirmation_amount',
                'installment_name': 'Confirmation',
                'payment_status': 'not_paid',
                'amount_paid': 0,
                'balance_amount': self.confirmation_amount,
                'amount': self.confirmation_amount,
                'residual': self.confirmation_amount,
                'booking_allotment_id': self.id
            })
        else:
            installment_number = 2

        if self.balance_amount > 0:
            if all([self.installment_starting_date, self.interval_id, self.total_installment]):
                start_date = self.installment_starting_date
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
                            balance = balance - (self.possession_amount *
                                                                         self.possession_amount_frequency)

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

                # if self.booking_allotment_history_ids:
                #     balance = self.booking_allotment_history_ids[-1].new_balance

                for rec in dates:
                    # first balloon payment
                    if self.balloon_payment_start and not start_balloon_payment:
                        if installment_number == self.balloon_payment_start:
                            if balance:
                                amount = self.balloon_payment if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.booking_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloon',
                                'installment_name': 'Installment' + ' '+str(installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                'payment_status': 'not_paid',
                                'balance_amount': amount + installment_amount if self.include_installment else amount,
                                'residual': amount + installment_amount if self.include_installment else amount,
                                'amount': amount + installment_amount if self.include_installment else amount,
                                'booking_allotment_id': self.id
                            })
                            if self.predefine_plan_id.treat_balloon_as == 'installment':
                                installment_count += 1
                            interval = interval + 1
                            balloon_interval += self.balloon_payment_start
                            start_balloon_payment = True
                            installment_number = installment_number + 1
                            continue

                    if self.unit_batch_id.plan_type == 'predefine' \
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
                                self.booking_plan_ids.create({
                                    'date': rec,
                                    'installment_number': installment_number,
                                    'installment_type': 'possession_amount',
                                    'installment_name': 'Possession',
                                    'payment_status': 'not_paid',
                                    'amount_paid': 0,
                                    'balance_amount': amount,
                                    'residual': amount,
                                    'amount': amount,
                                    'booking_allotment_id': self.id
                                })
                                possession_interval += 1
                                installment_number = installment_number + 1
                                continue

                    if self.unit_batch_id.plan_type == 'predefine' \
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
                                self.booking_plan_ids.create({
                                    'date': rec,
                                    'installment_number': installment_number,
                                    'installment_type': 'balloting_amount',
                                    'installment_name': 'Balloting',
                                    'payment_status': 'not_paid',
                                    'amount_paid': 0,
                                    'balance_amount': amount,
                                    'residual': amount,
                                    'amount': amount,
                                    'booking_allotment_id': self.id
                                })
                                primary_interval += 1
                                installment_number = installment_number + 1
                                continue

                    if (self.unit_batch_id.plan_type == 'predefine' and self.env.ref(
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
                        #     self.booking_plan_ids.create({
                        #         'date': rec,
                        #         'installment_type': 'installment',
                        #         'installment_number': installment_number,
                        #         'installment_name': 'Installment' + ' '+str(installment_count),
                        #         'amount_paid': 0,
                        #         'balance_amount': amount,
                        #         'amount': amount,
                        #         'residual': amount,
                        #         'payment_status': 'not_paid',
                        #         'booking_allotment_id': self.id
                        #     })
                        #     installment_count += 1
                        #     installment_number = installment_number + 1
                        #     continue

                        if balance:
                            amount = self.balloon_payment if balance > installment_amount else balance
                        else:
                            amount = 0
                        self.booking_plan_ids.create({
                            'date': rec,
                            'installment_number': installment_number,
                            'installment_type': 'balloon',
                            'installment_name': 'Installment' + ' '+str(installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                            'payment_status': 'not_paid',
                            'amount_paid': 0,
                            'balance_amount': amount + installment_amount if self.include_installment else amount,
                            'residual': amount + installment_amount if self.include_installment else amount,
                            'amount': amount + installment_amount if self.include_installment else amount,
                            'booking_allotment_id': self.id
                        })
                        if self.predefine_plan_id.treat_balloon_as == 'installment':
                            installment_count += 1
                        interval = interval + 1
                        balloon_interval += self.balloon_payment_interval
                        installment_number = installment_number + 1
                        continue
                    else:
                        self.booking_plan_ids.create({
                            'date': rec,
                            'installment_type': 'installment',
                            'installment_number': installment_number,
                            'installment_name': 'Installment' + ' '+str(installment_count),
                            'amount': installment_amount,
                            'balance_amount': installment_amount,
                            'amount_paid': 0,
                            'residual': installment_amount,
                            'payment_status': 'not_paid',
                            'booking_allotment_id': self.id
                        })
                        installment_count += 1
                        installment_number = installment_number + 1
                # total = sum(self.booking_plan_ids.mapped('amount'))
                # if total < self.total_amount:
                #     price = self.total_amount - total
                #     self.booking_plan_ids.search([])[-1].update({
                #         'amount': round(self.balance_amount / self.total_installment) + price,
                #         'balance_amount': round(self.balance_amount / self.total_installment) + price,
                #         'residual': round(self.balance_amount / self.total_installment) + price,
                #     })
                # elif total > self.total_amount:
                #     price = total - self.total_amount
                #     self.booking_plan_ids.search([])[-1].update({
                #         'amount': round(self.balance_amount / self.total_installment) - price,
                #         'balance_amount': round(self.balance_amount / self.total_installment) - price,
                #         'residual': round(self.balance_amount / self.total_installment) - price,
                #     })
                # del installment_number

                plan = self.env['booking.allotment.plan'].search([('booking_allotment_id', '=', self.id)])
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
                        'booking_allotment_id': self.id
                    })
                    installment_count += 1

                total = sum(self.booking_plan_ids.mapped('amount'))
                if total < self.total_amount:
                    price = self.total_amount - total
                    self.booking_plan_ids.search([])[-1].update({
                        'amount': self.booking_plan_ids.search([])[-1].amount + price,
                        'residual': self.booking_plan_ids.search([])[-1].residual + price,
                        'balance_amount': self.booking_plan_ids.search([])[-1].balance_amount + price,
                    })
                elif total > self.total_amount:
                    price = total - self.total_amount
                    self.booking_plan_ids.search([])[-1].update({
                        'amount': self.booking_plan_ids.search([])[-1].amount - price,
                        'residual': self.booking_plan_ids.search([])[-1].residual - price,
                        'balance_amount': self.booking_plan_ids.search([])[-1].balance_amount - price,
                    })
                del installment_number

                self.installment_created = True
            else:
                raise ValidationError(
                    _("Installment Starting Date,Interval and total installments should be there."))

    def generate_invoice_for_plan(self):
        for rec in self:
            if rec.state == 'invoice':
                if rec.booking_plan_ids and rec.payment_states == 'open' and rec.society_id.company_id == self.env.company:
                    due_invoices = rec.booking_plan_ids.search([('date', '<=', fields.Date.today()),
                                                                ('invoice_created', '!=', True),
                                                                ('booking_allotment_id', '=', rec.id)])
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
                                'booking_allotment_id': rec.id,
                                # 'invoice_payment_ref': rec.sequence_no,
                                'partner_id': rec.partner_id.id,
                                # 'branch_id': self.env.branch.id,
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
                            raise 'There is some error: %s in auto invoice creation for installment' % (e)

                    rec.generate_invoices_for_installment = True
                if len(rec.booking_plan_ids.mapped('invoice_id')) == len(
                        rec.booking_plan_ids.filtered(
                            lambda l: l.booking_allotment_id == rec.id and l.invoice_created).mapped(
                            'invoice_created')):
                    rec.payment_states = 'close'
            else:
                raise ValidationError(_("Down Payment invoice is not generated"))

    @api.model
    def allotment_installment_invoices(self):
        # --------------------------------------
        date = self.env.ref('unit_booking.ir_cron_booking_allotment_invoices').till_date or fields.Date.today()
        # -----------------------------------------
        for rec in self.search([('state', '=', 'invoice')]):
            if rec.generate_invoices_for_installment:
                no_of_installment = []
                if rec.booking_plan_ids and rec.payment_states == 'open' and rec.society_id.company_id == self.env.company:
                    for installment in rec.booking_plan_ids:

                        if installment.date <= date and not installment.invoice_created:
                            try:
                                prod = [(0, 0, {
                                    'product_id': self.env.ref('unit_booking.booking_allotment_installment').id,
                                    'name': self.env.ref('unit_booking.booking_allotment_installment').name,
                                    'account_id': self.env.ref(
                                        'unit_booking.booking_allotment_installment').property_account_income_id.id,
                                    'price_unit': installment.balance_amount
                                })]

                                invoice = self.env['account.move'].create({
                                    'booking_allotment_id': rec.id,
                                    # 'invoice_payment_ref': rec.sequence_no,
                                    'partner_id': rec.partner_id.id,
                                    # 'branch_id': self.env.branch.id,
                                    'move_type': 'out_invoice',
                                    'journal_id': self.env.company.account_journal_id.id,
                                    'property_invoice_type': 'allotment_installment',
                                    'invoice_date': installment.date,
                                    'invoice_date_due': installment.date,
                                })
                                invoice.invoice_line_ids = prod

                                invoice.action_post()

                                installment.invoice_id = invoice.id

                                installment.invoice_created = True
                            except Exception as e:
                                raise 'There is some error: %s in auto invoice creation for installment' % (e)

                        no_of_installment.append(installment.invoice_created)
                else:
                    no_of_installment.append(False)

                if all(no_of_installment):
                    rec.payment_states = 'close'

    def calculate_fix_rebate(self, rec):
        record = self.unit_booking_allotment_line_ids
        calculated_rebate = 0.0
        # filtered out the required data from allotment lines
        if rec.sector_id:
            record = self.unit_booking_allotment_line_ids.filtered(
                lambda line: line.category_id == rec.category_id and line.sector_id == rec.sector_id)
        if not rec.sector_id:
            record = self.unit_booking_allotment_line_ids.filtered(lambda line: line.category_id == rec.category_id)
        if rec.rate_calculation == 'per_marla':
            for file in record:
                file_area = file.units_booking_id.unit_category_type_id.area_marla
                rebate_value = file_area * rec.rebate_at_deal
                calculated_rebate += rebate_value
                per_file_rebate = file_area * rec.total_rebate
                file.units_booking_id.rebate_amount = per_file_rebate
                if rec.rebate_at_sale > 0:
                    file.units_booking_id.sale_rebate = file_area * rec.rebate_at_sale
                    file.units_booking_id.is_sale_rebate_applied = True
        elif rec.rate_calculation == 'per_file':
            total_files = len(record)
            calculated_rebate = (total_files * rec.rebate_at_deal)
            for rebate in record:
                rebate.units_booking_id.rebate_amount = rec.total_rebate
                if rec.rebate_at_sale > 0:
                    rebate.units_booking_id.sale_rebate = rec.rebate_at_sale
                    rebate.units_booking_id.is_sale_rebate_applied = True
        return calculated_rebate

    def calculate_percentage_rebate(self, rec):
        record = self.unit_booking_allotment_line_ids
        calculated_rebate = 0.0
        per_file_rebate = 0.0
        # filtered out the required data from allotment lines
        if rec.sector_id:
            record = self.unit_booking_allotment_line_ids.filtered(
                lambda line: line.category_id.id == rec.category_id.id
                             and line.sector_id.id == rec.sector_id.id)
        if not rec.sector_id:
            record = self.unit_booking_allotment_line_ids.filtered(lambda line: line.category_id == rec.category_id)

        if rec.rate_calculation == 'per_marla':
            for file in record:
                file_area = file.units_booking_id.unit_category_type_id.area_marla
                file_amount = file.units_booking_id.sale_amount
                per_marla_amount = file_amount/file_area
                per_marla_rebate_value = per_marla_amount * (rec.rebate_at_deal / 100)
                rebate_value_of_file = per_marla_rebate_value * file_area
                calculated_rebate += rebate_value_of_file
                # per file rebate calculation
                per_file_rebate = file_area * (per_marla_amount * (rec.total_rebate / 100))
                file.units_booking_id.rebate_amount = per_file_rebate
                if rec.rebate_at_sale > 0:
                    file.units_booking_id.sale_rebate = (file_area * (per_marla_amount * (rec.rebate_at_sale / 100)))
                    file.units_booking_id.is_sale_rebate_applied = True

        elif rec.rate_calculation == 'per_file':
            for file in record:
                file_amount = file.units_booking_id.sale_amount
                rebate_value = file_amount * (rec.rebate_at_deal / 100)
                calculated_rebate += rebate_value
                per_file_rebate = (file_amount * (rec.total_rebate / 100))
                file.units_booking_id.rebate_amount = per_file_rebate
                if rec.rebate_at_sale > 0:
                    file.units_booking_id.sale_rebate = (file_amount * (rec.rebate_at_sale / 100))
                    file.units_booking_id.is_sale_rebate_applied = True
        return calculated_rebate

    def calculate_rebate(self):
        self.net_of_rebate = self.separate_rebate = 0
        if self.rebate_settlement == 'on_deal_start':
            for rec in self.rebate_on_allotment_ids:
                if rec.settlement_option == 'net_off':

                    if rec.calculation_basis == 'fix':
                        calculated_rebate = self.calculate_fix_rebate(rec)
                        self.net_of_rebate = self.net_of_rebate + calculated_rebate

                    elif rec.calculation_basis == 'percentage':
                        calculated_rebate = self.calculate_percentage_rebate(rec)
                        self.net_of_rebate = self.net_of_rebate + calculated_rebate

                elif rec.settlement_option == 'separate':

                    if rec.calculation_basis == 'fix':
                        calculated_rebate = self.calculate_fix_rebate(rec)
                        self.separate_rebate = self.separate_rebate + calculated_rebate

                    elif rec.calculation_basis == 'percentage':
                        calculated_rebate = self.calculate_percentage_rebate(rec)
                        self.separate_rebate = self.separate_rebate + calculated_rebate
        elif self.rebate_settlement == 'on_deal_close':
            for rec in self.rebate_on_allotment_ids:
                if rec.settlement_option == 'separate':

                    if rec.calculation_basis == 'fix':
                        calculated_rebate = self.calculate_fix_rebate(rec)
                        self.separate_rebate = self.separate_rebate + calculated_rebate

                    elif rec.calculation_basis == 'percentage':
                        calculated_rebate = self.calculate_percentage_rebate(rec)
                        self.separate_rebate = self.separate_rebate + calculated_rebate

        self.rebate_amount = self.net_of_rebate + self.separate_rebate


class BookingAllotmentPlan(models.Model):
    _name = 'booking.allotment.plan'
    _description = 'Booking Allotment Plan'

    date = fields.Date(required=True)
    amount = fields.Float()
    installment_number = fields.Integer(readonly=False)
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', 'Ref')
    state = fields.Char(string='Status', readonly=False, related='invoice_id.invoice_way_type')
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

    booking_allotment_id = fields.Many2one('unit.booking.allotment')
    installment_name = fields.Char()

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

        return super(BookingAllotmentPlan, self).unlink()


class BookingAllotmentHistory(models.Model):
    _name = 'booking.allotment.history'
    _description = 'Booking Allotment History'

    date = fields.Date()
    transaction_type = fields.Selection([
        ('investor', 'Investor Settlement'),
        ('customer', 'File Adjustment'),
        ('cancel', 'Cancel'),
        ('buy_back', 'Buy Back'),
    ])
    payment_date = fields.Date()
    old_balance = fields.Float()
    new_balance = fields.Float()
    amount = fields.Float('Old Installment')
    new_amount = fields.Float()
    payment_received = fields.Float()
    installment_number = fields.Integer()
    file_id = fields.Many2one('file')

    booking_allotment_id = fields.Many2one('unit.booking.allotment')

    # ///////////////////////////////////////////////////////////////////////////////////////////////////////////////


class UnitBookingAllotmentLine(models.Model):
    _name = 'unit.booking.allotment.line'
    _description = 'Unit Booking Allotment Line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    price = fields.Float()
    batch_id = fields.Many2one('unit.batch.generation')

    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('assignment', 'Assignment'),
        ('print', 'Print'),
        ('allotment', 'Allotment'),
        ('issued', 'Issued'),
        ('file_created', 'File Created'),
        ('balloting', 'Balloting')
    ], related='units_booking_id.state', store=True)


class UnitSwapCancelHistory(models.Model):
    _name = 'unit.swap.cancel.history'
    _description = 'Unit Swap Cancel History'

    date = fields.Date()
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Plot Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    units_booking_id = fields.Many2one('units.booking')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment')

    new_units_booking_id = fields.Many2one('units.booking')
    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation')
    ], default='swap')
    new_deal_amount = fields.Float()
    old_deal_amount = fields.Float()


class RebateOnAllotment(models.Model):
    _name = 'rebate.on.allotment'
    _description = 'Rebate On Allotment'

    # selection fields
    settlement_option = fields.Selection([('net_off', 'Net Off'), ('separate', 'Separate')], tracking=True)
    calculation_basis = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')], tracking=True)
    rate_calculation = fields.Selection([('per_marla', 'Per Marla'), ('per_file', 'Per File')], tracking=True)

    # Numerical fields
    total_rebate = fields.Float(tracking=True)
    rebate_at_deal = fields.Float(tracking=True)
    rebate_at_sale = fields.Float(tracking=True)

    # relational fields
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment')
    sector_id = fields.Many2one('sector', readonly=False)
    category_id = fields.Many2one('plot.category', string='Category')

    # @api.constrains('rebate_at_deal', 'rebate_at_sale')
    # def check_value_for_rebate(self):
    #     for rec in self:
    #         if rec.calculation_basis:
    #             if (rec.rebate_at_deal + rec.rebate_at_sale) != rec.total_rebate:
    #                 raise ValidationError(
    #                     _(f"'Rebate At Deal' and 'Rebate At Sale' should be equal to 'Total Rebate' in each line"))
