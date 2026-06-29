from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from lxml import etree as ET


class OpenFileDuplicate(models.Model):
    _name = 'open.file.duplicate'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Open File Duplicate'

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
        ('approve', 'Approve'),
        ('cancel', 'Cancel'),
    ], default="draft", tracking=True)

    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('change_amount', 'Change Amount'),
        ('duplicate_file', 'Duplicate File')])

    # Char field
    tracking_number = fields.Char(tracking=True, related='units_booking_id.name')
    name = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    transferee_cnic_number = fields.Char('CNIC Number', store=True, related='transferee_partner_id.cnic',
                                         readonly=False)
    transferee_relation_name = fields.Char(store=True, related='transferee_partner_id.relation_name', readonly=False,
                                           string="Transferee Relation Name:")

    # Date field
    booking_date = fields.Date('Booking date', tracking=True, related='units_booking_id.booking_date')
    date = fields.Date(tracking=True, default=fields.Date.today())
    starting_date = fields.Date(related='units_booking_id.starting_date', store=True, tracking=True)

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
    units_booking_id = fields.Many2one('units.booking', store=True)
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id', store=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', store=True, readonly=False, tracking=True,
                                  related='units_booking_id.interval_id')
    transferee_partner_id = fields.Many2one('res.member', 'Name ',
                                            related='units_booking_id.transferee_partner_id', store=True)
    unit_booking_plan_ids = fields.One2many('unit.booking.plan', 'units_booking_id',
                                            readonly=False, related='units_booking_id.unit_booking_plan_ids')

    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment',
                                                related='units_booking_id.unit_booking_allotment_id')
    agent_id = fields.Many2one('res.partner', string="Dealer", related='units_booking_id.agent_id')
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
    duplicate_file = fields.Boolean(default=False)
    required_documents_line_ids = fields.One2many('required.documents.detail', 'units_booking_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('open.file.duplicate') or _('New')
        result = super().create(vals_list)
        return result

    def approve_request(self):
        for rec in self:
            if not rec.required_documents_line_ids:
                raise ValidationError(_('Add details in Required Document Tab'))
            if rec.units_booking_id:
                rec.state = 'approve'
                rec.duplicate_file = True

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(OpenFileDuplicate, self).fields_view_get(view_id=view_id, view_type=view_type,
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