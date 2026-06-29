from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from lxml import etree as ET


class OpenFileIssuanceRequest(models.Model):
    _name = 'open.file.issuance.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Open File Issuance Request'

    # Selection Field

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')], related='units_booking_id.project_type')

    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')], string='Payment Type', related='units_booking_id.payment_type')

    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', readonly=False, related='units_booking_id.payment_states')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'In Process'),
        ('approve', 'Approve'),
        ('cancel', 'Cancel'),
    ], default="draft", tracking=True)

    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('change_amount', 'Change Amount')])
    processed_by = fields.Selection([('main_agent', 'Main Dealer'),
                                     ('main_other_sub_agent', 'Main Dealer And Other Sub Dealer'),
                                     ('other_agent', 'Other Dealer'),
                                     ('other_sub_agent', 'Other Dealer And Sub Dealer'),
                                     ('free_lancer', 'Free Lancer')], default='main_agent')

    # Char field
    tracking_number = fields.Char(tracking=True, related='units_booking_id.name')
    free_lance_detail = fields.Char(string='Free Lancer')
    name = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    transferee_cnic_number = fields.Char('CNIC Number', store=True, related='transferee_partner_id.cnic',
                                         readonly=False)
    transferee_relation_name = fields.Char(store=True, related='transferee_partner_id.relation_name', readonly=False,
                                           string="Transferee Relation Name:")
    plan_description = fields.Char('Plan Description', store=True, readonly=False)
    transferee_name = fields.Char('Transferee Name')

    # Date field
    booking_date = fields.Date('Booking date', tracking=True, related='units_booking_id.booking_date')
    date = fields.Date(tracking=True, default=fields.Date.today())
    starting_date = fields.Date(related='units_booking_id.starting_date', store=True, tracking=True)

    # boolean fields
    is_transferee_partner = fields.Boolean('Is Member ?')
    is_invoice_generation = fields.Boolean(default=False)

    # Property Details
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]"
                                 , related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]"
                               , related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', readonly=False
                                , related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product',
                                            related='units_booking_id.unit_category_type_id')

    # models relational fields
    units_booking_id = fields.Many2one('units.booking')
    batch_id = fields.Many2one('unit.batch.generation')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', store=True, readonly=False, tracking=True,
                                  related='units_booking_id.interval_id')
    transferee_partner_id = fields.Many2one('res.member', 'Name ')
    unit_booking_plan_ids = fields.One2many('unit.booking.plan', 'units_booking_id',
                                            readonly=False, related='units_booking_id.unit_booking_plan_ids')

    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment',
                                                related='units_booking_id.unit_booking_allotment_id')
    agent_id = fields.Many2one('res.partner', string="Dealer", related='units_booking_id.agent_id')
    other_agent_id = fields.Many2one('res.partner', string="Other Dealer")
    other_sub_agent_id = fields.Many2one('res.partner', string='Other Sub Dealer')
    other_main_sub_agent_id = fields.Many2one('res.partner', string='Other Sub Dealer')
    sub_agent_id = fields.Many2one('res.partner', string='Sub Dealer', related='units_booking_id.sub_agent_id')

    # computed field
    qr_code = fields.Binary("QR Code", attachment=True, related='units_booking_id.qr_code')

    # Numerical fields
    number = fields.Integer(string='Number', related='units_booking_id.number')
    total_installment = fields.Integer('No of Installment', store=True, readonly=False, tracking=True,
                                       related='units_booking_id.total_installment')
    sale_amount = fields.Float('Sale Amount', store=True, tracking=True,
                               related='units_booking_id.sale_amount')
    ttl_sale_amount = fields.Float('Total Sale Amount', readonly=False, store=True, tracking=True,
                                   related='units_booking_id.ttl_sale_amount')
    net_sale_amount = fields.Float('Net Sale Amount', store=True, tracking=True, readonly=False,
                                   related='units_booking_id.net_sale_amount')
    balloting_amount = fields.Float(readonly=False, related='units_booking_id.balloting_amount',
                                    store=True, tracking=True)
    initial_payment = fields.Float('Initial Payment', readonly=False, related='units_booking_id.initial_payment')
    balance_amount = fields.Float('Balance Amount', related='units_booking_id.balance_amount',
                                  store=True, tracking=True)

    # installment and payment details
    include_installment = fields.Boolean(related='units_booking_id.include_installment')
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ], default='custom', related='units_booking_id.plan_type')
    invoice_generated_for = fields.Selection([
        ('customer', 'Customer'),
        ('dealer', 'Dealer')])
    predefine_plan_id = fields.Many2one('predefine.plan', related='units_booking_id.predefine_plan_id')
    installment_created = fields.Boolean(default=False, related='units_booking_id.installment_created')

    create_manually = fields.Boolean(default=False, related='units_booking_id.create_manually')
    custom_sale_amount = fields.Float('Sale Amount ', related='units_booking_id.custom_sale_amount')
    add_custom_value = fields.Boolean(related='units_booking_id.add_custom_value')
    factor_amount = fields.Float(related='units_booking_id.factor_amount')
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='units_booking_id.discount_type')
    initial_calculation_basis = fields.Selection([('percentage', 'Percentage'),
                                                  ('fix', 'Fix')], related='units_booking_id.initial_calculation_basis')
    balloting_calculation_basis = fields.Selection([('percentage', 'Percentage'), ('fix', 'Fix')],
                                                   default='percentage', string='Final Calculation Basis',
                                                   related='units_booking_id.balloting_calculation_basis')
    discount_amount = fields.Float(store=True, readonly=False, related='units_booking_id.discount_amount',
                                   tracking=True)
    balloting_amount_percentage = fields.Float(string='Final Payment Percentage', readonly=False,
                                               related='units_booking_id.balloting_amount_percentage',store=True)
    initial_payment_percentage = fields.Float('Initial Payment Percentage', readonly=False,
                                              related='units_booking_id.initial_payment_percentage')
    balloon_payment = fields.Float(related='units_booking_id.balloon_payment', store=True, tracking=True)
    installment_amount = fields.Float(related='units_booking_id.installment_amount')
    balloon_payment_interval = fields.Integer(related='units_booking_id.balloon_payment_interval')
    balloon_payment_frequency = fields.Integer(related='units_booking_id.balloon_payment_frequency')
    processing_fee = fields.Float()
    remaining_installments = fields.Integer('Remaining Installments', compute='_compute_remaining_installments')
    reset_installment_plan = fields.Selection([('yes', 'Yes'), ('no', 'No')])
    processing_fee_invoice_id = fields.Many2one('account.move')
    invoice_paid = fields.Boolean(default=False)
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')


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
                    'model': 'open.file.issuance.request',
                    # 'menu_id': self.env.ref('module_name.menu_record_id').id,
                    'action': self.env.ref('unit_booking.action_open_file_issuance_request').id,
                }'''
                params = '/booking/verification/%s/%s/%s/%s' % (
                    rec.id, rec.name)
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

    def view_installment_plan(self):
        context = {
                'default_plan_type': self.units_booking_id.plan_type,
                'default_payment_type': self.units_booking_id.payment_type,
                'default_units_booking_id': self.units_booking_id.id,
                'default_predefine_plan_id': self.units_booking_id.predefine_plan_id.id,
                'default_interval_id': self.units_booking_id.interval_id.id,
                'default_starting_date': self.units_booking_id.starting_date,
                'default_total_installment': self.units_booking_id.total_installment,
                'default_sale_amount': self.units_booking_id.sale_amount,
                'default_ttl_sale_amount': self.units_booking_id.ttl_sale_amount,
                'default_net_sale_amount': self.units_booking_id.net_sale_amount,
                'default_balloting_amount': self.units_booking_id.balloting_amount,
                'default_initial_payment': self.units_booking_id.initial_payment,
                'default_balance_amount': self.units_booking_id.balance_amount,
                'default_balloon_payment': self.units_booking_id.balloon_payment,
                'default_balloon_payment_interval': self.units_booking_id.balloon_payment_interval,
                'default_balloon_payment_frequency': self.units_booking_id.balloon_payment_frequency,
                'default_balloon_payment_start': self.units_booking_id.balloon_payment_start,
                'default_primary_amount': self.units_booking_id.primary_amount,
                'default_primary_amount_interval': self.units_booking_id.primary_amount_interval,
                'default_primary_amount_frequency': self.units_booking_id.primary_amount_frequency,
                'default_possession_amount': self.units_booking_id.possession_amount,
                'default_possession_amount_interval': self.units_booking_id.possession_amount_interval,
                'default_possession_amount_frequency': self.units_booking_id.possession_amount_frequency,
                'default_confirmation_amount': self.units_booking_id.confirmation_amount,
                'default_confirmation_amount_interval': self.units_booking_id.confirmation_amount_interval,
                'default_confirmation_amount_frequency': self.units_booking_id.confirmation_amount_frequency,
                'default_discount_amount': self.units_booking_id.discount_amount
                }
        return {
            'name': _('Plan Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'reset.installment.plan',
            'view_id': self.env.ref('unit_booking.reset_installment_plan_form1').id,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new',
        }

    @api.depends('units_booking_id')
    def _compute_remaining_installments(self):
        for rec in self:
            rec.remaining_installments = len(rec.units_booking_id.unit_booking_plan_ids.search(
                [('units_booking_id', '=', rec.units_booking_id.id),
                 ('installment_type', 'in', ['installment', 'balloon', 'possession_amount',
                                             'balloting_amount', 'confirmation_amount']),
                 ('invoice_created', '=', False), ('invoice_id', '=', False)]))

    @api.onchange('processed_by')
    def onchange_processed_by(self):
        for rec in self:
            if rec.processed_by == 'main_agent':
                rec.other_agent_id = False
                rec.other_sub_agent_id = False
                rec.other_main_sub_agent_id = False
                rec.free_lance_detail = ''
            elif rec.processed_by == 'main_other_sub_agent':
                rec.other_agent_id = False
                rec.other_sub_agent_id = False
                rec.free_lance_detail = ''
            elif rec.processed_by == 'other_agent':
                rec.other_sub_agent_id = False
                rec.free_lance_detail = ''
                rec.other_main_sub_agent_id = False
            elif rec.processed_by == 'other_sub_agent':
                rec.other_agent_id = False
                rec.other_sub_agent_id = False
                rec.free_lance_detail = ''
                rec.other_main_sub_agent_id = False
            elif rec.processed_by == 'free_lancer':
                rec.other_agent_id = False
                rec.other_sub_agent_id = False
                rec.other_main_sub_agent_id = False

    @api.onchange('transferee_cnic_number')
    def onchange_transferee_cnic(self):
        if self.transferee_cnic_number and not self.transferee_partner_id and self.is_transferee_partner:
            try:
                partner_obj = self.env['res.partner'].search([('cnic', '=', self.transferee_cnic_number)], limit=1)
            except Exception as e:
                raise ValidationError(_('Some Basic Data for member is not available.See Error :%s' % (e)))
            else:
                if partner_obj:
                    self.transferee_partner_id = partner_obj.id
                else:
                    raise ValidationError(_('No Record Found.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('issuance.request.number') or _('New')
        result = super().create(vals_list)
        return result

    def processing_fee_invoice(self):
        # processing fee invoice
        for rec in self:
            processing_fee_invoice = self.env['account.move'].create({
                'partner_id': rec.transferee_partner_id.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'out_invoice',
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_date': fields.Date.today(),
                'open_file_issuance_id': rec.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('real_estate.file_transfer').id,
                    'name': self.env.ref('real_estate.file_transfer').name,
                    'account_id': self.env.ref(
                        'real_estate.file_transfer').product_id.property_account_income_id.id,
                    'price_unit': rec.processing_fee
                })]
            })

            processing_fee_invoice.action_post()
            rec.processing_fee_invoice_id = processing_fee_invoice.id
            rec.is_invoice_generation = True

            if self.units_booking_id.sale_rebate and self.units_booking_id.is_sale_rebate_applied:
                rebate_invoice = self.env['account.move'].create({
                    'partner_id': self.units_booking_id.sub_agent_id.id if
                    self.units_booking_id.unit_booking_allotment_id.issue_to_subagent
                    else self.units_booking_id.agent_id,
                    # 'branch_id': self.env.branch.id,
                    'move_type': 'in_invoice',
                    'open_file_issuance_id': self.id,
                    'invoice_date': self.booking_date,
                    # 'journal_id': self.env.company.account_journal_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                        'name': self.env.ref('unit_booking.dealer_rebate').name,
                        'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                        'price_unit': self.units_booking_id.sale_rebate,
                    })],
                    'property_invoice_type': 'dealer_rebate',
                })
                rebate_invoice.action_post()

    def invoice_generation(self):
        for rec in self:
            if not rec.unit_booking_allotment_id.generate_invoices_for_installment:
                invoices = rec.units_booking_id.unit_booking_plan_ids.\
                    filtered(lambda l: l.date <= fields.Date.today() and not l.invoice_created)
                for inv in invoices:
                    prod = []
                    if inv.installment_type == 'final':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.final_product').id,
                            'name': self.env.ref('real_estate.final_product').name,
                            'account_id': self.env.ref(
                                'real_estate.final_product').product_id.property_account_income_id.id,
                            'price_unit': inv.amount,
                        })]
                    elif inv.installment_type == 'installment':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.installment_product').id,
                            'name': self.env.ref('real_estate.installment_product').name,
                            'account_id': self.env.ref(
                                'real_estate.installment_product').product_id.property_account_income_id.id,
                            'price_unit': inv.amount,
                        })]
                    elif inv.installment_type == 'balloon':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.balloon_payment').id,
                            'name': self.env.ref('real_estate.balloon_payment').name,
                            'account_id': self.env.ref(
                                'real_estate.balloon_payment').product_id.property_account_income_id.id,
                            'price_unit': inv.amount
                        })]

                    elif inv.installment_type == 'possession_amount':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.possession_amount_product').id,
                            'name': self.env.ref('real_estate.possession_amount_product').name,
                            'account_id': self.env.ref(
                                'real_estate.possession_amount_product').product_id.property_account_income_id.id,
                            'price_unit': inv.amount
                        })]

                    elif inv.installment_type == 'confirmation_amount':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                            'name': self.env.ref('real_estate.confirmation_amount_product').name,
                            'account_id': self.env.ref(
                                'real_estate.confirmation_amount_product').product_id.property_account_income_id.id,
                            'price_unit': inv.amount
                        })]

                    elif inv.installment_type == 'balloting_amount':
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.balloting_product').id,
                            'name': self.env.ref('real_estate.balloting_product').name,
                            'account_id': self.env.ref(
                                'real_estate.balloting_product').product_id.property_account_income_id.id,
                            'price_unit': inv.amount
                        })]

                    invoice = self.env['account.move'].create({
                        'units_booking_id': rec.units_booking_id.id,
                        'partner_id': rec.transferee_partner_id.id if rec.invoice_generated_for == 'customer'
                        else rec.unit_booking_allotment_id.partner_id.id,
                        # 'branch_id': self.env.branch.id,
                        'move_type': 'out_invoice',
                        'journal_id': self.env.company.account_journal_id.id,
                        'property_invoice_type': 'installment',
                        'date': inv.date,
                        'invoice_date': inv.date,
                    })
                    invoice.invoice_line_ids = prod

                    invoice.action_post()

                    inv.invoice_id = invoice.id
                    print("INVOICE ID:>>>>>>>", invoice.id)

                    inv.invoice_created = True
                    inv.invoice = invoice.name if rec.invoice_generated_for == 'customer' else 'Paid By Dealer'

    def approve_request(self):
        if not self.processing_fee_invoice_id:
            raise ValidationError(_('Please generate processing fee invoice first'))
        if not self.invoice_paid:
            raise ValidationError(_("Pay processing fee invoice first"))
        self.invoice_generation()
        if self.transaction_type == 'open_file':
            if not self.transferee_partner_id:
                raise ValidationError('Please create or select existing member to approve.')
            else:
                self.transferee_partner_id.project_type = self.project_type

            # if self.investment_id.options == 'full':
            #     if self.investment_id.amount_paid == 0 or self.investment_id.investor_unit_price > self.investment_id.amount_paid:
            #         raise ValidationError('You cannot issue file due to insufficient balance.')

            # for rec in self.unit_swapping_request_lines:
            file = self.env['file'].create({
                'project_type': self.project_type,
                # 'from_open_file': True,
                'add_custom_value': True,
                'tracking_id': self.units_booking_id.name,
                'membership_id': self.transferee_partner_id.id,
                'membership_name': self.transferee_partner_id.name,
                'booking_date': self.batch_id.open_date,
                'booking_agent_id': self.units_booking_id.agent_id.id,
                'booking_sub_agent_id': self.units_booking_id.sub_agent_id.id,
                'other_agent_id': self.other_agent_id.id,
                'other_sub_agent_id': self.other_sub_agent_id.id,
                'other_main_sub_agent_id': self.other_main_sub_agent_id.id,
                'free_lance_detail': self.free_lance_detail,
                'processed_by': self.processed_by,
                'unit_batch_id': self.batch_id.id,
                'unit_booking_id': self.units_booking_id.id,
                'file_type': 'new',
                'type': 'booking_file',
                'state': 'available',
                'society_id': self.units_booking_id.society_id.id,
                'phase_id': self.units_booking_id.phase_id.id,
                'category_id': self.units_booking_id.category_id.id,
                'unit_category_type_id': self.units_booking_id.unit_category_type_id.id,
                'plan_type': self.unit_booking_allotment_id.unit_batch_id.plan_type,
                'predefine_plan_id': self.unit_booking_allotment_id.predefine_plan_id.id,
                'payment_type': 'installments' if self.unit_booking_allotment_id.options == 'down' else 'lump_sum',
                'interval_id': self.unit_booking_allotment_id.interval_id.id,
                'starting_date': self.units_booking_id.starting_date,
                'total_installment': self.units_booking_id.total_installment,
                'payment_states': 'open' if self.unit_booking_allotment_id.options == 'down' else 'close',
                'overall_status': 'open' if self.unit_booking_allotment_id.options == 'down' else 'close',
                'sale_amount': self.units_booking_id.sale_amount,
                'custom_sale_amount': self.units_booking_id.sale_amount,
                'ttl_sale_amount': self.units_booking_id.ttl_sale_amount,
                'net_sale_amount': self.units_booking_id.net_sale_amount,
                'balloon_payment': self.units_booking_id.balloon_payment,
                'initial_payment': self.units_booking_id.initial_payment,
                'balloting_amount': self.units_booking_id.balloting_amount,
                'balance_amount': self.units_booking_id.balance_amount,
                'possession_amount': self.units_booking_id.possession_amount,
                'possession_amount_interval': self.units_booking_id.possession_amount_interval,
                'possession_amount_frequency': self.units_booking_id.possession_amount_frequency,
                'confirmation_amount': self.units_booking_id.confirmation_amount,
                'confirmation_amount_interval': self.units_booking_id.confirmation_amount_interval,
                'confirmation_amount_frequency': self.units_booking_id.confirmation_amount_frequency,
                'primary_amount': self.units_booking_id.primary_amount,
                'primary_amount_interval': self.units_booking_id.primary_amount_interval,
                'primary_amount_frequency': self.units_booking_id.primary_amount_frequency,
                'balloon_payment_interval': self.units_booking_id.balloon_payment_interval,
                'balloon_payment_frequency': self.units_booking_id.balloon_payment_frequency,
                'balloon_payment_start': self.units_booking_id.balloon_payment_start,
                'include_installment': self.units_booking_id.include_installment,
                'discount_amount': self.units_booking_id.discount_amount,
                'discount_type': 'fix' if self.units_booking_id.discount_amount else 'percentage',
            })

            # self.investment_id.amount_paid = self.investment_id.amount_paid - self.investment_id.investor_unit_price
            # file.investment_adjustment = True

            self.units_booking_id.state = 'file_created'
            self.units_booking_id.is_transferee_partner = True
            self.units_booking_id.transferee_name = self.transferee_name
            self.units_booking_id.transferee_partner_id = self.transferee_partner_id.id
            self.units_booking_id.transferee_relation_name = self.transferee_relation_name
            self.units_booking_id.transferee_cnic_number = self.transferee_cnic_number

            if self.unit_booking_allotment_id.options == 'down':
                allotment_history = self.unit_booking_allotment_id.booking_allotment_history_ids.create({
                    'installment_number': self.unit_booking_allotment_id.booking_allotment_history_ids[
                                              -1].installment_number + 1,
                    'date': fields.Date.today(),
                    'transaction_type': 'customer',
                    'file_id': file.id,
                    'amount': round((self.unit_booking_allotment_id.booking_allotment_history_ids[
                                         -1].new_balance / self.unit_booking_allotment_id.total_installment)),
                    'new_amount': round(((self.unit_booking_allotment_id.booking_allotment_history_ids[
                                              -1].new_balance - file.balance_amount) / self.unit_booking_allotment_id.remaining_installments)),
                    'old_balance': self.unit_booking_allotment_id.booking_allotment_history_ids[-1].new_balance,
                    'new_balance': self.unit_booking_allotment_id.booking_allotment_history_ids[
                                       -1].new_balance - file.balance_amount,
                    'booking_allotment_id': self.unit_booking_allotment_id.id,
                })

                # Creating installments on files which are already paid by investor
                if self.unit_booking_allotment_id.generate_invoices_for_installment:

                    # Creating down payment on file which is already paid by investor

                    # file.installment_plan_ids.create({
                    #     'date': self.batch_id.open_date,
                    #     'payment_date': self.batch_id.open_date,
                    #     'installment_type': 'down',
                    #     'invoice': 'Paid By Dealer',
                    #     'invoice_created': True,
                    #     'installment_number': 0,
                    #     'amount': self.units_booking_id.initial_payment,
                    #     'amount_paid': self.units_booking_id.initial_payment,
                    #     'residual': 0,
                    #     'payment_status': 'paid',
                    #     'file_id': file.id
                    # })

                    open_file_plan = self.units_booking_id.unit_booking_plan_ids
                    for line in self.unit_booking_allotment_id.booking_plan_ids:

                        if line.invoice_created and line.installment_type in ['installment', 'balloon',
                                                                              'possession_amount',
                                                                              'balloting_amount',
                                                                              'confirmation_amount']:
                            # making the current open file installment marked true which are paid by dealer
                            # or invoice are already created in dealer plan

                            current_invoice = open_file_plan.filtered(
                                lambda l: l.installment_number == line.installment_number
                                          and l.installment_type == line.installment_type)

                            current_invoice.invoice_created = line.invoice_created

                            current_invoice.invoice = line.invoice

                            current_invoice.amount = round(
                                line.balance_amount / self.unit_booking_allotment_id.no_of_units)

                            current_invoice.amount_paid = round(
                                    line.balance_amount / self.unit_booking_allotment_id.no_of_units)

                            current_invoice.residual = 0 if line.payment_status == 'paid' else round(
                                line.balance_amount / self.unit_booking_allotment_id.no_of_units)

                            current_invoice.payment_status = line.payment_status

                            current_invoice.payment_date = line.payment_date

                            current_invoice.invoice_id = line.invoice_id.id

                            current_invoice.date = line.date
                            # creating the installment plan line which are already  in real estate file

                            # file.installment_plan_ids.create({
                            #     'date': line.date,
                            #     'payment_date': line.payment_date,
                            #     'installment_type': line.installment_type,
                            #     'invoice': 'Paid By Dealer',
                            #     'invoice_created': True,
                            #     'installment_number': installment_number,
                            #     'amount': round(line.balance_amount / self.unit_booking_allotment_id.no_of_units),
                            #     'amount_paid': round(
                            #         line.balance_amount / self.unit_booking_allotment_id.no_of_units),
                            #     'residual': 0,
                            #     'payment_status': 'paid',
                            #     'file_id': file.id
                            # })
                            # installment_number = installment_number + 1
                        if not line.invoice_created and line.balance_amount > 0:
                            line.update({'file_adjusted_amount': line.file_adjusted_amount + (
                                    line.balance_amount / self.unit_booking_allotment_id.no_of_units),
                                         'balance_amount': line.balance_amount - (
                                                 line.balance_amount / self.unit_booking_allotment_id.no_of_units),
                                         'residual': line.balance_amount - (
                                                 line.balance_amount / self.unit_booking_allotment_id.no_of_units)})

                    # writing open file installment plan into real estate file plan
                    for invoice in self.units_booking_id.unit_booking_plan_ids:
                        file.installment_plan_ids = [
                            (0, 0, {
                                'date': invoice.date,
                                'installment_type': invoice.installment_type,
                                'installment_name': invoice.installment_name,
                                'invoice': invoice.invoice,
                                'invoice_created': invoice.invoice_created,
                                'installment_number': invoice.installment_number,
                                'amount': invoice.amount,
                                'amount_paid': invoice.amount_paid,
                                'residual': 0 if invoice.payment_status == 'paid' else invoice.residual,
                                'payment_status': invoice.payment_status,
                                'file_id': file.id,
                                'invoice_id': invoice.invoice_id.id})]

                # invoice which are generated before
                # the time of issuance of open file either in the name of partner or dealer
                if not self.unit_booking_allotment_id.generate_invoices_for_installment:
                    invoices = self.units_booking_id.unit_booking_plan_ids
                    if invoices:
                        for line in invoices:
                            file.installment_plan_ids = [
                                (0, 0, {
                                    'date': line.date,
                                    'installment_type': line.installment_type,
                                    'invoice': line.invoice,
                                    'invoice_created': line.invoice_created,
                                    'installment_number': line.installment_number,
                                    'installment_name': line.installment_name,
                                    'amount': line.amount,
                                    'amount_paid': line.amount_paid,
                                    'residual': 0 if line.payment_status == 'paid' else line.residual,
                                    'payment_status': line.payment_status,
                                    'file_id': file.id,
                                    'invoice_id': line.invoice_id.id})]
                            if line.invoice_id:
                                line.invoice_id.file_ids = file.id
                        plans = self.unit_booking_allotment_id.booking_plan_ids.filtered(lambda l: l.installment_type in
                                                        ['installment', 'balloon',
                                                         'possession_amount',
                                                         'balloting_amount',
                                                         'confirmation_amount'])
                    for plan in plans:
                        plan.update({'file_adjusted_amount': plan.file_adjusted_amount + (
                                plan.balance_amount / self.unit_booking_allotment_id.no_of_units),
                                     'balance_amount': plan.balance_amount - (
                                             plan.balance_amount / self.unit_booking_allotment_id.no_of_units),
                                     'residual': plan.balance_amount - (
                                             plan.balance_amount / self.unit_booking_allotment_id.no_of_units)})
                # maintaining the history on file
                file.history_log(self.name, 'Issuance', fields.Date.today(), self.transferee_partner_id.id, False)
                self.units_booking_id.write({
                    'history_ids': [(0, 0, {
                        'state': 'file_created',
                        'print_state': '',
                        'date': fields.Date.today(),
                    })]
                })
            self.state = 'approve'
            tree_view = (self.env.ref('real_estate.file_tree').id, 'list')
            form_view = (self.env.ref('real_estate.file_form').id, 'form')
            context = {'default_membership_id': self.transferee_partner_id.id, 'current_view': 'realestate',
                       'default_project_type': 'housing_society'}
            return {
                'type': 'ir.actions.act_window',
                'views': [tree_view, form_view],
                'view_mode': 'list,form',
                'name': _('File'),
                'res_model': 'file',
                'domain': [('membership_id', '=', self.transferee_partner_id.id)],
                'context': context,
            }

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'
            rec.units_booking_id.file_issuance_request_created = False

    def create_partner(self):
        return {
            'name': _('Member'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'view_id': self.env.ref('real_estate.view_partner_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                        'default_cnic': self.transferee_cnic_number,
                        'current_view': 'realestate',
                        'default_project_type': self.project_type,
                        'default_company_type': 'person',
                        'default_company_id': self.env.company.id
                        },
            'target': 'new'
        }

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(OpenFileIssuanceRequest, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                                   toolbar=toolbar,
                                                                   submenu=submenu)
        if view_type == 'form':
            doc = ET.XML(res['arch'])
            doc.set('edit', 'true')
            doc.set('create', 'false')
            res['arch'] = ET.tostring(doc)

        if view_type == 'tree':
            doc = ET.XML(res['arch'])
            doc.set('edit', 'false')
            doc.set('create', 'false')
            res['arch'] = ET.tostring(doc)

        return res

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'domain': [('open_file_issuance_id', '=', self.id)],
        }

    def _compute_no_of_invoices(self):
        for rec in self:
            rec.no_of_invoices = len(rec.env['account.move'].search([('open_file_issuance_id', '=', rec.id)]))