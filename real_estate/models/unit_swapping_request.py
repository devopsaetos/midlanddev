# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from lxml import etree as ET

import qrcode
import base64
from io import BytesIO
import string
import random
import PIL
from PIL import Image
import os
import requests
import secrets


class UnitSwappingRequest(models.Model):
    _name = 'unit.swapping.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Unit Swapping Request"

    member_image= fields.Binary(attachment=True, string='Member Image')
    member_cnic_front= fields.Binary(attachment=True, string='Member CNIC Front')
    member_cnic_back = fields.Binary(attachment=True, string='Member CNIC Back')
    kin_cnic_front = fields.Binary(attachment=True, string='KIN CNIC Front')
    kin_cnic_back = fields.Binary(attachment=True, string='KIN CNIC Back')
    file_issuance_request = fields.Binary(attachment=True, string='File Issuance Request')

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'), tracking=True)
    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'In Process'),
        ('approve', 'Approved'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    applicable_on = fields.Selection([
        ('investment', 'Investment'),
        ('file', 'File'),
    ], tracking=True)
    membership_id = fields.Many2one('res.member', string='Member No')
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Member Type', related='membership_id.company_type')
    cnic = fields.Char(related='file_id.membership_id.cnic')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", tracking=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", tracking=True)
    sector_id = fields.Many2one('sector', tracking=True)
    category_id = fields.Many2one('plot.category', string='Plot Category', tracking=True)
    street_id = fields.Many2one('street', tracking=True)
    inventory_id = fields.Many2one('plot.inventory', tracking=True)
    unit_number = fields.Char(tracking=True)
    size_id = fields.Many2one('unit.size', 'Unit Size', tracking=True)
    unit_category_type_id = fields.Many2one('unit.category.type', tracking=True)
    unit_class_id = fields.Many2one('unit.class', tracking=True)
    member_name = fields.Char(related='file_id.membership_id.name', string="Member Name")
    file_id = fields.Many2one('file', tracking=True)
    tracking_id = fields.Char(related='file_id.tracking_id')
    booking_date = fields.Date(related='file_id.booking_date')

    # New unit details
    new_inventory_id = fields.Many2one('plot.inventory', tracking=True)
    new_society_id = fields.Many2one('society', 'New Society', domain="[('is_society','=',True)]",
                                     related='new_inventory_id.society_id')
    new_phase_id = fields.Many2one('society', 'New Phase', domain="[('is_society','!=',True)]",
                                   related='new_inventory_id.phase_id')
    new_sector_id = fields.Many2one('sector', related='new_inventory_id.sector_id', string="New Sector")
    new_category_id = fields.Many2one('plot.category', string='New Plot Category', related='new_inventory_id.category_id')
    new_street_id = fields.Many2one('street', related='new_inventory_id.street_id', string='New Street')
    new_size_id = fields.Many2one('unit.size', 'New Unit Size', related='new_inventory_id.size_id')
    new_unit_category_type_id = fields.Many2one('unit.category.type', related='new_inventory_id.unit_category_type_id', string="New Unit Category Type")
    new_unit_class_id = fields.Many2one('unit.class', related='new_inventory_id.unit_class_id', string="New Unit Class")
    new_membership_id = fields.Many2one('res.member', string='New Member No')

    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('authorised_person', 'Authorised Person'),
        ('change_amount', 'Change Amount'),
        ('member_swap', 'Member Swap')
    ], tracking=True)
    appointment_date = fields.Datetime(tracking=True)

    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O', tracking=True)

    relation_name = fields.Char(tracking=True)

    # Payment Plan
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    balloting_amount = fields.Float('Balloting Amount', related='file_id.balloting_amount')
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    change_price = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    amount = fields.Float()
    apply_charges = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no')
    charges_amount = fields.Float()
    invoice_created = fields.Boolean()
    invoice_paid = fields.Boolean()

    # Transferee details
    is_transferee_partner = fields.Boolean('Is Member ?')
    transferee_company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Transferee Type', tracking=True)
    transferee_name = fields.Char('Transferee Name', tracking=True)
    transferee_cnic_number = fields.Char('CNIC Number', tracking=True)
    transferee_passport = fields.Char('Passport No.', tracking=True)
    transferee_emirates_id = fields.Char(string='Emirates ID', tracking=True)
    transferee_mobile = fields.Char('Mobile', tracking=True)
    # transferee_cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details ')
    transferee_email = fields.Char('Email', tracking=True)
    transferee_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string='Gender', default='male')
    transferee_partner_id = fields.Many2one('res.member', 'Name ', tracking=True)

    transferee_relation = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O', tracking=True)
    transferee_relation_name = fields.Char(tracking=True)

    # Address related fields
    transferee_street = fields.Char()
    transferee_street2 = fields.Char()
    transferee_zip = fields.Char()
    transferee_city_id = fields.Many2one('city', change_default=True, string='City ', tracking=True)
    transferee_state_id = fields.Many2one("res.country.state", string='State ')
    transferee_country_id = fields.Many2one('res.country', string='Country ', tracking=True)
    # Correspondence Address
    transferee_secondary_mobile = fields.Char(string='Secondary Mobile', tracking=True)
    is_same = fields.Boolean('Same Address')
    corespondence_street = fields.Char(string='Street')
    corespondence_street2 = fields.Char(string='Street 2')
    corespondence_city_id = fields.Many2one('city', change_default=True, string='City')
    corespondence_zip = fields.Char(change_default=True, store=True, related='corespondence_city_id.zip', string='Zip')
    corespondence_state_id = fields.Many2one("res.country.state", string='State', store=True, ondelete='restrict', related='corespondence_city_id.state_id')
    corespondence_country_id = fields.Many2one('res.country', string='Country', store=True, ondelete='restrict', related='corespondence_state_id.country_id')
    # Next of Kin fields
    kin_name = fields.Char(tracking=True)
    kin_cnic = fields.Char(string='CNIC', tracking=True)
    kin_mobile = fields.Char(string='Mobile No', tracking=True)
    kin_member_relation = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('wife', 'Wife'),
        ('husband', 'Husband'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('other', 'Other'),
    ], string='Relation With Member', tracking=True)
    other_relation = fields.Char('Relation ', tracking=True)

    # Address Fields for authorised person
    street = fields.Char()
    city = fields.Char()
    province = fields.Char()
    country = fields.Char()

    # Investment Fields
    investment_id = fields.Many2one('investment')
    investor_id = fields.Many2one('res.member', domain=[('is_investor', '=', True)], readonly=False, related='investment_id.partner_id', store=True)
    unit_swapping_request_lines = fields.One2many('unit.swapping.request.lines', 'unit_swapping_request_id')
    cancel_all_units = fields.Boolean()
    from_app = fields.Boolean()
    update_existing_person = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], default='no', tracking=True)
    image_1920 = fields.Image()
    cnic_front = fields.Binary(attachment=True, string='ID Front')
    cnic_back = fields.Binary(attachment=True, string='ID Back')
    passport_front = fields.Binary(attachment=True, string='Passport Front')
    passport_back = fields.Binary(attachment=True, string='Passport Back')
    emirates_id_front = fields.Binary(attachment=True, string='Emirates ID Front')
    emirates_id_back = fields.Binary(attachment=True, string='Emirates ID Back')
    # computed field
    qr_code = fields.Binary("QR Code", compute='generate_qr_code', attachment=True)
    secret_token = fields.Char(string="Secret Token", required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)

    # @api.model
    def assign_secret_tokens(self):
        # Fetch records that have the token as 'New' or empty
        records_with_default_token = self.search([('secret_token', '=', 'New')])
        for record in records_with_default_token:
            # Assign a new unique token if the token is still 'New'
            record.secret_token = secrets.token_hex(10)

    @api.depends('name', 'applicable_on')
    def generate_qr_code(self):
        for rec in self:
            if rec.name and rec.applicable_on:
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
                    'model': 'units.swapping.request',
                    # 'menu_id': self.env.ref('module_name.menu_record_id').id,
                    'action': self.env.ref('real_estate.action_file_issuance_request').id,
                }'''
                # params = '/booking/verification/%s/%s' % (rec.id, rec.name)
                params = '/booking/verification/%s' % rec.name
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if vals['transaction_type'] == 'open_file':
                    if self.env.company.id != 1:
                        random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        vals['name'] = 'IFR - '+random_num
                    else:
                        vals['name'] = self.env['ir.sequence'].next_by_code("investment.file.issuance.request") or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code("unit.swapping.request") or _('New')
            if vals.get('secret_token', _('New')) == _('New'):
                vals['secret_token'] = secrets.token_hex(10)
        rec = super(UnitSwappingRequest, self).create(vals_list)

        return rec

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'
            if rec.applicable_on == 'investment':
                for line in rec.unit_swapping_request_lines:
                    line.investor_file_id.state = 'open'
            if rec.applicable_on == 'file':
                rec.file_id.state = 'available'

    def approve_request(self):
        if self.applicable_on == 'file':
            if self.apply_charges == 'yes' and not self.invoice_created:
                raise ValidationError('Please create invoice and pay the charges.')
            if self.invoice_created and not self.invoice_paid:
                raise ValidationError('Please pay the charges for unit swap.')
            if self.transaction_type == 'cancel':
                self.file_id.state = 'cancel'
                self.file_id.file_status = 'cancel'
                self.file_id.inventory_id.state = 'avalible_for_sale'
                self.state = 'approve'
            if self.new_inventory_id and self.change_price == 'yes':
                paid_amount = sum(self.file_id.installment_plan_ids.filtered(lambda l: l.invoice_created and l.payment_status == 'paid').mapped('amount_paid'))
                plans = self.file_id.installment_plan_ids.filtered(lambda l: not l.invoice_created)
                difference_amount = 0
                if self.file_id.net_sale_amount < self.amount:
                    difference_amount = self.amount - self.file_id.net_sale_amount
                    installment_amount = difference_amount / len(plans)
                    if installment_amount > 0:
                        for plan in plans:
                            plan.amount += installment_amount
                            plan.residual += installment_amount
                elif self.file_id.net_sale_amount > self.amount:
                    difference_amount = self.file_id.net_sale_amount - self.amount
                    installment_amount = difference_amount / len(plans)
                    if installment_amount > 0:
                        for plan in plans:
                            plan.amount -= installment_amount
                            plan.residual = plan.amount

                history = self.file_id.file_request_history_ids.create({
                    'transaction_type': self.transaction_type,
                    'transaction_date': fields.Date.today(),
                    'ref_number': self.name,
                    'old_inventory_id': self.inventory_id.id,
                    'new_inventory_id': self.new_inventory_id.id,
                    'old_amount': self.net_sale_amount,
                    'new_amount': self.amount,
                    'file_id': self.file_id.id,
                })

                self.file_id.inventory_id.state = 'avalible_for_sale'
                self.file_id.net_sale_amount += difference_amount
                self.file_id.balance_amount += difference_amount
                # self.file_id.write({
                #                     'inventory_id': self.new_inventory_id.id,
                #                     'phase_id': self.new_inventory_id.phase_id.id,
                #                     'sector_id': self.new_inventory_id.sector_id.id,
                #                     'category_id': self.new_inventory_id.category_id.id,
                #                     'street_id': self.new_inventory_id.street_id.id,
                #                     'unit_category_type_id': self.new_inventory_id.unit_category_type_id.id,
                #                     'state': 'available',
                #                     })
                self.file_id.inventory_id = self.new_inventory_id.id
                self.file_id.phase_id = self.new_inventory_id.phase_id.id
                self.file_id.sector_id = self.new_inventory_id.sector_id.id
                self.file_id.category_id = self.new_inventory_id.category_id.id
                self.file_id.street_id = self.new_inventory_id.street_id.id
                self.file_id.unit_category_type_id = self.new_inventory_id.unit_category_type_id.id
                self.file_id.inventory_id.state = 'sold'
                self.file_id.state = 'available'
                self.state = 'approve'

            elif self.new_inventory_id and self.change_price != 'yes':
                self.file_id.inventory_id.state = 'avalible_for_sale'
                self.file_id.inventory_id = self.new_inventory_id.id
                self.file_id.phase_id = self.new_inventory_id.phase_id.id
                self.file_id.sector_id = self.new_inventory_id.sector_id.id
                self.file_id.category_id = self.new_inventory_id.category_id.id
                self.file_id.street_id = self.new_inventory_id.street_id.id
                self.file_id.unit_category_type_id = self.new_inventory_id.unit_category_type_id.id
                self.file_id.inventory_id.state = 'sold'
                self.file_id.state = 'available'
                self.state = 'approve'

                history = self.file_id.file_request_history_ids.create({
                    'transaction_type': self.transaction_type,
                    'transaction_date': fields.Date.today(),
                    'ref_number': self.name,
                    'old_inventory_id': self.inventory_id.id,
                    'new_inventory_id': self.new_inventory_id.id,
                    'old_amount': self.net_sale_amount,
                    'new_amount': self.amount,
                    'file_id': self.file_id.id,
                })

            elif self.new_membership_id:
                self.file_id.membership_id = self.new_membership_id.id

                history = self.file_id.file_request_history_ids.create({
                    'transaction_type': self.transaction_type,
                    'transaction_date': fields.Date.today(),
                    'ref_number': self.name,
                    'old_membership_id': self.membership_id.id,
                    'new_membership_id': self.new_membership_id.id,
                    'file_id': self.file_id.id,
                })
                self.state = 'approve'
        elif self.applicable_on == 'investment':
            if self.transaction_type == 'swap':
                for rec in self.unit_swapping_request_lines:
                    open_file = self.env['investor.file'].search([('inventory_id', '=', rec.inventory_id.id)])
                    open_file.inventory_id.state = 'avalible_for_sale'
                    open_file.inventory_id.list_price = 0.0
                    open_file.inventory_id.investor_unit_price = 0.0
                    open_file.inventory_id.deal_price = 0.0
                    rec.investment_id.inventory_ids = [(3, rec.inventory_id.id)]
                    open_file.inventory_id = rec.new_inventory_id.id
                    rec.new_inventory_id.list_price = rec.investment_id.investor_unit_price
                    rec.new_inventory_id.investor_unit_price = rec.investment_id.investor_unit_price
                    rec.new_inventory_id.deal_price = rec.investment_id.investor_unit_price
                    rec.investment_id.inventory_ids = [(4, rec.new_inventory_id.id)]
                    open_file.sector_id = rec.new_inventory_id.sector_id.id
                    open_file.street_id = rec.new_inventory_id.street_id.id
                    open_file.category_id = rec.new_inventory_id.category_id.id
                    open_file.size_id = rec.new_inventory_id.size_id.id
                    open_file.unit_category_type_id = rec.new_inventory_id.unit_category_type_id.id
                    open_file.unit_class_id = rec.new_inventory_id.unit_class_id.id
                    open_file.inventory_id.state = 'investor'
                    print(open_file)

                self.file_id.state = 'available'
                self.state = 'approve'

            elif self.transaction_type == 'cancel':

                # All open files against this investment
                unassigned_files = self.env['investor.file'].search([('investment_id', '=', self.investment_id.id)])

                # Open files in this request.
                open_files = self.env['investor.file'].search([
                    ('inventory_id', 'in', self.unit_swapping_request_lines.inventory_id.ids)
                ])

                due_invoices = self.investment_id.investment_plan_ids.filtered(lambda l: l.invoice_created == True and l.payment_status != 'paid')

                if all(self.investment_id.investment_plan_ids.mapped('invoice_created')):
                    amount = sum(open_files.mapped('net_sale_amount'))
                    self.investment_id.balance_amount = 0 if self.cancel_all_units else self.investment_id.total_amount - self.investment_id.down_payment
                    self.create_credit_note(amount)

                    investment_history = self.investment_id.investment_history_ids.create({
                        'installment_number': self.investment_id.investment_history_ids[
                                                  -1].installment_number + 1,
                        'date': fields.Date.today(),
                        'transaction_type': 'cancel',
                        'amount': 0,
                        'new_amount': self.investment_id.investment_history_ids[-1].amount - amount,
                        'old_balance': self.investment_id.investment_history_ids[-1].new_balance,
                        'new_balance': self.investment_id.investment_history_ids[-1].old_balance - amount,
                        'investment_id': self.investment_id.id,
                    })

                    # Updating remaining installments amount
                    for line in self.investment_id.investment_plan_ids.filtered(
                            lambda l: l.invoice_created == True and l.residual == 0):
                        line.update({'file_adjusted_amount': 0,
                                     'adjustment_amount': amount,
                                     'balance_amount': line.balance_amount - amount})

                elif due_invoices:
                    for rec in due_invoices:
                        prorate_amount = rec.balance_amount / len(unassigned_files)
                        amount = prorate_amount * len(open_files)
                        self.create_credit_note(amount)

                    # Updating Plan and Adjustment History
                    amount_to_deduct = round(
                        (self.investment_id.investment_history_ids[-1].new_amount / len(unassigned_files.filtered(lambda l: l.state == 'open'))) * len(open_files))
                    investment_history = self.investment_id.investment_history_ids.create({
                        'installment_number': self.investment_id.investment_history_ids[
                                                  -1].installment_number + 1,
                        'date': fields.Date.today(),
                        'transaction_type': 'cancel',
                        'amount': round(self.investment_id.investment_history_ids[-1].new_amount),
                        'new_amount': self.investment_id.investment_history_ids[-1].new_amount - amount_to_deduct,
                        'old_balance': self.investment_id.investment_history_ids[-1].new_balance,
                        'new_balance': self.investment_id.investment_history_ids[-1].new_balance - (amount_to_deduct * self.investment_id.total_installment),
                        'investment_id': self.investment_id.id,
                    })

                    # Updating remaining installments amount
                    for line in self.investment_id.investment_plan_ids.filtered(lambda l: l.invoice_created != True and l.balance_amount > 0):
                        line.update({'file_adjusted_amount': 0,
                                     'balance_amount': investment_history.new_amount,
                                     'residual': investment_history.new_amount})

                down_payment = round((self.investment_id.down_payment / len(
                    unassigned_files.filtered(lambda l: l.state != 'cancel')))) * len(open_files)
                self.investment_id.down_payment = self.investment_id.down_payment - down_payment
                # Updating Open file fields
                for open_file in open_files:
                    open_file.state = 'cancel'
                    open_file.inventory_id.state = 'avalible_for_sale'
                    open_file.inventory_id.list_price = 0.0
                    open_file.inventory_id.investor_unit_price = 0.0
                    open_file.inventory_id.deal_price = 0.0
                    self.investment_id.inventory_ids = [(3, open_file.inventory_id.id)]

                # Creating units Cancel/Swap history
                self.investment_id.unit_cancel_swap_ids = [(0, 0,
                                                            {'date': fields.Date.today(),
                                                             'transaction_type': line.transaction_type,
                                                             'investment_id': line.investment_id.id,
                                                             'sector_id': line.sector_id.id,
                                                             'category_id': line.category_id.id,
                                                             'unit_category_type_id': line.unit_category_type_id.id,
                                                             'size_id': line.size_id.id,
                                                             'unit_class_id': line.unit_class_id.id,
                                                             'inventory_id': line.inventory_id.id,
                                                             'investor_unit_price': line.investor_unit_price,
                                                             'new_inventory_id': line.new_inventory_id.id,
                                                             }) for line in self.unit_swapping_request_lines]
                if self.cancel_all_units:
                    self.investment_id.state = 'cancel'

                self.file_id.state = 'available'
                self.state = 'approve'

            elif self.transaction_type == 'open_file':
                if not self.is_transferee_partner and not all(
                        [self.transferee_name, self.transferee_mobile, self.transferee_relation_name, self.transferee_street, self.transferee_country_id,
                         self.transferee_company_type, self.kin_name, self.kin_member_relation]):
                    raise ValidationError("Please fill the following fields to proceed: \n "
                                          "Name, Member Type, Mobile, Father/Spouse, Street, Country, Kin Name and Relation.")

                if not self.transferee_partner_id:
                    self.create_partner()

                # if self.investment_id.options == 'full':
                #     if self.investment_id.amount_paid == 0 or self.investment_id.investor_unit_price > self.investment_id.amount_paid:
                #         raise ValidationError('You cannot issue file due to insufficient balance.')

                for rec in self.unit_swapping_request_lines:
                    file = self.env['file'].create({
                        'project_type': self.project_type,
                        'from_open_file': True,
                        'add_custom_value': True,
                        'investment_adjustment': False,
                        'tracking_id': rec.investor_file_id.name,
                        'membership_id': self.transferee_partner_id.id,
                        'membership_name': self.transferee_partner_id.name,
                        'booking_date': rec.investor_file_id.booking_date,
                        'investor_id': self.investor_id.id,
                        'investment_id': self.investment_id.id,
                        'investor_file': rec.investor_file_id.id,
                        'file_type': 'new',
                        'type': 'investor',
                        'state': 'available',
                        'society_id': rec.investor_file_id.society_id.id,
                        'phase_id': rec.investor_file_id.phase_id.id,
                        'sector_id': rec.investor_file_id.sector_id.id,
                        'street_id': rec.investor_file_id.street_id.id,
                        'category_id': rec.investor_file_id.category_id.id,
                        'unit_category_type_id': rec.investor_file_id.unit_category_type_id.id,
                        'size_id': rec.investor_file_id.size_id.id,
                        'unit_class_id': rec.investor_file_id.unit_class_id.id,
                        'inventory_id': rec.investor_file_id.inventory_id.id,
                        'unit_number': rec.investor_file_id.unit_number,
                        'payment_type': 'installments' if rec.investor_file_id.investment_id.options == 'down' else 'lump_sum',
                        'interval_id': rec.investor_file_id.interval_id.id,
                        'starting_date': rec.investor_file_id.starting_date,
                        'total_installment': rec.investor_file_id.total_installment,
                        'payment_states': 'open' if rec.investor_file_id.investment_id.options == 'down' else 'close',
                        'overall_status': 'open' if rec.investor_file_id.investment_id.options == 'down' else 'close',
                        'sale_amount': rec.investor_file_id.sale_amount,
                        'custom_sale_amount': rec.investor_file_id.sale_amount,
                        'ttl_sale_amount': rec.investor_file_id.ttl_sale_amount,
                        'net_sale_amount': rec.investor_file_id.net_sale_amount,
                        'initial_payment': rec.investor_file_id.initial_payment,
                    })

                    self.investment_id.amount_paid = self.investment_id.amount_paid - self.investment_id.investor_unit_price
                    file.investment_adjustment = True
                    # Creating down payment on file which is already paid by investor
                    file.installment_plan_ids.create({
                        'date': rec.investor_file_id.booking_date,
                        'payment_date': rec.investor_file_id.booking_date,
                        'installment_type': 'down',
                        'invoice': 'Paid By Investor',
                        'invoice_created': True,
                        'investor_payment': True,
                        'installment_number': 0,
                        'amount': rec.investor_file_id.initial_payment,
                        'amount_paid': rec.investor_file_id.initial_payment,
                        'residual': 0,
                        'payment_status': 'paid',
                        'file_id': file.id
                    })

                    rec.investor_file_id.state = 'issued'
                    rec.investor_file_id.inventory_id.state = 'sold'
                    rec.investor_file_id.is_transferee_partner = True
                    rec.investor_file_id.transferee_name = self.transferee_name
                    rec.investor_file_id.transferee_partner_id = self.transferee_partner_id.id
                    rec.investor_file_id.transferee_relation_name = self.transferee_relation_name
                    rec.investor_file_id.transferee_cnic_number = self.transferee_cnic_number

                    if self.investment_id.options == 'down':
                        investment_history = file.investment_id.investment_history_ids.create({
                            'installment_number': file.investment_id.investment_history_ids[-1].installment_number + 1 if file.investment_id.investment_history_ids[-1]
                            else 1,
                            'date': fields.Date.today(),
                            'transaction_type': 'customer',
                            'file_id': file.id,
                            'amount': round((file.investment_id.investment_history_ids[
                                                 -1].new_balance / file.investment_id.total_installment)),
                            'new_amount': round(((file.investment_id.investment_history_ids[
                                                      -1].new_balance - file.balance_amount) / file.investment_id.remaining_installments)),
                            'old_balance': file.investment_id.investment_history_ids[-1].new_balance,
                            'new_balance': file.investment_id.investment_history_ids[
                                               -1].new_balance - file.balance_amount,
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
                                             'balance_amount': line.balance_amount - (
                                                     file.balance_amount / file.total_installment),
                                             'residual': line.balance_amount - (
                                                     file.balance_amount / file.total_installment)})

                        file.create_installment_plan()

                self.file_id.state = 'available'
                self.state = 'approve'

            elif self.transaction_type == 'change_amount':

                due_invoices = self.investment_id.investment_plan_ids.filtered(lambda l: l.invoice_created == True and l.payment_status != 'paid')
                available_installments = self.investment_id.investment_plan_ids.filtered(lambda l: l.invoice_created != True and l.balance_amount > 0)
                old_price = sum(self.unit_swapping_request_lines.mapped('investor_unit_price'))
                new_price = sum(self.unit_swapping_request_lines.mapped('new_price'))

                if all(self.investment_id.investment_plan_ids.mapped('invoice_created')):
                    if new_price > old_price:
                        adjustment_amount = new_price - old_price
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.investment_installment').product_id.id,
                            'name': self.env.ref('real_estate.investment_installment').name,
                            'account_id': self.env.ref(
                                'real_estate.investment_installment').product_id.property_account_income_id.id,
                            'price_unit': adjustment_amount
                        })]
                        invoice = self.create_invoice(adjustment_amount, prod)
                        self.investment_id.total_amount = self.investment_id.total_amount + adjustment_amount
                        self.investment_id.investment_plan_ids.create({
                            'installment_number': self.investment_id.investment_plan_ids[-1].installment_number + 1,
                            'date': fields.Date.today(),
                            'installment_type': 'adjustment',
                            'invoice_created': True,
                            'invoice_id': invoice.id,
                            'amount': adjustment_amount,
                            'balance_amount': adjustment_amount,
                            'adjustment_amount': adjustment_amount,
                            'investment_id': self.investment_id.id,
                        })
                        investment_history = self.investment_id.investment_history_ids.create({
                            'installment_number': self.investment_id.investment_history_ids[
                                                      -1].installment_number + 1,
                            'date': fields.Date.today(),
                            'transaction_type': 'investor',
                            'amount': 0,
                            'new_amount': adjustment_amount,
                            'old_balance': 0,
                            'new_balance': adjustment_amount,
                            'investment_id': self.investment_id.id,
                        })

                    if new_price < old_price:
                        adjustment_amount = old_price - new_price
                        invoice = self.create_credit_note(adjustment_amount)
                        self.investment_id.total_amount = self.investment_id.total_amount - adjustment_amount
                        investment_history = self.investment_id.investment_history_ids.create({
                            'installment_number': self.investment_id.investment_history_ids[
                                                      -1].installment_number + 1,
                            'date': fields.Date.today(),
                            'transaction_type': 'investor',
                            'amount': 0,
                            'new_amount': adjustment_amount,
                            'old_balance': 0,
                            'new_balance': adjustment_amount,
                            'investment_id': self.investment_id.id,
                        })

                    for line in self.unit_swapping_request_lines:
                        line.inventory_id.investor_unit_price = line.new_price
                        line.inventory_id.deal_price = line.new_price
                        line.investor_file_id.sale_amount = line.new_price
                        line.investor_file_id.ttl_sale_amount = line.new_price
                        line.investor_file_id.net_sale_amount = line.new_price
                        line.investor_file_id.net_sale_amount = line.new_price
                        line.investor_file_id.balance_amount = line.new_price - line.investor_file_id.initial_payment - line.investor_file_id.balloting_amount

                elif available_installments:
                    if new_price > old_price:
                        adjustment_amount = round((new_price - old_price) / len(available_installments))
                        self.investment_id.total_amount = self.investment_id.total_amount + (new_price - old_price)
                        for plan in available_installments:
                            plan.update({
                                'installment_type': 'adjustment',
                                'balance_amount': plan.balance_amount + adjustment_amount,
                                'residual': plan.balance_amount + adjustment_amount,
                                'adjustment_amount': adjustment_amount,
                            })
                        investment_history = self.investment_id.investment_history_ids.create({
                            'installment_number': self.investment_id.investment_history_ids[-1].installment_number + 1,
                            'date': fields.Date.today(),
                            'transaction_type': 'investor',
                            'amount': self.investment_id.investment_history_ids[-1].new_amount,
                            'new_amount': self.investment_id.investment_history_ids[-1].new_amount + adjustment_amount,
                            'old_balance': self.investment_id.investment_history_ids[-1].new_balance,
                            'new_balance': self.investment_id.investment_history_ids[-1].new_balance + adjustment_amount,
                            'investment_id': self.investment_id.id,
                        })

                    elif new_price < old_price:
                        adjustment_amount = round((old_price - new_price) / len(available_installments))
                        self.investment_id.total_amount = self.investment_id.total_amount - adjustment_amount
                        for plan in available_installments:
                            plan.update({
                                'installment_type': 'adjustment',
                                'balance_amount': plan.balance_amount - adjustment_amount,
                                'residual': plan.balance_amount - adjustment_amount,
                                'adjustment_amount': adjustment_amount,
                            })
                        investment_history = self.investment_id.investment_history_ids.create({
                            'installment_number': self.investment_id.investment_history_ids[-1].installment_number + 1,
                            'date': fields.Date.today(),
                            'transaction_type': 'investor',
                            'amount': self.investment_id.investment_history_ids[-1].new_amount,
                            'new_amount': self.investment_id.investment_history_ids[-1].new_amount - adjustment_amount,
                            'old_balance': self.investment_id.investment_history_ids[-1].new_balance,
                            'new_balance': self.investment_id.investment_history_ids[-1].new_balance - adjustment_amount,
                            'investment_id': self.investment_id.id,
                        })

                    for line in self.unit_swapping_request_lines:
                        line.inventory_id.investor_unit_price = line.new_price
                        line.inventory_id.deal_price = line.new_price
                        line.investor_file_id.sale_amount = line.new_price
                        line.investor_file_id.ttl_sale_amount = line.new_price
                        line.investor_file_id.net_sale_amount = line.new_price
                        line.investor_file_id.net_sale_amount = line.new_price
                        line.investor_file_id.balance_amount = line.new_price - line.investor_file_id.initial_payment - line.investor_file_id.balloting_amount

                self.file_id.state = 'available'
                self.state = 'approve'

            elif self.transaction_type == 'authorised_person':
                if self.investor_id.authorised_representative_ids and self.update_existing_person != 'yes':
                    self.investor_id.authorised_representative_ids.filtered(lambda l: l.status == 'active')[-1].status = 'expire'
                    self.investor_id.authorised_representative_ids = [(0, 0, {
                        'name': self.kin_name,
                        'mobile': self.kin_mobile,
                        'cnic': self.kin_cnic,
                        'street': self.street,
                        'city': self.city,
                        'state': self.province,
                        'country': self.country,
                        'status': 'active'
                    })]
                    self.state = 'approve'
                if self.investor_id.authorised_representative_ids and self.update_existing_person == 'yes':
                    authorised_person = self.investor_id.authorised_representative_ids.filtered(lambda l: l.status == 'active')[-1]
                    if authorised_person:
                        authorised_person.write({'mobile': self.kin_mobile,
                                                 'street': self.street,
                                                 'city': self.city,
                                                 'state': self.province,
                                                 'country': self.country})

                        self.state = 'approve'

    def generate_invoice(self):
        if self.apply_charges and self.charges_amount:
            prod = [(0, 0, {
                'product_id': self.env.ref('real_estate.unit_swapping_charges').product_id.id,
                'name': self.env.ref('real_estate.unit_swapping_charges').name,
                'account_id': self.env.ref('real_estate.unit_swapping_charges').product_id.property_account_income_id.id,
                'price_unit': self.charges_amount
            })]
            invoice = self.env['account.move'].create({
                'partner_id': self.membership_id.partner_id.id,
                'move_type': 'out_invoice',
                'unit_swap_request_id': self.id,
                'investment_id': self.investment_id.id,
                # 'file_ids': self.file_id.id,
                'invoice_date': fields.Date.today(),
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
            })
            invoice.file_ids = self.file_id.id
            invoice.action_post()
            self.invoice_created = True

    def open_invoice(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'domain': [('unit_swap_request_id', '=', self.id), ('move_type', '=', 'out_invoice'), ('partner_id', '=', self.membership_id.partner_id.id)],
            'context': {'default_partner_id': self.membership_id.partner_id.id},
        }

    def create_partner(self):
        partner = self.env['res.member'].with_context({'active_model': 'unit.swapping.request', 'active_id': self.id}).create({
            'project_type': self.society_id.project_type,
            'name': self.transferee_name,
            'company_type': self.transferee_company_type,
            'mobile': self.transferee_mobile,
            'relation_name': self.transferee_relation_name,
            'cnic': self.transferee_cnic_number,
            'passport': self.transferee_passport,
            'emirates_id': self.transferee_emirates_id,
            'email': self.transferee_email,
            'gender': self.transferee_gender,
            'street': self.transferee_street,
            'street2': self.transferee_street2,
            'city_id': self.transferee_city_id.id,
            'zip': self.transferee_zip,
            'state_id': self.transferee_state_id.id,
            'country_id': self.transferee_country_id.id,
            'kin_name': self.kin_name,
            'kin_cnic': self.kin_cnic,
            'kin_member_relation': self.kin_member_relation,
            'kin_mobile': self.kin_mobile,
            'other_relation': self.other_relation
        })

    def create_credit_note(self, amount):
        if amount > 0:
            prod = [(0, 0, {
                'product_id': self.env.ref('real_estate.investment_adjustment').product_id.id,
                'name': self.env.ref('real_estate.investment_adjustment').name,
                'account_id': self.env.ref('real_estate.investment_adjustment').product_id.property_account_income_id.id,
                'price_unit': amount
            })]
            # Credit Note
            invoice = self.env['account.move'].create({
                'partner_id': self.investment_id.partner_id.partner_id.id,
                'move_type': 'out_refund',
                'unit_swap_request_id': self.id,
                'investment_id': self.investment_id.id,
                'invoice_date': fields.Date.today(),
                # 'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
            })
            invoice.action_post()

            return invoice
        else:
            raise ValidationError(_('Please enter amount to create credit note.'))

    def create_invoice(self, amount, prod):
        if amount > 0 and prod:
            invoice = self.env['account.move'].create({
                'partner_id': self.investment_id.partner_id.partner_id.id,
                'move_type': 'out_invoice',
                'unit_swap_request_id': self.id,
                'investment_id': self.investment_id.id,
                # 'file_ids': self.file_id.id,
                'invoice_date': fields.Date.today(),
                # 'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
            })
            invoice.file_ids = self.file_id.id
            invoice.action_post()

            return invoice
        else:
            raise ValidationError(_('Please enter amount to create invoice.'))

    def search_member(self):
        if not self.transferee_cnic_number:
            raise ValidationError("Please enter cnic to search.")

        member = self.env['res.member'].search([('cnic', '=', self.transferee_cnic_number)], limit=1)
        if member:
            # Member Fields
            self.is_transferee_partner = True
            self.transferee_name = member.name
            self.transferee_partner_id = member.id
            self.transferee_company_type = member.company_type
            self.transferee_relation_name = member.relation_name
            self.transferee_mobile = member.mobile
            self.transferee_gender = member.gender
            self.transferee_email = member.email
            self.transferee_street = member.street
            self.transferee_street2 = member.street2
            self.transferee_city_id = member.city_id.id
            self.transferee_zip = member.zip
            self.transferee_country_id = member.country_id.id

            # Kin Fields
            self.kin_name = member.kin_name
            self.kin_cnic = member.kin_cnic
            self.kin_mobile = member.kin_mobile
            self.kin_member_relation = member.kin_member_relation
            self.kin_name = member.kin_name
            self.other_relation = member.other_relation
        else:
            self.is_transferee_partner = False
            self.transferee_name = ''
            self.transferee_partner_id = False
            self.transferee_relation_name = ''
            self.transferee_company_type = ''
            self.transferee_mobile = ''
            self.transferee_gender = ''
            self.transferee_email = ''
            self.transferee_street = ''
            self.transferee_street2 = ''
            self.transferee_city_id = False
            self.transferee_zip = ''
            self.transferee_country_id = False

            # Kin Fields
            self.kin_name = ''
            self.kin_cnic = ''
            self.kin_mobile = ''
            self.kin_member_relation = ''
            self.kin_name = ''
            self.other_relation = ''

    def unlink(self):
        for rec in self:
            if rec.state == 'draft':
                rec.file_id.state = 'available'
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record once it is approved!'))

        return super(UnitSwappingRequest, self).unlink()


class UnitSwappingRequestLines(models.Model):
    _name = 'unit.swapping.request.lines'
    _description = 'Unit Swapping Request Lines'

    investment_id = fields.Many2one('investment')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Plot Category')
    inventory_id = fields.Many2one('plot.inventory', default=False)
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size')
    unit_category_type_id = fields.Many2one('unit.category.type')
    unit_class_id = fields.Many2one('unit.class')
    unit_swapping_request_id = fields.Many2one('unit.swapping.request')

    new_price = fields.Float()
    new_inventory_id = fields.Many2one('plot.inventory')
    check = fields.Boolean()
    transaction_type = fields.Selection([
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('open_file', 'File Issuance'),
        ('change_amount', 'Change Amount')
    ], default='swap')
    investor_unit_price = fields.Float()
    investor_file_id = fields.Many2one('investor.file')
    ttl_sale_amount = fields.Float(related='investor_file_id.ttl_sale_amount')
