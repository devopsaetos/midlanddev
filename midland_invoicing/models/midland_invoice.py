# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MidlandInvoice(models.Model):
    _name = 'midland.invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Midland Customer Invoice'
    _rec_name = 'name'
    _order = 'invoice_date desc, id desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Invoice Number', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
    ], default='out_invoice', required=True, tracking=True)

    # ── Customer ──────────────────────────────────────────────────────────────
    member_id = fields.Many2one('res.member', string='Customer', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Accounting Partner',
        compute='_compute_partner_id', store=True, readonly=False,
    )
    delivery_address_id = fields.Many2one('res.partner', string='Delivery Address')

    # ── Header info ───────────────────────────────────────────────────────────
    ref = fields.Char(string='Reference', tracking=True)
    is_maintenance_batch = fields.Boolean(string='Is Maintenance Batch', tracking=True)
    payment_no = fields.Char(string='Payment No.', tracking=True)
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('adv_and_securities', 'Advances and Securities'),
        ('installment', 'Installment'),
        ('initial_payment_plus_installment', 'Initial Payment + Installment'),
        ('transfer_application', 'Transfer Application'),
        ('rent', 'Rent'),
        ('token', 'Token'),
        ('investment', 'Investment'),
        ('investment_installment', 'Investment Installment'),
        ('maintenance', 'Maintenance Charges'),
        ('map_fee', 'Mapping Fee'),
        ('tax', 'PRA-Tax'),
        ('236k_sale', '236k-Sale'),
        ('demarcation', 'Demarcation'),
        ('merger_adjustment', 'Merger Adjustment'),
        ('down', 'Booking'),
        ('confirmation_amount', 'Confirmation'),
        ('balloon', 'Balloon'),
        ('balloting_amount', 'Balloting'),
        ('possession_amount', 'Possession'),
        ('final', 'Final Payment'),
        ('merger_fee', 'Merger Fee'),
        ('booking_allotment', 'Booking Allotment'),
        ('allotment_installment', 'Allotment Installment'),
        ('registration', 'Registration'),
        ('security', 'Security'),
        ('dealer_rebate', 'Rebate'),
        ('renewal', 'Renewal'),
        ('buy_back', 'Buy Back'),
        ('dealer_cancellation', 'Dealer Cancellation'),
        ('others', 'Others'),
    ], string='Invoice Type', tracking=True)

    # ── Dates / Company ───────────────────────────────────────────────────────
    invoice_date = fields.Date(string='Invoice Date', default=fields.Date.today, tracking=True)
    branch_id = fields.Many2one('res.company', string='Branch', tracking=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── Source record links ───────────────────────────────────────────────────
    investor_file_id = fields.Many2one('investor.file', string='Investor File')
    investment_id = fields.Many2one('investment', string='Investment')
    investment_installment_id = fields.Many2one('investment.plan', string='Investment Installment')
    file_ids = fields.Many2one('file', string='File')
    installment_id = fields.Many2one('installment.plan', string='Installment No.')
    units_booking_id = fields.Many2one('units.booking', string='Units Booking')
    crm_id = fields.Many2one('crm.lead', string='CRM Lead')
    token_id = fields.Many2one('token.money', string='Token')
    unit_swap_request_id = fields.Many2one('unit.swapping.request', string='Swap Request')
    transfer_application_id = fields.Many2one('transfer.application', string='Transfer Application')
    merger_application_id = fields.Many2one('plot.merger.application', string='Merger Application')
    open_file_issuance_id = fields.Many2one('open.file.issuance.request', string='Issuance Request')
    booking_allotment_id = fields.Many2one('unit.booking.allotment', string='Booking Allotment')
    dealer_renewal_id = fields.Many2one('dealer.renewal.req', string='Dealer Renewal')
    dealer_cancellation_id = fields.Many2one('dealer.cancellation.req', string='Dealer Cancellation')
    buy_back_id = fields.Many2one('buy.back', string='Buy Back')

    # ── Lines ─────────────────────────────────────────────────────────────────
    invoice_line_ids = fields.One2many(
        'midland.invoice.line', 'invoice_id', string='Invoice Lines',
    )

    # ── Amounts (computed) ────────────────────────────────────────────────────
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount', compute='_compute_amounts', store=True,
        currency_field='currency_id',
    )
    amount_tax = fields.Monetary(
        string='Tax', compute='_compute_amounts', store=True,
        currency_field='currency_id',
    )
    amount_total = fields.Monetary(
        string='Total', compute='_compute_amounts', store=True,
        currency_field='currency_id', tracking=True,
    )
    amount_residual = fields.Monetary(
        string='Amount Due', compute='_compute_amount_residual', store=True,
        currency_field='currency_id',
    )

    # ── Payment status ────────────────────────────────────────────────────────
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], default='not_paid', string='Payment Status', tracking=True, copy=False)
    amount_paid = fields.Monetary(
        string='Amount Paid', currency_field='currency_id', default=0.0,
    )

    # ── JV link (secondary — created on post) ─────────────────────────────────
    jv_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False)

    # ── Tracks which mode was active when this invoice was posted ─────────────
    entry_mode = fields.Boolean(
        string='Entry Created', readonly=True, copy=False,
        help='True = posted with Create Entry for Invoices ON (Dr Receivable/Cr Revenue JV created).\n'
             'False = posted with Create Entry for Invoices OFF (no JV at invoice time).',
    )

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends('member_id')
    def _compute_partner_id(self):
        for rec in self:
            if rec.member_id and rec.member_id.partner_id:
                rec.partner_id = rec.member_id.partner_id
            elif not rec.member_id:
                rec.partner_id = False

    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.tax_ids',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity')
    def _compute_amounts(self):
        for rec in self:
            untaxed = sum(rec.invoice_line_ids.mapped('price_subtotal'))
            tax = 0.0
            for line in rec.invoice_line_ids:
                if line.tax_ids:
                    tax_res = line.tax_ids.compute_all(
                        line.price_unit, rec.currency_id,
                        line.quantity, product=line.product_id.product_id,
                        partner=rec.partner_id,
                    )
                    tax += tax_res['total_included'] - tax_res['total_excluded']
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

    @api.depends('amount_total', 'amount_paid')
    def _compute_amount_residual(self):
        for rec in self:
            rec.amount_residual = rec.amount_total - rec.amount_paid

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('midland.invoice') or _('New')
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_post(self):
        create_entry = self.env['ir.config_parameter'].sudo().get_param(
            'midland.create_invoice_entry', default='False'
        ) in ('True', '1', 'true')
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft invoices can be posted.'))
            if not rec.invoice_line_ids:
                raise ValidationError(_('Add at least one invoice line before posting.'))

            partner = rec.partner_id or (rec.member_id.partner_id if rec.member_id else False)
            if not partner:
                raise ValidationError(_('Please set a customer before posting.'))

            if create_entry:
                # ── Mode: true — create Dr Receivable / Cr Revenue JV ─────────
                jv_line_vals = []
                for line in rec.invoice_line_ids:
                    shadow = line.product_id.product_id
                    lv = {
                        'product_id': shadow.id if shadow else False,
                        'name': line.name or (line.product_id.name if line.product_id else '/'),
                        'quantity': line.quantity,
                        'price_unit': line.price_unit,
                        'tax_ids': [(6, 0, line.tax_ids.ids)],
                    }
                    if line.account_id:
                        lv['account_id'] = line.account_id.id
                    jv_line_vals.append((0, 0, lv))

                jv = self.env['account.move'].create({
                    'move_type': rec.move_type,
                    'partner_id': partner.id,
                    'invoice_date': rec.invoice_date,
                    'currency_id': rec.currency_id.id,
                    'company_id': rec.company_id.id,
                    'ref': rec.name,
                    'invoice_payment_term_id': rec.payment_term_id.id,
                    'invoice_line_ids': jv_line_vals,
                })
                jv.action_post()
                rec.write({'state': 'posted', 'jv_id': jv.id, 'entry_mode': True})
                # Link installment plan to JV so payment_status, amount_paid, residual sync
                if rec.installment_id:
                    rec.installment_id.write({'invoice_id': jv.id, 'invoice_created': True})
            else:
                # ── Mode: false — no JV at invoice time, just mark posted ─────
                rec.write({'state': 'posted', 'entry_mode': False})
                if rec.installment_id:
                    rec.installment_id.write({'invoice_created': True})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'posted' and rec.jv_id:
                if rec.jv_id.state == 'posted':
                    rec.jv_id.button_cancel()
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('posted', 'cancelled'):
                continue
            if rec.jv_id and rec.jv_id.state == 'posted':
                raise ValidationError(
                    _('Cannot reset to draft: the journal entry %s is already posted. '
                      'Reverse it first.') % rec.jv_id.name
                )
            rec.write({'state': 'draft', 'jv_id': False})

    def action_view_jv(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.jv_id.id,
        }

    def action_register_payment(self):
        self.ensure_one()
        payment = self.env['midland.payment'].create({
            'member_id': self.member_id.id,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'file_id': self.file_ids.id if self.file_ids else False,
            'investment_id': self.investment_id.id if self.investment_id else False,
            'payment_amount': self.amount_residual,
            'currency_id': self.currency_id.id,
            'remarks': self.name,
            'invoice_line_ids': [(0, 0, {
                'invoice_id': self.id,
                'payment_amount': self.amount_residual,
            })],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'midland.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }


class MidlandInvoiceLine(models.Model):
    _name = 'midland.invoice.line'
    _description = 'Midland Invoice Line'

    invoice_id = fields.Many2one(
        'midland.invoice', string='Invoice',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)

    product_id = fields.Many2one('product.realestate', string='Product')
    name = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    account_id = fields.Many2one('account.account', string='Account')
    tax_ids = fields.Many2many('account.tax', string='Taxes')

    currency_id = fields.Many2one(
        related='invoice_id.currency_id', store=True, readonly=True,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_price_subtotal', store=True,
        currency_field='currency_id',
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.name = line.product_id.name
                line.account_id = line.product_id.property_account_income_id
