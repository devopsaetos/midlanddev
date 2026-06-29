# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartnerExt(models.Model):
    _inherit = 'res.partner'

    is_unit_booking_agent = fields.Boolean()
    unit_booking_agent_type = fields.Selection([
        ('main_agent', "Main Dealer"),
        ('sub_agent', "Sub Dealer")],
        string="Dealer Type",
        help="""Type of the Dealer. Either the Main Dealer or the Sub Dealer"""
    )
    state = fields.Selection([
        ('draft', "Draft"),
        ('in_process', 'In Process'),
        ('invoice', 'Invoice'),
        ('approve', "Approve"), ('renewal', 'Renewal'), ('cancel', 'Cancel')], default='draft', tracking=True)
    # authorised_representative = fields.One2many('authorised.representative', 'agent_id')
    unit_booking_agent_id = fields.Many2one('res.partner', domain=[('unit_booking_agent_type', '=', 'main_agent')])
    identification_type = fields.Selection([
        ('cnic', 'CNIC'),
        ('parent_cnic', "Parent's CNIC"),
        ('passport', 'Passport'),
        ('form_b', 'Form B'),
        ('ni_cop', 'NICOP'),
    ], default='cnic', string='Identification Type', store=True, tracking=True)
    nicop = fields.Char(string='NICOP')
    valid_till = fields.Date()
    dealer_asset_allocation_id = fields.Many2one('dealer.asset.allocation')

    # registration info
    dealer_category_id = fields.Many2one('dealer.category', tracking=True)
    registration_fee = fields.Float(tracking=True)
    security_fee = fields.Float(tracking=True)
    registration_invoice_id = fields.Many2one('account.move')
    security_invoice_id = fields.Many2one('account.move')
    is_invoice_generation = fields.Boolean(default=False)
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    def _compute_no_of_invoices(self):
        for rec in self:
            rec.no_of_invoices = len(self.env['account.move'].search([('partner_id', '=', rec.id), ('move_type', '=', 'out_invoice'), ('property_invoice_type', 'in', ['security', 'registration'])]))

    def open_allocation(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('unit_booking.dealer_asset_allocation_tree').id, 'list'),
                      (self.env.ref('unit_booking.dealer_asset_allocation_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Allocation'),
            'res_model': 'dealer.asset.allocation',
            'domain': [('partner_id', '=', self.id)],
        }

    @api.onchange('dealer_category_id')
    def set_value(self):
        for rec in self:
            if rec.dealer_category_id:
                rec.registration_fee = rec.dealer_category_id.registration_fee
                rec.security_fee = rec.dealer_category_id.security_fee

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'

    def create_invoice(self):
        # registration fee invoice
        if not self.is_invoice_generation:
            registration_fee_invoice = self.env['account.move'].create({
                'partner_id': self.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'out_invoice',
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_date': fields.Date.today(),
                'property_invoice_type': 'registration',
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.dealer_registration').id,
                    'name': self.env.ref('unit_booking.dealer_registration').name,
                    'account_id': self.env.ref('unit_booking.dealer_registration').property_account_income_id.id,
                    'price_unit': self.registration_fee
                })]
            })

            registration_fee_invoice.action_post()
            self.registration_invoice_id = registration_fee_invoice.id

            # security fee invoice
            security_fee_invoice = self.env['account.move'].create({
                'partner_id': self.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'out_invoice',
                'property_invoice_type': 'security',
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.dealer_security').id,
                    'name': self.env.ref('unit_booking.dealer_security').name,
                    'account_id': self.env.ref('unit_booking.dealer_security').property_account_income_id.id,
                    'price_unit': self.security_fee
                })]
            })

            security_fee_invoice.action_post()
            self.security_invoice_id = security_fee_invoice.id

            self.is_invoice_generation = True
            self.state = 'invoice'
        else:
            raise ValidationError(_('Invoice is already generated'))

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'domain': [('partner_id', '=', self.id), ('move_type', '=', 'out_invoice'),
                       ('property_invoice_type', 'in', ['security', 'registration'])],
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'is_unit_booking_agent' in vals and vals['is_unit_booking_agent']:
                vals['ref'] = self.env['ir.sequence'].next_by_code("dealer.sequence.number") or _('New')
        record = super().create(vals_list)
        if self.env.context.get('active_model') == "open.file.issuance.request":
            request = self.env['open.file.issuance.request'].browse(self.env.context.get('active_id'))
            request.is_transferee_partner = True
            request.transferee_partner_id = record.id

        return record

    @api.constrains('dob')
    def check_starting_and_ending(self):
        for recs in self:
            if recs.dob and recs.is_unit_booking_agent:
                if recs.dob > fields.Date.today():
                    raise ValidationError(
                        _("Date of birth can't be in future"))

    @api.constrains('email')
    def check_constrain_valid_email(self):
        for rec in self:
            if rec.email and rec.is_unit_booking_agent:
                regex = re.compile('^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$')
                if not (re.search(regex, rec.email)):
                    raise ValidationError(_('Please Enter Valid Email'))

    @api.constrains('cnic_line_ids')
    def len_of_record(self):
        for rec in self:
            if rec.company_type == 'aop' and rec.is_unit_booking_agent:
                if len(rec.cnic_line_ids) < 2:
                    raise ValidationError(_('Add minimum 2 line in joint owner detail'))

    @api.constrains('form_b', 'secondary_phone', 'phone', 'cp_mobile', 'cnic')
    def validate_fields(self):
        for rec in self:
            if rec.is_unit_booking_agent:
                regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
                if rec.form_b:
                    if regex.search(rec.form_b) is not None:
                        raise ValidationError(_('Please enter valid Form B Number'))
                elif rec.secondary_phone:
                    if regex.search(rec.secondary_phone) is not None:
                        raise ValidationError(_('Please enter valid secondary Phone Number'))
                elif rec.phone:
                    if regex.search(rec.phone) is not None:
                        raise ValidationError(_('Please enter valid Phone Number'))
                elif rec.cp_mobile:
                    if regex.search(rec.cp_mobile) is not None:
                        raise ValidationError(_('Please enter valid Company Mobile Number'))
                elif rec.cnic:
                    if regex.search(rec.cnic) is not None:
                        raise ValidationError(_('Please enter valid Dealer CNIC Number'))

    def set_to_approve(self):
        for rec in self:
            if rec.is_unit_booking_agent:
                rec.check_constrain_special_char_mobile()
                rec.state = 'approve'

    def unlink(self):
        for rec in self:
            if rec.state == 'approve' and rec.is_unit_booking_agent:
                raise ValidationError(_('You cannot delete a record once it is approved.'))
        return super(ResPartnerExt, self).unlink()


class DealerCategory(models.Model):
    _name = 'dealer.category'
    _description = 'Dealer Category'

    name = fields.Char()
    registration_fee = fields.Float()
    security_fee = fields.Float()
    state = fields.Selection([
        ('draft', "Draft"),
        ('approve', "Approve")], default='draft')

    def approve_category(self):
        for rec in self:
            rec.state = 'approve'
