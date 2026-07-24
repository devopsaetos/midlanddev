# -*- coding: utf-8 -*-
import psycopg2

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .res_member import _format_cnic


class ResInvestor(models.Model):
    _name = 'res.investor'
    _description = "Investor"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'investor_id'

    investor_id = fields.Char(string="Investor Name", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)

    # Hidden partner bridge for accounting (invoices/payments need res.partner)
    partner_id = fields.Many2one(
        'res.partner',
        string="Related Partner",
        ondelete='restrict',
        copy=False,
    )

    # Investor classification
    investment_category = fields.Many2one('investment.category', string="Investment Category", tracking=True)
    investor_type = fields.Selection([
        ('dealer', 'Dealer'),
        ('marketing_company', 'Marketing Company'),
        ('sub_dealer', 'Sub Dealer'),
    ], default="dealer", string="Dealer Type", required=True, tracking=True)
    marketing_company_id = fields.Many2one(
        'res.partner',
        tracking=True,
    )
    main_investor_id = fields.Many2one(
        'res.investor',
        domain=[('investor_type', '=', 'dealer')],
        tracking=True,
    )

    # Fees & registration
    fee_type = fields.Selection([
        ('registration', 'Registration'),
        ('security', 'Security'),
    ], default="registration", string="Registration Fee", tracking=True)
    fees_line_ids = fields.One2many('registration.security.line', 'investor_id', tracking=True)
    owner_name = fields.Char(string="Owner Name")
    show_sale_summary = fields.Selection([
        ('self', 'Self'),
        ('all', 'All'),
        ('none', 'None'),
    ], default="none", string="Show Sale Summary", tracking=True, copy=False)

    # Workflow state
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'In Process'),
        ('invoice', 'Invoice'),
        ('approve', 'Approve'),
    ], default='draft', tracking=True)
    is_invoice_generation = fields.Boolean(default=False)

    # Contact info
    email = fields.Char(string="Email", tracking=True)
    linkedin = fields.Char(string="LinkedIn", tracking=True)
    ntn = fields.Char(string="NTN Number", tracking=True)
    mobile = fields.Char(string="Mobile", tracking=True)
    phone = fields.Char(string="Phone", tracking=True)
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
    ], default='person', string="Company Type")

    # Primary address
    street = fields.Char(tracking=True)
    street2 = fields.Char()
    city_id = fields.Many2one('city', string='City')
    state_id = fields.Many2one('res.country.state', string='State', ondelete='restrict',
                                domain="[('country_id', '=?', country_id)]", tracking=True)
    zip = fields.Char(tracking=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', tracking=True)

    # Correspondence address
    is_same = fields.Boolean('Same Address')
    corespondence_street = fields.Char()
    corespondence_street2 = fields.Char()
    corespondence_city_id = fields.Many2one('city')
    corespondence_zip = fields.Char(store=True, related='corespondence_city_id.zip')
    corespondence_state_id = fields.Many2one('res.country.state', string='State ', store=True, ondelete='restrict',
                                              related='corespondence_city_id.state_id')
    corespondence_country_id = fields.Many2one('res.country', string='Country ', store=True, ondelete='restrict',
                                                related='corespondence_state_id.country_id')

    # Identification
    identification_type = fields.Selection([
        ('cnic', 'CNIC'),
        ('parent_cnic', "Parent's CNIC"),
        ('passport', 'Passport'),
        ('form_b', 'Form B'),
        ('ni_cop', 'NICOP'),
    ], default='cnic', string='Identification Type', tracking=True)
    relation_name = fields.Char(string="Mother/Father", tracking=True)
    cnic = fields.Char(string='CNIC Number', tracking=True)
    cnic_expiry_date = fields.Date(string='CNIC Expiry Date')
    cnic_front = fields.Binary(string='CNIC Front', attachment=True)
    cnic_back = fields.Binary(string='CNIC Back', attachment=True)
    nicop = fields.Char(string='NICOP')
    passport = fields.Char(string='Passport Number', tracking=True)
    passport_expiry_date = fields.Date(string='Passport Expiry Date')
    passport_front = fields.Binary(string='Passport Front', attachment=True)
    form_b = fields.Char(string='Form B Number', tracking=True)
    form_b_front = fields.Binary(string='Form B Front', attachment=True)

    # KIN info
    kin_name = fields.Char(string="KIN Name")
    kin_mobile = fields.Char(string="KIN Mobile")
    kin_cnic = fields.Char(string="KIN CNIC")
    document = fields.Binary(string="Document")

    # CNIC lines
    cnic_line_ids = fields.One2many('res.cnic', 'investor_id', string="CNIC Details")

    # Authorized representatives
    authorised_representative_ids = fields.One2many(
        'authorised.representative',
        'investor_id',
        string="Authorised Representatives",
    )

    # UI & workflow helpers
    ref = fields.Char(string='Investor Code', copy=False, tracking=True, readonly=True)
    active = fields.Boolean(default=True)
    image_1920 = fields.Image(max_width=1920, max_height=1920)
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    def _compute_no_of_invoices(self):
        for rec in self:
            if rec.partner_id:
                rec.no_of_invoices = self.env['account.payment'].search_count([
                    ('partner_id', '=', rec.partner_id.id),
                ])
            else:
                rec.no_of_invoices = 0

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'

    def open_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)] if self.partner_id else [('id', '=', False)],
        }

    def _ensure_partner(self):
        """Create or sync the res.partner bridge record used for accounting."""
        for rec in self:
            if not rec.partner_id:
                partner = self.env['res.partner'].sudo().create({
                    'name': rec.investor_id or 'Investor',
                    'company_type': 'person',
                    'email': rec.email or False,
                    'phone': rec.phone or rec.mobile or False,
                })
                rec.partner_id = partner.id
            else:
                vals = {}
                if rec.investor_id:
                    vals['name'] = rec.investor_id
                if vals:
                    rec.partner_id.sudo().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].sudo().next_by_code('investor.sequence.number') or _('New')
        records = super().create(vals_list)
        for rec in records:
            rec._ensure_partner()
            rec._add_kin_as_representative()
        return records

    def write(self, vals):
        if 'ref' in vals:
            for rec in self:
                if rec.ref and rec.ref != _('New'):
                    raise UserError(_('Investor Code cannot be changed once it is assigned.'))
        res = super().write(vals)
        if 'investor_id' in vals:
            for rec in self:
                if rec.partner_id:
                    rec.partner_id.sudo().write({'name': vals['investor_id']})
        return res

    def unlink(self):
        """Investors still referenced by other records (e.g. Investment.partner_id)
        can't be deleted due to FK constraints. Archive those instead of failing
        the whole operation with a raw DB error."""
        to_archive = self.browse()
        for investor in self:
            try:
                with self.env.cr.savepoint():
                    super(ResInvestor, investor).unlink()
            except psycopg2.Error:
                to_archive |= investor
        if to_archive:
            to_archive.write({'active': False})
        return True

    @api.onchange('city_id')
    def _onchange_city_id(self):
        self.state_id = self.city_id.state_id.id
        self.zip = self.city_id.zip
        self.country_id = self.state_id.country_id.id

    @api.onchange('cnic')
    def _onchange_cnic_format(self):
        self.cnic = _format_cnic(self.cnic)

    @api.onchange('kin_cnic')
    def _onchange_kin_cnic_format(self):
        self.kin_cnic = _format_cnic(self.kin_cnic)

    @api.onchange('is_same')
    def _onchange_is_same(self):
        if self.is_same:
            self.corespondence_street, self.corespondence_street2, self.corespondence_city_id = \
                self.street, self.street2, self.city_id.id
        else:
            self.corespondence_street = self.corespondence_street2 = False
            self.corespondence_city_id = False

    def _add_kin_as_representative(self):
        if self.kin_name and self.kin_mobile:
            self.authorised_representative_ids = [(0, 0, {
                'name': self.kin_name,
                'mobile': self.kin_mobile,
                'cnic': self.kin_cnic or False,
                'document': self.document or False,
            })]

    def approve(self):
        for rec in self:
            rec.state = 'approve'

    def create_registration_invoice(self):
        if not self.is_invoice_generation:
            self._ensure_partner()
            for lines in self.fees_line_ids:
                adv_pay = self.env['account.payment'].create({
                    'advance_against': 'other',
                    'payment_category': 'advance_payment',
                    'partner_id': self.partner_id.id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'date': lines.date,
                    'memo': lines.remarks,
                    'mode_of_payments': lines.mode_of_payments,
                    'amount': lines.total_amount,
                    'advance_payment_account_id': self.env.company.advance_payment_account_id.id,
                    'journal_id': lines.journal_id.id,
                })
                if adv_pay:
                    adv_pay.action_post()
                    lines.payment_id = adv_pay.id
            self.is_invoice_generation = True
            self.state = 'invoice'
        else:
            raise ValidationError(_('Invoice is already generated'))


class AmenityAmenity(models.Model):
    _name = 'amenity.amenity'
    _description = 'Amenity / Fee Type'

    name = fields.Char(required=True)


class RefundPolicy(models.Model):
    _name = 'refund.policy'
    _description = 'Refund Policy'

    name = fields.Char(required=True)


class RegistrationSecurityLines(models.Model):
    _name = 'registration.security.line'
    _description = 'Registration Security Line'

    amenity_id = fields.Many2one('amenity.amenity', required=True)
    total_amount = fields.Float()
    refund_policy = fields.Many2one('refund.policy')
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default="cash")
    journal_id = fields.Many2one('account.journal', string='Journal')
    date = fields.Date()
    remarks = fields.Char(string='Remarks')
    move_id = fields.Many2one('account.move')
    payment_id = fields.Many2one('account.payment')
    investor_id = fields.Many2one('res.investor')


class AuthorisedRepresentativeExt(models.Model):
    _inherit = 'authorised.representative'

    investor_id = fields.Many2one('res.investor', ondelete='cascade')


class CnicLinesExt(models.Model):
    _inherit = 'res.cnic'

    investor_id = fields.Many2one('res.investor', ondelete='cascade')
    email = fields.Char(tracking=True)
