from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import qrcode
import base64
from io import BytesIO
from werkzeug.urls import url_encode


class InvestorFile(models.Model):
    _name = 'investor.file'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Investor File'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    state = fields.Selection([
        ('open', 'Open'),
        ('selected', 'Selected'),
        ('in_process', 'In Process'),
        ('issued', 'Issued'),
        ('cancel', 'Cancelled'),
    ], default='open')

    file_state = fields.Selection([
        ('available', 'Available'),
        ('cancel', 'Cancel'),
        ('inprocess', 'Inprocess'),
        ('refund', 'Refund'),
        ('merged', 'Merged'),
        ('suspend', 'Suspended')
    ], default='available')

    name = fields.Char('File Number', required=True, copy=False, index=True, readonly=True,
                       default=lambda self: _('New'))

    active = fields.Boolean(default=True)

    tracking = fields.Char()
    booking_date = fields.Date('Booking Date', default=fields.Date.today())
    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')
    ], string='Payment Type')
    investor_id = fields.Many2one('res.investor', string='Investor No')
    investment_id = fields.Many2one('investment', string='Investment No')
    investor_name = fields.Char(string='Name', store=True, related='investor_id.display_name')
    user_id = fields.Many2one('res.users', "Sale Person")
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", store=True, readonly=False)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", store=True, readonly=False)
    sector_id = fields.Many2one('sector', store=True, readonly=False, tracking=True)
    street_id = fields.Many2one('street', store=True, readonly=False, tracking=True)
    inventory_id = fields.Many2one('plot.inventory', 'Plot No', tracking=True)
    unit_number = fields.Char(related='inventory_id.name', store=True, readonly=False, tracking=True)
    coverd_area = fields.Float('Covered Area', related="inventory_id.standard_area", readonly=False,
                               tracking=True)
    category_id = fields.Many2one('plot.category', store=True, string='Category', readonly=False,
                                  tracking=True)
    size_id = fields.Many2one('unit.size', 'Size', store=True, readonly=False, tracking=True)
    unit_category_type_id = fields.Many2one('unit.category.type', store=True, readonly=False, required=True,
                                            tracking=True)
    unit_class_id = fields.Many2one('unit.class', store=True, readonly=False, tracking=True)
    price_list_id = fields.Many2one('price.list', store=True)

    # Payment Plan
    plan_type = fields.Selection([
        ('custom', 'Custom'),
        ('predefine', 'Predefine'),
    ], default='custom')
    predefine_plan_id = fields.Many2one('predefine.plan')
    plan_description = fields.Char('Plan Description', store=True, readonly=False, tracking=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', store=True, readonly=False, tracking=True)
    total_installment = fields.Integer('No of Installment', store=True, readonly=False, tracking=True)
    starting_date = fields.Date(tracking=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', readonly=False, tracking=True)

    # File Info

    sale_amount = fields.Float('Sale Amount', store=True, tracking=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', readonly=False, store=True, tracking=True)
    net_sale_amount = fields.Float('Net Sale Amount', store=True, readonly=False, tracking=True)
    balloting_amount = fields.Float(readonly=False, tracking=True)
    initial_payment = fields.Float('Initial Payment', readonly=False, tracking=True)
    balance_amount = fields.Float('Balance Amount', readonly=False, tracking=True, compute='_compute_balance_amount',
                                  store=True)

    token_generated = fields.Boolean(default=False)

    # Transferee details

    is_transferee_partner = fields.Boolean('Is Member ?')
    transfer_type = fields.Selection([
        ('sale', 'Sale'),
        ('gift', 'Gift'),
        ('inherit', 'Inherit')
    ])
    reset_installment_plan = fields.Selection([('yes', 'Yes'),
                                               ('no', 'No')
                                               ], readonly=False, tracking=True, default='no')
    transferee_partner_id = fields.Many2one('res.member', 'Name ')
    transferee_name = fields.Char('Transferee Name')
    transferee_cnic_number = fields.Char('CNIC Number', store=True, related='transferee_partner_id.cnic',
                                         readonly=False)

    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')
    relation_name = fields.Char()
    transferee_relation_name = fields.Char(store=True, related='transferee_partner_id.relation_name', readonly=False, string="Transfree Relation Name:")

    file_created = fields.Boolean(default=False)
    token_id = fields.Many2one('token.money')

    @api.depends('net_sale_amount', 'initial_payment', 'balloting_amount')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = round(rec.net_sale_amount - rec.initial_payment - rec.balloting_amount)

    @api.onchange('inventory_id')
    def _onchange_inventory(self):
        if self.inventory_id.preference_factor_ids:
            self.preference_ids = [(0, 0, {
                'factor_id': rec.id,
            }) for rec in self.inventory_id.preference_factor_ids]
        for rec in self:
            if rec.society_id and rec.phase_id and rec.inventory_id:
                rec.sector_id = rec.inventory_id.sector_id.id
                rec.street_id = rec.inventory_id.street_id.id
                rec.category_id = rec.inventory_id.category_id.id
                rec.size_id = rec.inventory_id.size_id.id
                rec.unit_category_type_id = rec.inventory_id.unit_category_type_id.id
                rec.unit_class_id = rec.inventory_id.unit_class_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'token_generated' in vals:
                vals['token_generated'] = True
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("investor.file") or _('New')

        return super(InvestorFile, self).create(vals_list)

    def create_file(self):
        if not self.transferee_partner_id:
            raise ValidationError(_('Please create member first to approve request.'))

        # if self.investment_id.options == 'full':
        #     if self.investment_id.amount_paid == 0 or self.investment_id.investor_unit_price > self.investment_id.amount_paid:
        #         raise ValidationError('You cannot issue file due to insufficient balance.')
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
            'membership_id': self.transferee_partner_id.id,
            'correspondence_address': correspondence_address,
            'membership_name': self.transferee_partner_id.name,
            'booking_date': self.booking_date,
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
            'payment_type': 'installments' if self.investment_id.options == 'down' else 'lump_sum',
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
        })

        # Agent Auto Assignment Code removed: referenced 'assignment.rule.line' and file.agent_id,
        # neither of which exist anywhere in this module set — dead/never-finished feature.
        self.investment_id.amount_paid = self.investment_id.amount_paid - self.investment_id.investor_unit_price
        file.investment_adjustment = True
        # Creating down payment on file which is already paid by investor
        file.installment_plan_ids.create({
            'date': self.booking_date,
            'payment_date': self.booking_date,
            'installment_name': 'Booking',
            'installment_type': 'down',
            'invoice': 'Paid By Investor',
            'invoice_created': True,
            'investor_payment': True,
            'installment_number': 0,
            'amount': self.initial_payment,
            'amount_paid': self.initial_payment,
            'residual': 0,
            'payment_status': 'paid',
            'file_id': file.id
        })

        if self.investment_id.options == 'down':
            investment_history = file.investment_id.investment_history_ids.create({
                'installment_number': file.investment_id.investment_history_ids[-1].installment_number + 1,
                'date': fields.Date.today(),
                'transaction_type': 'customer',
                'file_id': file.id,
                'amount': round(
                    (file.investment_id.investment_history_ids[-1].new_balance / file.investment_id.total_installment)),
                'new_amount': round(((file.investment_id.investment_history_ids[
                                          -1].new_balance - file.balance_amount) / file.investment_id.remaining_installments)),
                'old_balance': file.investment_id.investment_history_ids[-1].new_balance,
                'new_balance': file.investment_id.investment_history_ids[-1].new_balance - file.balance_amount,
                'investment_id': file.investment_id.id,
            })

            # Creating installments on files which are already paid by investor
            installment_number = 1
            for line in file.investment_id.investment_plan_ids:
                if line.invoice_created and line.installment_type == 'installment':
                    file.installment_plan_ids.create({
                        'date': line.date,
                        'payment_date': line.payment_date,
                        'installment_type': 'installment',
                        'invoice': 'Paid By Investor',
                        'invoice_created': True,
                        'investor_payment': True,
                        'installment_number': installment_number,
                        'amount': round(file.balance_amount / file.investment_id.total_installment),
                        'amount_paid': round(file.balance_amount / file.investment_id.total_installment),
                        'residual': 0,
                        'payment_status': 'paid',
                        'file_id': file.id
                    })
                    installment_number = installment_number + 1
                if not line.invoice_created and line.balance_amount > 0:
                    line.update({'file_adjusted_amount': line.file_adjusted_amount + (
                            file.balance_amount / file.total_installment),
                                 'balance_amount': line.balance_amount - (file.balance_amount / file.total_installment),
                                 'residual': line.balance_amount - (file.balance_amount / file.total_installment)})

            file._balloon_payment()
            file.create_installment_plan()

        self.state = 'issued'
        self.inventory_id.state = 'sold'
        self.file_created = True

    def create_partner(self):
        return {
            'name': _('Transferee Member'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.member',
            'view_id': self.env.ref('real_estate.view_member_form').id,
            'type': 'ir.actions.act_window',
            'context': {'default_name': self.transferee_name,
                        'default_relation_name': self.transferee_relation_name,
                        'default_cnic': self.transferee_cnic_number, 'default_project_type': self.project_type,
                        'default_company_type': 'person'},
            'target': 'new'
        }

    def unlink(self):
        for rec in self:
            if rec:
                raise UserError(_('You cannot delete a record!'))
