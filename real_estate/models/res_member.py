# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from lxml import etree as ET
import json


class ResMember(models.Model):
    _name = 'res.member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Members"
    _rec_name = 'name'

    project_type = fields.Selection([('skyscraper', 'Skyscraper'), ('housing_society', 'Housing Society')], default="housing_society")

    # Fields normally provided "for free" by res.partner inheritance - now declared explicitly
    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Salesperson')
    is_company = fields.Boolean()
    vat = fields.Char(string="NTN")
    function = fields.Char(string="Profession")
    category_id = fields.Many2many('res.partner.category', string="Tags")
    image_1920 = fields.Image(max_width=1920, max_height=1920)

    ref = fields.Char('Member Number', required=True, copy=False, readonly=True, index=True,
                      default=lambda self: _('New'))
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owner'),
    ], default='person', tracking=True)
    street = fields.Char(tracking=True)
    street2 = fields.Char(tracking=True)
    zip = fields.Char(tracking=True)
    city = fields.Char(tracking=True)
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]", tracking=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', tracking=True)
    email = fields.Char(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    emirates_id = fields.Char(string='Emirates ID', tracking=True)
    is_investor = fields.Boolean()
    source_ids = fields.Many2one('source')
    crm_id = fields.Many2one('crm.lead')
    token_id = fields.Many2one('token.money')
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')
    no_of_files = fields.Integer(compute='_compute_no_of_files')
    no_of_realestate_files = fields.Integer(compute='_compute_no_of_realestate_files')
    no_of_project_files = fields.Integer(compute='_compute_no_of_project_files')
    tracking_id = fields.Char(compute='_compute_tracking_id', search="_search_tracking_id")
    token_generated = fields.Boolean(related='token_id.token_generated', readonly=True)

    # Address related fields
    city_id = fields.Many2one('city', string='City')
    is_same = fields.Boolean('Same Address')
    corespondence_street = fields.Char()
    corespondence_street2 = fields.Char()
    corespondence_zip = fields.Char(store=True, related='corespondence_city_id.zip')
    corespondence_city_id = fields.Many2one('city')
    corespondence_state_id = fields.Many2one("res.country.state", string='State ', store=True, ondelete='restrict',
                                             related='corespondence_city_id.state_id')
    corespondence_country_id = fields.Many2one('res.country', string='Country ', store=True, ondelete='restrict',
                                               related='corespondence_state_id.country_id')

    # In contact info phone and mobile are inherited
    country_code_phone_id = fields.Many2one('res.country.code')
    country_code_mobile_id = fields.Many2one('res.country.code')
    country_code_mobile2_id = fields.Many2one('res.country.code')
    secondary_phone = fields.Char()

    # Contact Person Info
    cp_name = fields.Char('Name ')
    cp_mobile = fields.Char('Mobile ')
    cp_desigination = fields.Char('Designation')
    cp_landline = fields.Char('LandLine')
    cp_code_mobile_id = fields.Many2one('res.country.code')
    cp_code_landline_id = fields.Many2one('res.country.code')

    # Company Information
    nature_of_business = fields.Char('Nature Of Business')
    company_tel = fields.Char('Telephone')
    fax = fields.Char('FAX')
    uan = fields.Char('UAN')
    tax_status = fields.Selection([
        ('filer', 'Filer'),
        ('non_filer', 'Non-Filer'),
    ], string='Tax Status')
    company_email = fields.Char('Email ')

    # Relation of Member
    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')
    relation_name = fields.Char(tracking=True)

    identification_type = fields.Selection([
        ('cnic', 'CNIC'),
        ('parent_cnic', "Parent's CNIC"),
        ('passport', 'Passport'),
        ('form_b', 'Form B'),
    ], default='cnic', string='Identification Type')

    cnic = fields.Char('ID Number', copy=False, tracking=True)
    cnic_expiry_date = fields.Date('ID Expiry Date')
    cnic_front = fields.Binary(attachment=True, string='ID Front')
    cnic_back = fields.Binary(attachment=True, string='ID Back')

    cnic_line_ids = fields.One2many('res.cnic', 'member_id')

    passport = fields.Char('Passport', copy=False, )
    passport_expiry_date = fields.Date('Passport Expiry Date')
    passport_front = fields.Binary(attachment=True, string='Passport Front')

    form_b = fields.Char('Form B', copy=False, )
    form_b_front = fields.Binary(attachment=True, string='Form B Front')

    # Hidden technical accounting link - never exposed on any res.member view.
    # Auto-managed by create()/write()/unlink()/toggle_active() below.
    partner_id = fields.Many2one('res.partner', string='Accounting Partner',
                                  copy=False, ondelete='restrict', index=True, readonly=True)

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
    kin_line_ids = fields.One2many('res.kin', 'member_id')
    document = fields.Binary(attachment=True)

    biometric = fields.Boolean()
    biometric_image = fields.Binary('Thumb Print', attachment=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string='Gender')
    dob = fields.Date('Date of Birth ')

    file_line_ids = fields.One2many('file', 'membership_id', string='File Lines', ondelete='restrict')
    realestate_file_line_ids = fields.One2many('file', 'membership_id', string='Real Estate Files', readonly=True,
        domain=[('project_type', 'in', ['housing_society', False])])
    project_file_line_ids = fields.One2many('file', 'membership_id', string='Building Files', readonly=True,
        domain=[('project_type', '=', 'skyscraper')])
    authorised_representative_ids = fields.One2many('authorised.representative', 'member_id', ondelete='cascade')
    authorized_user_ids = fields.One2many('partner.authorized.user', 'member_id', ondelete='cascade')

    company_ids = fields.Many2many('res.company', string='Allowed Companies',
                                   default=lambda self: self.env.user.company_id)
    member_company_id = fields.Many2one('res.company', string='Member Companies',
                                        compute='_compute_member_company_ids', store=True)
    ownership_percentage = fields.Boolean(default=lambda self: self.env.company.ownership_percentage, store=False)

    # Assigned User
    assigned_user_ids = fields.Many2one('res.users')

    def generate_authorized_sub_users(self):
        for rec in self:
            group_portal = self.env.ref('base.group_portal')

            if rec.authorized_user_ids:
                for person in rec.authorized_user_ids.filtered(lambda x: not x.user_id):
                    user = self.env['res.users'].with_context(no_reset_password=True).create({
                        'name': person.name,
                        'email': person.login,
                        'login': person.login,
                        'company_id': self.env.company.id,
                        'company_ids': [(6, 0, [self.env.company.id])],
                        'active': True,
                        'is_sub_user': True,
                        'groups_id': [(4, group_portal.id)]
                    })
                    person.user_id = user.id

    def get_all_users(self):
        users = []
        if self.env.company and self.env.company.parent_id:
            users = self.sudo().env['res.users'].with_context(company_id=self.env.company.parent_id).search([]).ids
        elif self.env.company and not self.env.company.parent_id:
            users = self.sudo().env['res.users'].with_context(company_id=self.env.company).search([]).ids
        return [('id', 'in', users)]

    @api.depends('company_id')
    def _compute_member_company_ids(self):
        for rec in self:
            rec.member_company_id = rec.company_id if rec.company_id else False

    def scan_image(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/dwt/scan/%s/%s/%s/%s' % (
                self._name,
                self.id,
                self.env.ref('real_estate.action_members').id,
                self._context.get('target_field'),
            ),
        }

    def _search_tracking_id(self, operator, value):
        return [('id', '=', [rec.id for rec in self.search([]) if
                             rec.tracking_id and value in rec.tracking_id][0])]

    @api.onchange('company_type')
    def onchange_company_type(self):
        if self.company_type == 'company':
            self.is_company = True

    @api.onchange('city_id')
    def onchange_city(self):
        self.state_id = self.city_id.state_id.id
        self.zip = self.city_id.zip
        self.country_id = self.state_id.country_id.id

    @api.onchange('corespondence_city_id')
    def onchange_correspondence_city(self):
        self.corespondence_state_id = self.corespondence_city_id.state_id.id
        self.corespondence_zip = self.corespondence_city_id.zip
        self.corespondence_country_id = self.corespondence_state_id.country_id.id

    @api.depends('file_line_ids')
    def _compute_tracking_id(self):
        for rec in self:
            rec.tracking_id = rec.file_line_ids.mapped('tracking_id')

    def toggle_active(self):
        if self.file_line_ids:
            raise ValidationError("You can not deactivate a member who have files attached")
        res = super(ResMember, self).toggle_active()
        for rec in self:
            if rec.partner_id:
                rec.partner_id.sudo().active = rec.active
        return res

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Member Invoices'),
            'res_model': 'account.move',
            'domain': [('partner_id', '=', self.partner_id.id), ('move_type', '=', 'out_invoice')],
            'context': {
                'current_view': 'realestate'
            }
        }

    def open_file(self):
        obj = self._context.get('current_view')
        context = {"from_member": True, 'default_membership_id': self.id, 'current_view': 'realestate',
                   'default_project_type': 'housing_society'}
        if obj == 'building' or self.project_type == 'skyscraper':
            tree_view = (self.env.ref('land_development.file_tree').id, 'list')
            form_view = (self.env.ref('land_development.file_form').id, 'form')
            if self.crm_id and self.no_of_files == 0:
                plan = self.env['propose.plan'].search(
                    [('crm_id', '=', self.crm_id.id)])
                if self.token_id.payment_type == 'lump_sum':
                    total_sale_amount = self.token_id.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                member = self.env['res.member'].search([('crm_id', '=', self.crm_id.id)])
                if member or self.token_id.is_existing == True and self.token_id.partner_id:
                    vals = {
                        "from_member": True,
                        'membership_name': self.name,
                        'membership_id': self.id,
                        'user_id': self.user_id.id or self.crm_id.user_id.id,
                        'project_type': 'skyscraper',
                        'token_id': self.token_id.id,
                        'crm_id': self.crm_id.id,
                        'society_id': self.token_id.society_id.id,
                        'phase_id': self.token_id.token_line_ids.phase_id.id,
                        'sector_id': self.token_id.token_line_ids.sector_id.id,
                        'street_id': self.token_id.token_line_ids.street_id.id,
                        'category_id': self.token_id.token_line_ids.category_id.id,
                        'unit_category_type_id': self.token_id.token_line_ids.unit_category_type_id.id,
                        'size_id': self.token_id.token_line_ids.size_id.id,
                        'unit_class_id': self.token_id.token_line_ids.unit_class_id.id,
                        'inventory_id': self.token_id.token_line_ids.inventory_id.id,
                        'price_list_id': plan.price_list_id.id,
                        'payment_type': self.token_id.payment_type if self.token_id.payment_type else 'installments',
                        'booking_date': plan.booking_date if plan else fields.Date.today(),
                        'add_custom_value': plan.add_custom_value if plan else False,
                        'plan_type': plan.plan_type if plan else 'custom',
                        'predefine_plan_id': plan.predefine_plan_id.id if plan else False,
                        'interval_id': plan.interval_id.id if plan else False,
                        'starting_date': plan.starting_date if plan else False,
                        'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                   'approved': True if plan.include_in_plan == 'yes' else False}) for
                                           rec in plan.factor_id] if plan else False,
                        'discount_type': plan.discount_type if plan else 0,
                        'discount_amount': plan.discount_amount if plan else 0,
                        'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                        'sale_amount': plan.amount if plan else total_sale_amount,
                        'ttl_sale_amount': total_sale_amount,
                        'net_sale_amount': total_sale_amount,
                        'initial_payment': plan.initial_payment if plan else 0,
                        'balloting_amount': plan.final_payment if plan else 0,
                        'total_installment': plan.total_installment if plan else 0,
                        'create_manually': plan.create_manually,
                        'manual_installment_plan_ids': [(0, 0,
                                                         {'product_id': x.product_id.id,
                                                          'date': x.date,
                                                          'percentage': x.percentage,
                                                          'amount_manual': x.amount_manual,
                                                          'line_calculated': x.line_calculated,
                                                          }) for x in plan.manual_installment_plan_ids if
                                                        plan.create_manually],
                        'balance_amount': plan.balance_amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.balance_amount
                    }
                    res_ids = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).ids
                    if len(res_ids) < 1 and self.token_id.payment_type == 'installments':
                        file = self.env['file'].create(vals)
                        file.create_installment_plan()

                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id,
                        }
                    elif len(res_ids) < 1 and self.token_id.payment_type == 'lump_sum':
                        file = self.env['file'].create(vals)
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }

            elif self.token_id and self.no_of_files == 0:
                plan = self.env['propose.plan'].search(
                    [('token_id', '=', self.token_id.id)])
                if self.token_id.payment_type == 'lump_sum':
                    total_sale_amount = self.token_id.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                member = self.env['res.member'].search([('token_id', '=', self.token_id.id)])
                context = {"from_member": True, 'default_membership_id': self.id, 'default_user_id': self.user_id.id,
                           'current_view': 'buildings', 'default_project_type': 'skyscraper'}

                if member or self.token_id.is_existing == True and self.token_id.partner_id:
                    vals = {
                        "from_member": True,
                        'membership_name': self.name,
                        'membership_id': self.id,
                        'user_id': self.user_id.id,
                        'project_type': 'skyscraper',
                        'token_id': self.token_id.id,
                        'crm_id': self.crm_id.id,
                        'society_id': self.token_id.society_id.id,
                        'phase_id': self.token_id.token_line_ids.phase_id.id,
                        'sector_id': self.token_id.token_line_ids.sector_id.id,
                        'street_id': self.token_id.token_line_ids.street_id.id,
                        'category_id': self.token_id.token_line_ids.category_id.id,
                        'unit_category_type_id': self.token_id.token_line_ids.unit_category_type_id.id,
                        'size_id': self.token_id.token_line_ids.size_id.id,
                        'unit_class_id': self.token_id.token_line_ids.unit_class_id.id,
                        'inventory_id': self.token_id.token_line_ids.inventory_id.id,
                        'payment_type': self.token_id.payment_type if self.token_id.payment_type else 'installments',
                        'booking_date': plan.booking_date if plan else fields.Date.today(),
                        'add_custom_value': plan.add_custom_value if plan else False,
                        'plan_type': plan.plan_type if plan else 'custom',
                        'predefine_plan_id': plan.predefine_plan_id.id if plan else False,
                        'interval_id': plan.interval_id.id if plan else False,
                        'starting_date': plan.starting_date if plan else False,
                        'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                   'approved': True if plan.include_in_plan == 'yes' else False}) for
                                           rec in plan.factor_id] if plan else False,
                        'discount_type': plan.discount_type if plan else 0,
                        'discount_amount': plan.discount_amount if plan else 0,
                        'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                        'sale_amount': plan.amount if plan else total_sale_amount,
                        'ttl_sale_amount': total_sale_amount,
                        'net_sale_amount': total_sale_amount,
                        'initial_payment': plan.initial_payment if plan else 0,
                        'balloting_amount': plan.final_payment if plan else 0,
                        'total_installment': plan.total_installment if plan else 0,
                        'create_manually': plan.create_manually,
                        'manual_installment_plan_ids': [(0, 0,
                                                         {'product_id': x.product_id.id,
                                                          'date': x.date,
                                                          'percentage': x.percentage,
                                                          'amount_manual': x.amount_manual,
                                                          'line_calculated': x.line_calculated,
                                                          }) for x in plan.manual_installment_plan_ids if
                                                        plan.create_manually],
                        'balance_amount': plan.balance_amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.balance_amount
                    }
                    res_ids = self.env['file'].search([('token_id', '=', self.token_id.id)]).ids
                    if len(res_ids) < 1 and self.token_id.payment_type == 'installments':
                        file = self.env['file'].create(vals)
                        file.create_installment_plan()

                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }
                    elif len(res_ids) < 1 and self.token_id.payment_type == 'lump_sum':
                        file = self.env['file'].create(vals)
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }
            else:
                context = {"from_member": True,
                           'default_membership_id': self.id,
                           'default_user_id': self.user_id.id,
                           'default_kin_name': self.kin_name,
                           'default_kin_mobile': self.kin_mobile,
                           'default_kin_cnic': self.kin_cnic,
                           'default_kin_member_relation': self.kin_member_relation,
                           'default_kin_line_ids': [(0, 0,
                                                     {'name': self.kin_name,
                                                      'cnic': self.kin_cnic,
                                                      'mobile': self.kin_mobile,
                                                      'relation_with_member': self.kin_member_relation,
                                                      'relation_name': self.other_relation,
                                                      'start_date': fields.Date.today(),
                                                      })],
                           'current_view': 'buildings',
                           'default_project_type': 'skyscraper'}
                return {
                    'type': 'ir.actions.act_window',
                    'views': [tree_view, form_view],
                    'view_mode': 'list,form',
                    'name': _('File'),
                    'res_model': 'file',
                    'domain': [('membership_id', '=', self.id)],
                    'context': context,
                }

        elif obj == 'realestate' or self.project_type == 'housing_society':
            tree_view = (self.env.ref('real_estate.file_tree').id, 'list')
            form_view = (self.env.ref('real_estate.file_form').id, 'form')
            if self.crm_id and self.no_of_files == 0:
                plan = self.env['propose.plan'].search(
                    [('crm_id', '=', self.crm_id.id)])
                if self.token_id.payment_type == 'lump_sum':
                    total_sale_amount = self.token_id.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                member = self.env['res.member'].search([('crm_id', '=', self.crm_id.id)])
                if member or self.token_id.is_existing == True and self.token_id.partner_id:
                    vals = {
                        "from_member": True,
                        'membership_name': self.name,
                        'membership_id': self.id,
                        'user_id': self.user_id.id or self.crm_id.user_id.id,
                        'project_type': 'housing_society',
                        'token_id': self.token_id.id,
                        'crm_id': self.crm_id.id,
                        'society_id': self.token_id.society_id.id,
                        'phase_id': self.token_id.token_line_ids.phase_id.id,
                        'sector_id': self.token_id.token_line_ids.sector_id.id,
                        'street_id': self.token_id.token_line_ids.street_id.id,
                        'category_id': self.token_id.token_line_ids.category_id.id,
                        'unit_category_type_id': self.token_id.token_line_ids.unit_category_type_id.id,
                        'size_id': self.token_id.token_line_ids.size_id.id,
                        'unit_class_id': self.token_id.token_line_ids.unit_class_id.id,
                        'inventory_id': self.token_id.token_line_ids.inventory_id.id,
                        'price_list_id': plan.price_list_id.id,
                        'payment_type': self.token_id.payment_type if self.token_id.payment_type else 'installments',
                        'booking_date': plan.booking_date if plan else fields.Date.today(),
                        'add_custom_value': plan.add_custom_value if plan else False,
                        'plan_type': plan.plan_type if plan else 'custom',
                        'predefine_plan_id': plan.predefine_plan_id.id if plan else False,
                        'interval_id': plan.interval_id.id if plan else False,
                        'starting_date': plan.starting_date if plan else False,
                        'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                   'approved': True if plan.include_in_plan == 'yes' else False}) for
                                           rec in plan.factor_id] if plan else False,
                        'discount_type': plan.discount_type if plan else 0,
                        'discount_amount': plan.discount_amount if plan else 0,
                        'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                        'sale_amount': plan.amount if plan else total_sale_amount,
                        'ttl_sale_amount': total_sale_amount,
                        'net_sale_amount': total_sale_amount,
                        'initial_payment': plan.initial_payment if plan else 0,
                        'balloting_amount': plan.final_payment if plan else 0,
                        'total_installment': plan.total_installment if plan else 0,
                        'create_manually': plan.create_manually,
                        'manual_installment_plan_ids': [(0, 0,
                                                         {'product_id': x.product_id.id,
                                                          'date': x.date,
                                                          'percentage': x.percentage,
                                                          'amount_manual': x.amount_manual,
                                                          'line_calculated': x.line_calculated,
                                                          }) for x in plan.manual_installment_plan_ids if
                                                        plan.create_manually],
                        'balance_amount': plan.balance_amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.balance_amount
                    }
                    res_ids = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).ids
                    if len(res_ids) < 1 and self.token_id.payment_type == 'installments':
                        file = self.env['file'].create(vals)
                        file.create_installment_plan()

                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id,
                        }
                    elif len(res_ids) < 1 and self.token_id.payment_type == 'lump_sum':
                        file = self.env['file'].create(vals)
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }
                    else:
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id,
                        }

            elif self.token_id and self.no_of_files == 0:
                plan = self.env['propose.plan'].search(
                    [('token_id', '=', self.token_id.id)])

                if self.token_id.payment_type == 'lump_sum':
                    total_sale_amount = self.token_id.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                member = self.env['res.member'].search([('token_id', '=', self.token_id.id)])
                context = {"from_member": True, 'default_membership_id': self.id, 'default_user_id': self.user_id.id,
                           'current_view': 'realestate', 'default_project_type': 'housing_society'}

                if member or self.token_id.is_existing == True and self.token_id.partner_id:
                    vals = {
                        "from_member": True,
                        'membership_name': self.name,
                        'membership_id': self.id,
                        'user_id': self.user_id.id,
                        'project_type': 'housing_society',
                        'token_id': self.token_id.id,
                        'crm_id': self.crm_id.id,
                        'society_id': self.token_id.society_id.id,
                        'phase_id': self.token_id.token_line_ids.phase_id.id,
                        'sector_id': self.token_id.token_line_ids.sector_id.id,
                        'street_id': self.token_id.token_line_ids.street_id.id,
                        'category_id': self.token_id.token_line_ids.category_id.id,
                        'unit_category_type_id': self.token_id.token_line_ids.unit_category_type_id.id,
                        'size_id': self.token_id.token_line_ids.size_id.id,
                        'unit_class_id': self.token_id.token_line_ids.unit_class_id.id,
                        'inventory_id': self.token_id.token_line_ids.inventory_id.id,
                        'payment_type': self.token_id.payment_type if self.token_id.payment_type else 'installments',
                        'booking_date': plan.booking_date if plan else fields.Date.today(),
                        'add_custom_value': plan.add_custom_value if plan else False,
                        'plan_type': plan.plan_type if plan else 'custom',
                        'predefine_plan_id': plan.predefine_plan_id.id if plan else False,
                        'interval_id': plan.interval_id.id if plan else False,
                        'starting_date': plan.starting_date if plan else False,
                        'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                   'approved': True if plan.include_in_plan == 'yes' else False}) for
                                           rec in plan.factor_id] if plan else False,
                        'discount_type': plan.discount_type if plan else 0,
                        'discount_amount': plan.discount_amount if plan else 0,
                        'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                        'sale_amount': plan.amount if plan else total_sale_amount,
                        'ttl_sale_amount': total_sale_amount,
                        'net_sale_amount': total_sale_amount,
                        'initial_payment': plan.initial_payment if plan else 0,
                        'balloting_amount': plan.final_payment if plan else 0,
                        'total_installment': plan.total_installment if plan else 0,
                        'create_manually': plan.create_manually,
                        'manual_installment_plan_ids': [(0, 0,
                                                         {'product_id': x.product_id.id,
                                                          'date': x.date,
                                                          'percentage': x.percentage,
                                                          'amount_manual': x.amount_manual,
                                                          'line_calculated': x.line_calculated,
                                                          }) for x in plan.manual_installment_plan_ids if
                                                        plan.create_manually],
                        'balance_amount': plan.balance_amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.balance_amount
                    }
                    res_ids = self.env['file'].search([('token_id', '=', self.token_id.id)]).ids
                    if len(res_ids) < 1 and self.token_id.payment_type == 'installments':
                        file = self.env['file'].create(vals)
                        file.create_installment_plan()
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }
                    elif len(res_ids) < 1 and self.token_id.payment_type == 'lump_sum':
                        file = self.env['file'].create(vals)
                        return {
                            'type': 'ir.actions.act_window',
                            'views': [tree_view, form_view],
                            'view_mode': 'list,form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.id)],
                            'context': context,
                            'res_id': self.env['file'].search([('token_id', '=', self.token_id.id)]).id,
                        }

            else:
                context = {"from_member": True,
                           'default_membership_id': self.id,
                           'default_user_id': self.user_id.id,
                           'default_kin_name': self.kin_name,
                           'default_kin_mobile': self.kin_mobile,
                           'default_kin_cnic': self.kin_cnic,
                           'default_kin_member_relation': self.kin_member_relation,
                           'default_kin_line_ids': [(0, 0,
                                                     {'name': self.kin_name,
                                                      'cnic': self.kin_cnic,
                                                      'mobile': self.kin_mobile,
                                                      'relation_with_member': self.kin_member_relation,
                                                      'relation_name': self.other_relation,
                                                      'start_date': fields.Date.today(),
                                                      })],
                           'current_view': 'realestate',
                           'default_project_type': 'housing_society'}
                return {
                    'type': 'ir.actions.act_window',
                    'views': [tree_view, form_view],
                    'view_mode': 'list,form',
                    'name': _('File'),
                    'res_model': 'file',
                    'domain': [('membership_id', '=', self.id)],
                    'context': context,
                }
        else:
            raise ValidationError("There is some issue, Please contact system administrator.")

    def _compute_no_of_invoices(self):
        for rec in self:
            rec.no_of_invoices = self.env['account.move'].search_count([
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice')]) if rec.partner_id else 0

    def _compute_no_of_files(self):
        for rec in self:
            rec.no_of_files = len(self.env['file'].search([('membership_id', '=', rec.id)]))

    def _compute_no_of_realestate_files(self):
        for rec in self:
            rec.no_of_realestate_files = self.env['file'].search_count([
                ('membership_id', '=', rec.id),
                ('project_type', 'in', ['housing_society', False]),
            ])

    def _compute_no_of_project_files(self):
        for rec in self:
            rec.no_of_project_files = self.env['file'].search_count([
                ('membership_id', '=', rec.id),
                ('project_type', '=', 'skyscraper'),
            ])

    def open_realestate_files(self):
        tree_view = (self.env.ref('real_estate.file_tree').id, 'list')
        form_view = (self.env.ref('real_estate.file_form').id, 'form')
        return {
            'type': 'ir.actions.act_window',
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'name': _('Real Estate Files'),
            'res_model': 'file',
            'domain': [('membership_id', '=', self.id), ('project_type', 'in', ['housing_society', False])],
            'context': {
                'default_membership_id': self.id,
                'default_project_type': 'housing_society',
                'current_view': 'realestate',
            },
        }

    def open_project_files(self):
        tree_view = (self.env.ref('land_development.file_tree').id, 'list')
        form_view = (self.env.ref('land_development.file_form').id, 'form')
        return {
            'type': 'ir.actions.act_window',
            'views': [tree_view, form_view],
            'view_mode': 'list,form',
            'name': _('Building Files'),
            'res_model': 'file',
            'domain': [('membership_id', '=', self.id), ('project_type', '=', 'skyscraper')],
            'context': {
                'default_membership_id': self.id,
                'default_project_type': 'skyscraper',
                'current_view': 'building',
            },
        }

    @api.constrains('cnic', 'email', 'mobile', 'vat')
    def _check_something(self):
        res = self.env['res.member']

        if self.cnic and res.search_count([('cnic', '=', self.cnic), ('company_type', '=', self.company_type), ('company_id', '=', self.company_id.id)]) > 1:
            raise ValidationError("CNIC No should be unique: %s" % self.cnic)

        if self.email and res.search_count([('email', '=', self.email)]) > 1:
            raise ValidationError("Email should be unique: %s" % self.email)

    def copy(self, default=None):
        default = dict(default or {})
        newo = {'cnic': '', 'email': '', 'vat': '', 'mobile': ''}
        finala = {**default, **newo}
        return super(ResMember, self).copy(finala)

    def _shadow_partner_vals(self):
        self.ensure_one()
        return {
            'name': self.name,
            'is_company': self.company_type == 'company',
            'company_type': 'company' if self.company_type == 'company' else 'person',
            'email': self.email,
            'phone': self.phone,
            'street': self.street,
            'street2': self.street2,
            'city': self.city,
            'zip': self.zip,
            'state_id': self.state_id.id,
            'country_id': self.country_id.id,
            'vat': self.vat,
            'ref': self.ref,
            'company_id': self.company_id.id,
            'customer_rank': 1,
            'active': self.active,
        }

    def _create_or_get_shadow_partner(self):
        self.ensure_one()
        return self.env['res.partner'].sudo().create(self._shadow_partner_vals())

    _SHADOW_SYNC_FIELDS = {
        'name', 'email', 'phone', 'street', 'street2',
        'city', 'zip', 'state_id', 'country_id', 'company_id',
        'vat', 'ref', 'company_type', 'active',
    }

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('ref', _('New')) == _('New'):
                if val.get('is_investor'):
                    val['ref'] = self.env['ir.sequence'].next_by_code("investors.sequence") or _('New')
                else:
                    val['ref'] = self.env['ir.sequence'].next_by_code("res.partner") or _('New')

            if self._context.get('active_model', True) and self._context.get('active_model') != 'res.company':
                val['company_id'] = self.env.company.id

            if val.get('kin_name', False) and val.get('kin_member_relation', False):
                val['kin_line_ids'] = [(0, 0,
                                         {'name': val.get('kin_name'),
                                          'cnic': val.get('kin_cnic'),
                                          'mobile': val.get('kin_mobile'),
                                          'relation_with_member': val.get('kin_member_relation'),
                                          'relation_name': val.get('other_relation'),
                                          'start_date': fields.Date.today(),
                                          })]

        records = super(ResMember, self).create(vals_list)

        for record in records:
            if not record.partner_id:
                record.partner_id = record._create_or_get_shadow_partner()

        for record in records:
            if record.company_type == 'aop' and not record.cnic_line_ids:
                raise ValidationError(_("Please add information in Details tab."))

            if self._context.get('active_model') and self._context.get('active_model') == "transfer.application":
                transfer_app = self.env['transfer.application'].browse(self._context.get('active_id'))
                transfer_app.transferee_existing_partner = 'yes'
                transfer_app.transferee_partner_id = record.id
                transfer_app.transferee_name = record.name

            if self._context.get('active_model') and self._context.get('active_model') == "investor.file":
                investor_file = self.env['investor.file'].browse(self._context.get('active_id'))
                investor_file.is_transferee_partner = True
                investor_file.transferee_partner_id = record.id
                investor_file.transferee_name = record.name

            if self._context.get('active_model') and self._context.get('active_model') == "unit.swapping.request":
                unit_swapping_request = self.env['unit.swapping.request'].browse(self._context.get('active_id'))
                unit_swapping_request.is_transferee_partner = True
                unit_swapping_request.transferee_partner_id = record.id

        return records

    def write(self, vals):
        res = super(ResMember, self).write(vals)
        if self.company_type == 'aop' and not self.cnic_line_ids:
            raise ValidationError(_("Please add information in Details tab."))
        if self._SHADOW_SYNC_FIELDS & vals.keys():
            for rec in self:
                if rec.partner_id:
                    rec.partner_id.sudo().write(rec._shadow_partner_vals())
                else:
                    rec.partner_id = rec._create_or_get_shadow_partner()
        return res

    @api.depends('name', 'ref')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.ref and record.ref != 'New':
                name = "%s:%s" % (record.ref, record.name)
            result.append((record.id, name))
        return result

    @api.onchange('is_same')
    def _copy_address(self):
        if self.is_same:
            self.corespondence_street, self.corespondence_street2, self.corespondence_city_id = self.street, self.street2, self.city_id.id
            self.corespondence_state_id, self.corespondence_zip, self.corespondence_country_id = self.state_id.id, self.zip, self.country_id.id
        if not self.is_same:
            self.corespondence_street = self.corespondence_street2 = self.corespondence_zip = " "
            self.corespondence_city_id = self.corespondence_state_id = self.corespondence_country_id = False

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(ResMember, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                       submenu=submenu)
        is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')
        is_user2 = self.env.user.has_group('real_estate.group_can_create_record')

        if is_user:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='real_estate_member']")
                doc.set('edit', 'true')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)

            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'true')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)

            if view_type == 'kanban':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'true')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)
        elif is_user2:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)

            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)

            if view_type == 'kanban':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)
        else:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

            if view_type == 'kanban':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='real_estate_member']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

        return res

    def unlink(self):
        is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')
        is_user2 = self.env.user.has_group('real_estate.group_can_create_record')
        if not is_user:
            raise UserError(_("You are not allowed to delete record"))
        if not is_user2:
            raise UserError(_("You are not allowed to delete record"))
        partners = self.mapped('partner_id')
        res = super(ResMember, self).unlink()
        partners.sudo().write({'active': False})
        return res

    @api.model
    def _from_login_partner(self):
        """Resolve the res.member behind the currently logged-in portal user's shadow partner."""
        return self.search([('partner_id', '=', self.env.user.partner_id.id)], limit=1)

    @api.model
    def create_authorised_person_request(self, **kwargs):
        person_data = kwargs['person_data']
        partner = self._from_login_partner()

        investment_request = self.env['unit.swapping.request'].sudo().search([('investor_id', '=', partner.id),
                                                                              ('transaction_type', '=',
                                                                               'authorised_person'),
                                                                              ('state', '=', 'draft')])
        if investment_request:
            raise ValidationError('Request already created against this investor and is in draft state.')

        investment_request = investment_request.create({
            'from_app': True,
            'project_type': partner.project_type,
            'transaction_type': kwargs['transaction_type'],
            'applicable_on': 'investment',
            'investor_id': partner.id,
            'kin_name': person_data[0].get('name'),
            'kin_cnic': person_data[0].get('cnic'),
            'kin_mobile': person_data[0].get('mobile'),
            'street': person_data[0].get('street'),
            'city': person_data[0].get('city'),
            'province': person_data[0].get('state'),
            'country': person_data[0].get('country')
        })
        if investment_request:
            return json.dumps({'success': "Request successfully created.", 'status': 200})
        else:
            return json.dumps({'error': "Failed to create request.", 'status': 400})

    @api.model
    def edit_authorised_person(self, **kwargs):
        person_data = kwargs['person_data']
        partner = self._from_login_partner()

        investment_request = self.env['unit.swapping.request'].sudo().search([('investor_id', '=', partner.id),
                                                                              ('transaction_type', '=',
                                                                               'authorised_person'),
                                                                              ('state', '=', 'draft')])
        if investment_request:
            raise ValidationError('Request already created against this investor and is in draft state.')

        investment_request = investment_request.create({
            'from_app': True,
            'project_type': partner.project_type,
            'transaction_type': kwargs['transaction_type'],
            'applicable_on': 'investment',
            'update_existing_person': person_data[0].get('update_existing_person'),
            'investor_id': partner.id,
            'kin_mobile': person_data[0].get('mobile'),
            'street': person_data[0].get('street'),
            'city': person_data[0].get('city'),
            'province': person_data[0].get('state'),
            'country': person_data[0].get('country')
        })
        if investment_request:
            return json.dumps({'success': "Request successfully created.", 'status': 200})
        else:
            return json.dumps({'error': "Failed to create request.", 'status': 400})


class AuthorisedRepresentative(models.Model):
    _name = 'authorised.representative'
    _description = "Authorised Representative"

    name = fields.Char()
    mobile = fields.Char()
    cnic = fields.Char()
    document = fields.Binary(attachment=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('expire', 'Expire')
    ])

    # Address Fields
    street = fields.Char()
    city = fields.Char()
    state = fields.Char()
    country = fields.Char()

    member_id = fields.Many2one('res.member', ondelete='cascade')

    @api.constrains('status')
    def check_status(self):
        if self.search_count([('member_id', '=', self.member_id.id), ('status', '=', 'active')]) > 1:
            raise ValidationError('Only one person can be active at a time.')


class AuthorizedUsers(models.Model):
    _name = 'partner.authorized.user'
    _description = "Partner Authorized Users"

    name = fields.Char(string="Name", required=True)
    mobile = fields.Char(string="Mobile")
    cnic = fields.Char(string="CNIC")
    login = fields.Char("User Name", required=True, tracking=True)
    password = fields.Char(required=True, tracking=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('expire', 'Expire')
    ])
    member_id = fields.Many2one('res.member', ondelete='cascade')
    user_id = fields.Many2one('res.users')

