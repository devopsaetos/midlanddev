# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from datetime import date


class TokenMoney(models.Model):
    _name = "token.money"
    _description = 'Token Money'
    _rec_name = 'serial_number'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    serial_number = fields.Char(
        'Token Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    state = fields.Selection([
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('adjusted', 'Adjusted'),
        ('refund', 'Refund'),
        ('cancel', 'Cancel'),
    ], default='open', tracking=True)
    token_generated = fields.Boolean()
    party_type = fields.Selection([
        ('member', 'Member'),
        ('investor', 'Investor'),
    ], default='member', required=True, tracking=True, string='Party Type')
    investor_id = fields.Many2one('res.investor', string='Investor', tracking=True)
    investment_id = fields.Many2one('investment', string='Investment No', tracking=True)
    no_of_units = fields.Integer(related='investment_id.no_of_units', string='No of Units')

    @api.onchange('investment_id')
    def _onchange_investment_id(self):
        if self.investment_id:
            if self.investment_id.partner_id:
                self.investor_id = self.investment_id.partner_id
            if self.investment_id.society_id:
                self.society_id = self.investment_id.society_id
            # total price of all the deal's units flows into the token
            self.ttl_sale_amount = self.investment_id.total_amount
    is_existing = fields.Boolean('Existing Member?')
    change_member = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], default='no', help="Set this option to yes if you want to create a new member.", tracking=True)
    contact_name = fields.Char('Name ', related='partner_id.name', store=True, readonly=False)
    name = fields.Char(related='partner_id.name', store=True, tracking=True)
    partner_id = fields.Many2one('res.member', string='Member Name', tracking=True)
    email = fields.Char('Email', store=True, related='partner_id.email', readonly=False, tracking=True)
    cnic = fields.Char('CNIC', store=True, related='partner_id.cnic', readonly=False, tracking=True)
    cnic_line_ids = fields.One2many('res.cnic', 'token_id', store=True, related='partner_id.cnic_line_ids')

    phone_no = fields.Char('Phone Number', store=True, related='partner_id.mobile', readonly=False, tracking=True)
    cp_phone_no = fields.Char('Phone No', store=True, related='partner_id.cp_mobile', readonly=False)
    society_id = fields.Many2one('society', required=True, string='Society', domain=[('is_society', '=', True)])
    company_type = fields.Selection([('person', 'Individual'),
                                     ('company', 'Company'),
                                     ('aop', 'Joint Owner')], related='partner_id.company_type', store=True,
                                    readonly=False, tracking=True)
    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ], related='society_id.project_type', store=True)
    token_line_ids = fields.One2many('token.money.line', 'token_id')
    token_fees = fields.Float(string="Token Money", digits='Product Price', required=True)
    date = fields.Date(required=True, tracking=True)
    token_date = fields.Date(tracking=True)
    remarks = fields.Text(tracking=True)
    crm_id = fields.Many2one('crm.lead')
    token_paid = fields.Boolean(default=False)
    from_crm = fields.Boolean()
    plan_locked = fields.Boolean()
    journal_id = fields.Many2one('account.journal', 'Payment Journal', domain=[('type', 'in', ('cash', 'bank'))], tracking=True)
    cheque_name = fields.Char('Cheque Name')
    cheque_no = fields.Char('Cheque No')
    bank_ref = fields.Char('Bank Reference')
    validity_expire = fields.Boolean(default=False)
    create_open_file = fields.Boolean(default=False)
    open_file_amount_received = fields.Boolean(default=False)
    open_files_created = fields.Boolean()
    payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')
    ], string='Payment Type', tracking=True)
    ttl_sale_amount = fields.Float(
        'Total Sale Amount', store=True, tracking=True
    )
    balance_amount = fields.Float('Balance Amount', store=True, compute='_compute_balance_amount', readonly=False)
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')
    payment_date = fields.Date()

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(self.env['midland.invoice'].search([('token_id', '=', self.id)]))

    @api.depends('ttl_sale_amount', 'token_fees')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = rec.ttl_sale_amount - rec.token_fees

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'name': _('Token Invoices'),
            'res_model': 'midland.invoice',
            'domain': [('token_id', '=', self.id)],
            'context': {'current_view': 'realestate'},
        }



    @api.constrains('date')
    def _check_date_validity(self):
        if self.date < date.today():
            raise ValidationError(_("Please give a valid date;)"))

    @api.onchange('is_existing')
    def onchange_is_existing(self):
        # on change of existing member we have to null following fields
        pass
        # self.company_type = ''
        # self.cnic = ''
        # self.phone_no = ''
        # self.cp_phone_no = ''
        # self.partner_id = False
        # self.contact_name = ''

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('serial_number', _('New')) == _('New'):
                val['serial_number'] = self.env['ir.sequence'].next_by_code("token.money") or _('New')

        res = super(TokenMoney, self).create(vals_list)

        for rec in res:
            if rec.company_type == 'aop' and not rec.line_ids:
                raise ValidationError(_("Please add information in Details tab."))

            if rec.party_type == 'member' and not rec.is_existing:
                partner = rec.env['res.member'].create({
                    'name': rec.contact_name,
                    'company_type': rec.company_type,
                    'mobile': rec.phone_no,
                    'cp_mobile': rec.cp_phone_no,
                    'cnic': rec.cnic,
                    'email': rec.email,
                    'city': False,
                    # 'token_id': rec.id
                })
                rec.partner_id = partner.id

        return res

    def write(self, vals):
        res = super(TokenMoney, self).write(vals)
        # investor tokens carry no unit lines; units live on the Deal
        if self.party_type != 'investor' and not self.token_line_ids:
            raise ValidationError(_("You can not save record before select any plot."))
        # if self.company_type == 'aop' and not self.cnic_line_ids:
        #     raise ValidationError(_("Please add information in Details tab."))
        return res

    def _token_party_vals(self):
        """member_id/partner_id pair to merge into a midland.invoice or midland.payment
        create() dict, depending on whether this token is for a Member or an Investor.
        For investors there's no dedicated link field on midland.invoice/midland.payment,
        so partner_id is set directly (bypassing the member_id-driven compute) - the same
        pattern file_financials/models/investment.py already uses for investor payments."""
        self.ensure_one()
        if self.party_type == 'investor':
            if not self.investor_id:
                raise ValidationError(_("Please select an Investor first."))
            return {'partner_id': self.investor_id.partner_id.id}
        if not self.partner_id:
            raise ValidationError(_("Please select a Member first."))
        return {'member_id': self.partner_id.id}

    def _token_accounting_partner_id(self):
        """The res.partner id behind this token, whichever party_type it is - for spots
        (like cancel_token()'s manual journal entry) that need a plain partner_id rather
        than the member_id/partner_id pair midland.invoice/midland.payment expect."""
        self.ensure_one()
        if self.party_type == 'investor':
            return self.investor_id.partner_id.id
        return self.partner_id.partner_id.id

    def create_token_fees(self):
        if self.token_fees <= 0:
            return ''
        # investor tokens are an advance against a Deal; units and the
        # installment plan live on the Deal, so those checks are member-only
        if self.party_type != 'investor':
            if not self.token_line_ids:
                raise ValidationError(_("You can not Generate token before select any Criteria."))

            if self.company_type == 'aop' and not self.cnic_line_ids:
                raise ValidationError(_("Please add information in Details tab."))

            plan = self.env['propose.plan'].search([('crm_id', '=', self.crm_id.id)])

            if plan and plan.state == 'draft':
                raise ValidationError(_("Installment plan must be locked before generating token."))

            # if not self.plan_locked and self.payment_type == 'installments':
            if not plan and self.payment_type == 'installments':
                raise ValidationError(_("You can not Generate token before create Installment Plan"))
        token = self.env.ref('real_estate.token_money')
        company = self.env.company
        if self.token_fees:
            invoice_vals = {
                'company_id': company.id,
                'crm_id': self.crm_id.id,
                'token_id': self.id,
                'invoice_date': self.token_date if self.token_date else fields.Date.today(),
                'property_invoice_type': 'token',
                'invoice_line_ids': [(0, 0, {
                    'product_id': token.id,
                    'name': token.name,
                    'account_id': token.property_account_income_id.id or False,
                    'quantity': 1.0,
                    'price_unit': self.token_fees,
                })]
            }
            invoice_vals.update(self._token_party_vals())
            invoice = self.env['midland.invoice'].create(invoice_vals)
            invoice.action_post()

            payment_type = self.env.company.payment_type
            if not payment_type:
                raise ValidationError(_("Please Setup Payment Steps Type from Setting first."))
            if payment_type == 'osp':
                payment_vals = {
                    'date': fields.Date.today(),
                    'payment_amount': self.token_fees,
                    'journal_id': self.journal_id.id,
                    'company_id': company.id,
                    'currency_id': company.currency_id.id,
                    'remarks': invoice.name,
                    'invoice_line_ids': [(0, 0, {'invoice_id': invoice.id, 'payment_amount': self.token_fees})],
                }
                payment_vals.update(self._token_party_vals())
                payment = self.env['midland.payment'].create(payment_vals)
                payment.action_confirm()
                self.token_paid = True
                self.state = 'paid'

            for rec in self.token_line_ids:
                rec.inventory_id.state = 'investor' if self.party_type == 'investor' else 'reserved'

            if self.party_type == 'member':
                self.partner_id.project_type = self.project_type
            self.token_generated = True

    def create_open_file_invoice(self):
        if self.balance_amount <= 0:
            raise ValidationError(_("Balance amount must be greater than zero."))
        prod = []
        token = self.env.ref('real_estate.token_money')
        lump_sum = self.env.ref('real_estate.lump_sum_product')
        prod.append((0, 0, {
                    'product_id': lump_sum.id,
                    'name': lump_sum.name,
                    'account_id': lump_sum.property_account_income_id.id or False,
                    'quantity': 1.0,
                    'price_unit': self.balance_amount + self.token_fees,
                }))
        prod.append((0, 0, {
                    'product_id': token.id,
                    'name': token.name,
                    'account_id': token.property_account_income_id.id or False,
                    'quantity': 1.0,
                    'price_unit': -self.token_fees,
                }))
        if self.balance_amount:
            invoice_vals = {
                'company_id': self.env.company.id,
                'crm_id': self.crm_id.id,
                'token_id': self.id,
                'invoice_date': self.token_date if self.token_date else fields.Date.today(),
                'property_invoice_type': 'initial_payment',
                'invoice_line_ids': prod,
            }
            invoice_vals.update(self._token_party_vals())
            invoice = self.env['midland.invoice'].create(invoice_vals)
            invoice.action_post()

            self.state = 'adjusted'
            payment_type = self.env.company.payment_type
            if not payment_type:
                raise ValidationError(_("Please Setup Payment Steps Type from Setting first."))
            if payment_type == 'osp':
                payment_vals = {
                    'date': fields.Date.today(),
                    'payment_amount': self.balance_amount,
                    'journal_id': self.journal_id.id,
                    'company_id': self.env.company.id,
                    'currency_id': self.env.company.currency_id.id,
                    'remarks': invoice.name,
                    'invoice_line_ids': [(0, 0, {'invoice_id': invoice.id, 'payment_amount': self.balance_amount})],
                }
                payment_vals.update(self._token_party_vals())
                payment = self.env['midland.payment'].create(payment_vals)
                payment.action_confirm()
                self.open_file_amount_received = True

    def create_member(self):
        if not self.token_paid:
            raise ValidationError(_("You can not Create Member without paying token fees."))

        if self.change_member == 'yes':
            return {
                'res_model': 'res.member',
                'type': 'ir.actions.act_window',
                'context': {
                    'current_view': 'realestate',
                    # 'default_name': self.contact_name,
                    'default_project_type': 'housing_society' if self.society_id.project_type == 'housing_society' else 'skyscraper',
                    'default_token_id': self.id,
                    'default_user_id': self.crm_id.user_id.id,
                },
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.env['res.member'].search([('token_id','=',self.id)], limit=1).id,
                'view_id': self.env.ref(
                    "real_estate.view_partner_form").id if self.project_type == 'housing_society' else self.env.ref(
                    'land_development.view_partner_form').id,
                'target': 'self'
            }
        else:
            self.partner_id.token_id = self.id
            return {
                'res_model': 'res.member',
                'type': 'ir.actions.act_window',
                'context': {
                    'current_view': 'realestate',
                    'default_name': self.contact_name,
                    'default_project_type': 'housing_society' if self.society_id.project_type == 'housing_society' else 'skyscraper',
                    'default_token_id': self.id,
                    'default_user_id': self.crm_id.user_id.id,
                    'default_street': self.crm_id.street,
                    'default_city_id': self.env['city'].search([('name', '=', self.crm_id.city)]).id,
                    'default_email': self.email,
                    'default_company_type': self.company_type,
                    'default_ttl_sale_amount': self.ttl_sale_amount,
                    'default_payment_type': self.payment_type,
                    'default_mobile': self.phone_no if self.company_type == 'person' else False,
                    'default_cp_mobile': self.cp_phone_no if self.company_type == 'aop' or 'company' else False,
                    'default_cnic': self.cnic,
                    'default_crm_id': self.crm_id.id,
                    'default_cnic_line_ids': [(0, 0,
                                               {'member_name': rec.member_name,
                                                'cnic': rec.cnic,
                                                'cnic_expiry_date': rec.cnic_expiry_date,
                                                'cnic_front': rec.cnic_front,
                                                'cnic_back': rec.cnic_back,
                                                'phone': rec.phone,
                                                'address': rec.address,
                                                'name': rec.name,
                                                'father_spouse_cnic': rec.father_spouse_cnic
                                                }) for rec in self.cnic_line_ids],
                },
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.partner_id.id,
                'view_id': self.env.ref(
                    "real_estate.view_partner_form").id if self.project_type == 'housing_society' else self.env.ref(
                    'land_development.view_partner_form').id,
                'target': 'self'
            }

    def create_file(self):
        if not self.token_paid:
            raise ValidationError(_("You can not Create File without paying token fees."))
        if self.party_type == 'investor':
            raise ValidationError(_(
                "Investor tokens are converted via 'Create Open File', not 'Create File' - "
                "investors get an Investor File, not a Member File."))
        self.state = 'adjusted'

        if self.project_type == 'skyscraper':
            if self.crm_id:
                plan = self.env['propose.plan'].search(
                    [('crm_id', '=', self.crm_id.id)])
                if self.payment_type == 'lump_sum':
                    total_sale_amount = self.ttl_sale_amount
                    balance_amount = self.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                        balance_amount = plan.balance_amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                        balance_amount = plan.balance_amount

                member = self.env['res.member'].search([('crm_id', '=', self.crm_id.id)])
                payment = self.payment_type
                if member or self.is_existing == True and self.partner_id:
                    res_ids = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).ids
                    result = {
                        'name': (_('File')),
                        'res_model': 'file',
                        'type': 'ir.actions.act_window',
                        # 'context': context,
                        'view_type': 'form',
                        'target': 'self'
                    }
                    if len(res_ids) < 1 and self.payment_type == 'installments':
                        file = self.env['file'].create({
                                "from_member": True,
                                'membership_name': self.contact_name,
                                'membership_id': self.partner_id.id,
                                'user_id': self.partner_id.user_id.id or self.crm_id.user_id.id,
                                'project_type': 'skyscraper',
                                'token_id': self.id,
                                'crm_id': self.crm_id.id,
                                'society_id': self.society_id.id,
                                'ttl_sale_amount': total_sale_amount,
                                'sale_amount': total_sale_amount,
                                'phase_id': self.token_line_ids.phase_id.id,
                                'sector_id': self.token_line_ids.sector_id.id,
                                'street_id': self.token_line_ids.street_id.id,
                                'category_id': self.token_line_ids.category_id.id,
                                'unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                'size_id': self.token_line_ids.size_id.id,
                                'unit_class_id': self.token_line_ids.unit_class_id.id,
                                'inventory_id': self.token_line_ids.inventory_id.id,
                                'payment_type': payment,
                                'price_list_id': plan.price_list_id.id,
                                'add_custom_value': plan.add_custom_value,
                                'booking_date': plan.booking_date,
                                'plan_type': plan.plan_type,
                                'predefine_plan_id': plan.predefine_plan_id.id if plan.plan_type == 'predefine' else False,
                                'interval_id': plan.interval_id.id,
                                'starting_date': plan.starting_date,
                                'balloon_payment_interval': plan.balloon_payment_interval,
                                'balloon_payment_frequency': plan.balloon_payment_frequency,
                                'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                                   'approved': True if plan.include_in_plan == 'yes' else False})
                                                           for rec in plan.factor_id] if plan else False,
                                # 'factor_amount': plan.factor_amount,
                                'discount_type': plan.discount_type,
                                'discount_amount': plan.discount_amount,
                                'initial_payment': plan.initial_payment,
                                'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                                # 'ttl_sale_amount': plan.amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.amount,
                                'net_sale_amount': total_sale_amount,
                                'balloting_amount': plan.final_payment,
                                'total_installment': plan.total_installment,
                                'balloon_payment': plan.balloon_payment,
                                'create_manually': plan.create_manually,
                                'manual_installment_plan_ids': [(0, 0,
                                                                         {'product_id': x.product_id.id,
                                                                          'date': x.date,
                                                                          'percentage': x.percentage,
                                                                          'amount_manual': x.amount_manual,
                                                                          'line_calculated': x.line_calculated,
                                                                          }) for x in plan.manual_installment_plan_ids if
                                                                        plan.create_manually],
                                'balance_amount': balance_amount
                            })
                        file.create_installment_plan()
                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("land_development.file_form").id
                        result['res_id'] = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id

                    if len(res_ids) < 1 and self.payment_type == 'lump_sum':
                        return {
                            'type': 'ir.actions.act_window',
                            'view_id': self.env.ref('land_development.file_form').id,
                            'view_mode': 'form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.partner_id.id)],
                            'context': {'default_membership_id': self.partner_id.id,
                                        'default_token_id': self.id,
                                        'default_project_type': 'skyscraper',
                                        'from_member': 1,
                                        'default_payment_type': self.payment_type,
                                        'default_society_id': self.society_id.id,
                                        'default_phase_id': self.token_line_ids.phase_id.id,
                                        'default_sector_id': self.token_line_ids.sector_id.id,
                                        'default_street_id': self.token_line_ids.street_id.id,
                                        'default_category_id': self.token_line_ids.category_id.id,
                                        'default_unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                        'default_size_id': self.token_line_ids.size_id.id,
                                        'default_unit_class_id': self.token_line_ids.unit_class_id.id,
                                        'default_inventory_id': self.token_line_ids.inventory_id.id,
                                        },
                            'res_id': self.env['file'].search([('token_id', '=', self.id)]).id,
                        }

                    elif len(res_ids) < 2:
                        result['domain'] = []
                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("land_development.file_form").id
                        result['res_id'] = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id
                    else:
                        result['domain'] = [('membership_id', '=', self.partner_id.id),
                                            ('project_type', '=', 'skyscraper'), ('crm_id', '=', self.crm_id.id)]
                        result['view_mode'] = 'tree,form'

                    return result

            else:
                plan = self.env['propose.plan'].search(
                    [('token_id', '=', self.id)])
                if self.payment_type == 'lump_sum':
                    total_sale_amount = self.ttl_sale_amount
                    balance_amount = self.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                        balance_amount = plan.balance_amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                        balance_amount = plan.balance_amount
                member = self.env['res.member'].search([('token_id', '=', self.id)])
                payment = self.payment_type

                if member or self.is_existing == True and self.partner_id:
                    res_ids = self.env['file'].search([('token_id', '=', self.id)]).ids
                    result = {
                        'name': (_('File')),
                        'res_model': 'file',
                        'type': 'ir.actions.act_window',
                        # 'context': context,
                        'view_type': 'form',
                        'target': 'self'
                    }
                    if len(res_ids) < 1 and self.payment_type == 'installments':
                        file = self.env['file'].create({
                                'membership_name': self.contact_name,
                                'membership_id': self.partner_id.id,
                                'user_id': self.partner_id.user_id.id or self.crm_id.user_id.id,
                                'project_type': 'skyscraper',
                                'token_id': self.id,
                                'crm_id': self.crm_id.id,
                                'society_id': self.society_id.id,
                                'phase_id': self.token_line_ids.phase_id.id,
                                'sector_id': self.token_line_ids.sector_id.id,
                                'street_id': self.token_line_ids.street_id.id,
                                'category_id': self.token_line_ids.category_id.id,
                                'unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                'size_id': self.token_line_ids.size_id.id,
                                'unit_class_id': self.token_line_ids.unit_class_id.id,
                                'inventory_id': self.token_line_ids.inventory_id.id,
                                'payment_type': payment,
                                'price_list_id': plan.price_list_id.id,
                                'add_custom_value': plan.add_custom_value,
                                'booking_date': plan.booking_date,
                                'plan_type': plan.plan_type,
                                'predefine_plan_id': plan.predefine_plan_id.id if plan.plan_type == 'predefine' else False,
                                'interval_id': plan.interval_id.id,
                                'starting_date': plan.starting_date,
                                'balloon_payment_interval': plan.balloon_payment_interval,
                                'balloon_payment_frequency': plan.balloon_payment_frequency,
                                'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                                   'approved': True if plan.include_in_plan == 'yes' else False})
                                                           for rec in plan.factor_id] if plan else False,
                                # 'factor_amount': plan.factor_amount,
                                'discount_type': plan.discount_type,
                                'discount_amount': plan.discount_amount,
                                'initial_payment': plan.initial_payment,
                                'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                                'ttl_sale_amount': total_sale_amount,
                                'sale_amount': total_sale_amount,
                                # 'ttl_sale_amount': plan.amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.amount,
                                'net_sale_amount': total_sale_amount,
                                'balloting_amount': plan.final_payment,
                                'total_installment': plan.total_installment,
                                'balloon_payment': plan.balloon_payment,
                                'create_manually': plan.create_manually,
                                'manual_installment_plan_ids': [(0, 0,
                                                                         {'product_id': x.product_id.id,
                                                                          'date': x.date,
                                                                          'percentage': x.percentage,
                                                                          'amount_manual': x.amount_manual,
                                                                          'line_calculated': x.line_calculated,
                                                                          }) for x in plan.manual_installment_plan_ids if
                                                                        plan.create_manually],
                                'balance_amount': balance_amount
                        })

                        file.create_installment_plan()

                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("land_development.file_form").id
                        result['res_id'] = self.env['file'].search([('token_id', '=', self.id)]).id

                    if len(res_ids) < 1 and self.payment_type == 'lump_sum':
                        return {
                            'type': 'ir.actions.act_window',
                            'view_id': self.env.ref('land_development.file_form').id,
                            'view_mode': 'form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.partner_id.id)],
                            'context': {'default_membership_id': self.partner_id.id,
                                        'default_token_id': self.id,
                                        'default_project_type': 'skyscraper',
                                        'from_member': 1,
                                        'default_payment_type': self.payment_type,
                                        'default_society_id': self.society_id.id,
                                        'default_phase_id': self.token_line_ids.phase_id.id,
                                        'default_sector_id': self.token_line_ids.sector_id.id,
                                        'default_street_id': self.token_line_ids.street_id.id,
                                        'default_category_id': self.token_line_ids.category_id.id,
                                        'default_unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                        'default_size_id': self.token_line_ids.size_id.id,
                                        'default_unit_class_id': self.token_line_ids.unit_class_id.id,
                                        'default_inventory_id': self.token_line_ids.inventory_id.id,
                                        },
                            'res_id': self.env['file'].search([('token_id', '=', self.id)]).id,
                        }

                    elif len(res_ids) < 2:
                        result['domain'] = []
                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("land_development.file_form").id
                        result['res_id'] = self.env['file'].search([('token_id', '=', self.id)]).id
                    else:
                        result['domain'] = [('membership_id', '=', self.partner_id.id),
                                            ('project_type', '=', 'skyscraper'), ('token_id', '=', self.id)]
                        result['view_mode'] = 'tree,form'

                    return result

        elif self.project_type == 'housing_society':
            if self.crm_id:
                plan = self.env['propose.plan'].search(
                    [('crm_id', '=', self.crm_id.id)])
                if self.payment_type == 'lump_sum':
                    total_sale_amount = self.ttl_sale_amount
                    balance_amount = self.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                        balance_amount = plan.balance_amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                        balance_amount = plan.balance_amount

                member = self.env['res.member'].search([('crm_id', '=', self.crm_id.id)])
                payment = self.payment_type
                if member or self.is_existing == True and self.partner_id:
                    res_ids = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).ids
                    result = {
                        'name': (_('File')),
                        'res_model': 'file',
                        'type': 'ir.actions.act_window',
                        # 'context': context,
                        'view_type': 'form',
                        'target': 'self'
                    }
                    if len(res_ids) < 1 and self.payment_type == 'installments':
                        file = self.env['file'].create({
                            'membership_name': self.contact_name,
                            'membership_id': self.partner_id.id,
                            'user_id': self.partner_id.user_id.id or self.crm_id.user_id.id,
                            'project_type': 'housing_society',
                            'token_id': self.id,
                            'crm_id': self.crm_id.id,
                            'society_id': self.society_id.id,
                            'phase_id': self.token_line_ids.phase_id.id,
                            'sector_id': self.token_line_ids.sector_id.id,
                            'street_id': self.token_line_ids.street_id.id,
                            'category_id': self.token_line_ids.category_id.id,
                            'unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                            'size_id': self.token_line_ids.size_id.id,
                            'unit_class_id': self.token_line_ids.unit_class_id.id,
                            'inventory_id': self.token_line_ids.inventory_id.id,
                            'payment_type': payment,
                            'price_list_id': plan.price_list_id.id,
                            'add_custom_value': plan.add_custom_value,
                            'booking_date': plan.booking_date,
                            # 'plan_type': plan.plan_type,
                            'plan_type': 'custom',
                            # 'predefine_plan_id': plan.predefine_plan_id.id if plan.plan_type == 'predefine' else False,
                            'predefine_plan_id': False,
                            'interval_id': plan.interval_id.id,
                            'starting_date': plan.starting_date,
                            'balloon_payment_interval': plan.balloon_payment_interval,
                            'balloon_payment_frequency': plan.balloon_payment_frequency,
                            'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                       'approved': True if plan.include_in_plan == 'yes' else False})
                                               for rec in plan.factor_id] if plan else False,
                            # 'factor_amount': plan.factor_amount,
                            'discount_type': plan.discount_type,
                            'discount_amount': plan.discount_amount,
                            'initial_payment': plan.initial_payment,
                            'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                            'ttl_sale_amount': total_sale_amount,
                            'sale_amount': total_sale_amount,
                            # 'ttl_sale_amount': plan.amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.amount,
                            'net_sale_amount': total_sale_amount,
                            'balloting_amount': plan.final_payment,
                            'total_installment': plan.total_installment,
                            'balloon_payment': plan.balloon_payment,
                            'create_manually': plan.create_manually,
                            # 'create_manually': True,
                            'installment_plan_ids': [(0, 0,
                                                             {'date': x.date,
                                                                'installment_number': x.installment_number,
                                                                'installment_type': x.installment_type,
                                                                'installment_name': x.installment_name,
                                                                'payment_status': 'not_paid',
                                                                'residual': x.amount,
                                                                'amount': x.amount,
                                                              }) for x in plan.propose_installment_plan_ids],
                            # 'manual_installment_plan_ids': [(0, 0,
                            #                                  {'product_id': x.product_id.id,
                            #                                   'date': x.date,
                            #                                   'percentage': x.percentage,
                            #                                   'amount_manual': x.amount_manual,
                            #                                   'line_calculated': x.line_calculated,
                            #                                   }) for x in plan.manual_installment_plan_ids if
                            #                                 plan.create_manually],
                            'balance_amount': balance_amount
                        })
                        # file.create_installment_plan()

                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("real_estate.file_form").id
                        result['res_id'] = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id

                    if len(res_ids) < 1 and self.payment_type == 'lump_sum':
                        return {
                            'type': 'ir.actions.act_window',
                            'view_id': self.env.ref('real_estate.file_form').id,
                            'view_mode': 'form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.partner_id.id)],
                            'context': {'default_membership_id': self.partner_id.id,
                                        'default_token_id': self.id,
                                        'default_project_type': 'housing_society',
                                        'from_member': 1,
                                        'default_payment_type': self.payment_type,
                                        'default_society_id': self.society_id.id,
                                        'default_phase_id': self.token_line_ids.phase_id.id,
                                        'default_sector_id': self.token_line_ids.sector_id.id,
                                        'default_street_id': self.token_line_ids.street_id.id,
                                        'default_category_id': self.token_line_ids.category_id.id,
                                        'default_unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                        'default_size_id': self.token_line_ids.size_id.id,
                                        'default_unit_class_id': self.token_line_ids.unit_class_id.id,
                                        'default_inventory_id': self.token_line_ids.inventory_id.id,
                                        },
                            'res_id': self.env['file'].search([('token_id', '=', self.id)]).id,
                        }

                    elif len(res_ids) < 2:
                        result['domain'] = []
                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("real_estate.file_form").id
                        result['res_id'] = self.env['file'].search([('crm_id', '=', self.crm_id.id)]).id
                    else:
                        result['domain'] = [('membership_id', '=', self.partner_id.id),
                                            ('project_type', '=', 'housing_society'), ('crm_id', '=', self.crm_id.id)]
                        result['view_mode'] = 'tree,form'

                    return result

            else:
                plan = self.env['propose.plan'].search(
                    [('token_id', '=', self.id)])
                if self.payment_type == 'lump_sum':
                    total_sale_amount = self.ttl_sale_amount
                    balance_amount = self.ttl_sale_amount
                else:
                    if plan.include_in_plan == 'yes':
                        total_sale_amount = plan.amount + plan.factor_amount
                        balance_amount = plan.balance_amount + plan.factor_amount
                    else:
                        total_sale_amount = plan.amount
                        balance_amount = plan.balance_amount

                member = self.env['res.member'].search([('token_id', '=', self.id)])
                payment = self.payment_type

                if member or self.is_existing == True and self.partner_id:
                    res_ids = self.env['file'].search([('token_id', '=', self.id)]).ids
                    result = {
                        'name': (_('File')),
                        'res_model': 'file',
                        'type': 'ir.actions.act_window',
                        # 'context': context,
                        'view_type': 'form',
                        'target': 'self'
                    }
                    if len(res_ids) < 1 and self.payment_type == 'installments':
                        file = self.env['file'].create({
                            'membership_name': self.contact_name,
                            'membership_id': self.partner_id.id,
                            'user_id': self.partner_id.user_id.id or self.crm_id.user_id.id,
                            'project_type': 'housing_society',
                            'token_id': self.id,
                            'crm_id': self.crm_id.id,
                            'society_id': self.society_id.id,
                            'phase_id': self.token_line_ids.phase_id.id,
                            'sector_id': self.token_line_ids.sector_id.id,
                            'street_id': self.token_line_ids.street_id.id,
                            'category_id': self.token_line_ids.category_id.id,
                            'unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                            'size_id': self.token_line_ids.size_id.id,
                            'unit_class_id': self.token_line_ids.unit_class_id.id,
                            'inventory_id': self.token_line_ids.inventory_id.id,
                            'payment_type': payment,
                            'price_list_id': plan.price_list_id.id,
                            'add_custom_value': plan.add_custom_value,
                            'booking_date': plan.booking_date,
                            'plan_type': plan.plan_type,
                            'predefine_plan_id': plan.predefine_plan_id.id if plan.plan_type == 'predefine' else False,
                            'interval_id': plan.interval_id.id,
                            'starting_date': plan.starting_date,
                            'balloon_payment_interval': plan.balloon_payment_interval,
                            'balloon_payment_frequency': plan.balloon_payment_frequency,
                            'preference_ids': [(0, 0, {'factor_id': rec.id, 'total': plan.factor_amount,
                                                               'approved': True if plan.include_in_plan == 'yes' else False})
                                                       for rec in plan.factor_id] if plan else False,
                            # 'factor_amount': plan.factor_amount,
                            'discount_type': plan.discount_type,
                            'discount_amount': plan.discount_amount,
                            'initial_payment': plan.initial_payment,
                            'custom_sale_amount': plan.amount if plan.add_custom_value else 0,
                            'ttl_sale_amount': total_sale_amount,
                            'sale_amount': total_sale_amount,
                            # 'ttl_sale_amount': plan.amount + plan.factor_amount if plan.include_in_plan == 'yes' else plan.amount,
                            'net_sale_amount': total_sale_amount,
                            'balloting_amount': plan.final_payment,
                            'total_installment': plan.total_installment,
                            'balloon_payment': plan.balloon_payment,
                            'create_manually': plan.create_manually,
                            'manual_installment_plan_ids': [(0, 0,
                                                                     {'product_id': x.product_id.id,
                                                                      'date': x.date,
                                                                      'percentage': x.percentage,
                                                                      'amount_manual': x.amount_manual,
                                                                      'line_calculated': x.line_calculated,
                                                                      }) for x in plan.manual_installment_plan_ids if
                                                                    plan.create_manually],
                            'balance_amount': balance_amount
                        })
                        file.create_installment_plan()

                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("real_estate.file_form").id
                        result['res_id'] = self.env['file'].search([('token_id', '=', self.id)]).id

                    if len(res_ids) < 1 and self.payment_type == 'lump_sum':
                        return {
                            'type': 'ir.actions.act_window',
                            'view_id': self.env.ref('real_estate.file_form').id,
                            'view_mode': 'form',
                            'name': _('File'),
                            'res_model': 'file',
                            'domain': [('membership_id', '=', self.partner_id.id)],
                            'context': {'default_membership_id': self.partner_id.id,
                                        'default_token_id': self.id,
                                        'default_project_type': 'housing_society',
                                        'from_member': 1,
                                        'default_payment_type': self.payment_type,
                                        'default_society_id': self.society_id.id,
                                        'default_phase_id': self.token_line_ids.phase_id.id,
                                        'default_sector_id': self.token_line_ids.sector_id.id,
                                        'default_street_id': self.token_line_ids.street_id.id,
                                        'default_category_id': self.token_line_ids.category_id.id,
                                        'default_unit_category_type_id': self.token_line_ids.unit_category_type_id.id,
                                        'default_size_id': self.token_line_ids.size_id.id,
                                        'default_unit_class_id': self.token_line_ids.unit_class_id.id,
                                        'default_inventory_id': self.token_line_ids.inventory_id.id,
                                        'default_ttl_sale_amount': self.ttl_sale_amount,
                                        'default_sale_amount': self.ttl_sale_amount,
                                        'default_net_sale_amount': self.ttl_sale_amount,
                                        'default_balance_amount': self.balance_amount,
                                        },
                            'res_id': self.env['file'].search([('token_id', '=', self.id)]).id,
                        }

                    elif len(res_ids) < 2:
                        result['domain'] = []
                        result['view_mode'] = 'form'
                        result['view_id'] = self.env.ref("real_estate.file_form").id
                        result['res_id'] = self.env['file'].search([('token_id', '=', self.id)]).id

                    else:
                        result['domain'] = [('membership_id', '=', self.partner_id.id),
                                            ('project_type', '=', 'housing_society'), ('token_id', '=', self.id)]
                        result['view_mode'] = 'tree,form'

                    return result

    def create_open_files(self):
        if self.open_file_amount_received != True:
            raise ValidationError("You must pay all the remaining amount to create open file.")

        if not self.open_files_created:
            for inv in self.token_line_ids:
                investor_file = self.env['investor.file']
                vals = {
                        'token_id': self.id,
                        'state': 'open',
                        'society_id': self.society_id.id,
                        'phase_id': inv.phase_id.id,
                        'sector_id': inv.sector_id.id,
                        'street_id': inv.street_id.id,
                        'category_id': inv.category_id.id,
                        'unit_category_type_id': inv.unit_category_type_id.id,
                        'size_id': inv.size_id.id,
                        'unit_class_id': inv.unit_class_id.id,
                        'inventory_id': inv.inventory_id.id,
                        'unit_number': inv.inventory_id.name,
                        'payment_type': 'lump_sum',
                        'interval_id': False,
                        'starting_date': fields.Date.today(),
                        'total_installment': 0,
                        'payment_states': 'open',
                        'sale_amount': self.balance_amount + self.token_fees,
                        'ttl_sale_amount': self.balance_amount + self.token_fees,
                        'net_sale_amount': self.balance_amount + self.token_fees,
                        'initial_payment': self.balance_amount + self.token_fees,
                        'balance_amount': 0,
                       }
                investor_file.create(vals)
            self.open_files_created = True
        else:
            return {
                'res_model': 'investor.file',
                'type': 'ir.actions.act_window',
                'context': {},
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.env['investor.file'].search([('token_id','=',self.id)]).id,
                'view_id': self.env.ref(
                    "real_estate.investor_file_form").id if self.project_type == 'housing_society' else self.env.ref(
                    'land_development.investor_file_form').id,
                'target': 'self'
            }

    def propose_plan(self):
        # if self.plan_locked:
        #     raise ValidationError(_("Your Installment Plan is already created. Probably on CRM."))
        if not self.token_line_ids:
            raise ValidationError(_("You can not Propose Plan before select any plot."))
        if self.crm_id:
            return {
                'res_model': 'propose.plan',
                'type': 'ir.actions.act_window',
                'context': {'default_token_id': self.id, },
                # 'domain': [('crm_id', '=', self.crm_id.id)],
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.env['propose.plan'].search(
                    ['|', ('token_id', '=', self.id), ('crm_id', '=', self.crm_id.id)]).id,
                'view_id': self.env.ref("real_estate.propose_plan_form").id,
                'target': 'self'
            }
        else:
            context = {'default_token_id': self.id, }
            return {
                'res_model': 'propose.plan',
                'type': 'ir.actions.act_window',
                'context': context,
                # 'domain': [('customer_id', '=', self.customer_id)],
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.env['propose.plan'].search([('token_id', '=', self.id)]).id,
                'view_id': self.env.ref("real_estate.propose_plan_form").id,
                'target': 'self'
            }

    @api.model
    def validate_token_date(self):
        date = self.env.ref('real_estate.ir_cron_token_validity').till_date or fields.Date.today()
        for rec in self.search([('state', '!=', 'cancel')]):
            if rec.token_generated == True and rec.date <= date:
                rec.validity_expire = True
                rec.token_line_ids[0].inventory_id.state = 'avalible_for_sale'

    def token_expiry(self):
        for rec in self:
            if rec.token_generated == True and rec.state in ('open','paid'):
                rec.validity_expire = True
                rec.token_line_ids[0].inventory_id.state = 'avalible_for_sale'

    def increase_validity(self):
        # file = self.env['file'].search([('token_id', '=', self.id)])
        # if file:
        #     raise ValidationError('File is already created so validity of token cannot be increased.')
        context = {'default_current_date': self.date, }
        return {
            'name': _('Validity Increase'),
            'view_mode': 'form',
            'res_model': 'validity.increase',
            'context': context,
            'res_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def token_refund(self):
        # file = self.env['file'].search([('token_id', '=', self.id)])
        # if file:
        #     raise ValidationError('File is already created so token cannot be refund.')
        if self.token_generated == True and self.state != 'cancel':
            context = {
                'default_token_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_contact_name': self.contact_name,
                'default_email': self.email,
                'default_cnic': self.cnic,
                'default_phone_no': self.phone_no,
                'default_society_id': self.society_id.id,
                'default_date': self.date,
                'default_journal_id': self.journal_id.id,
                'default_cheque_name': self.cheque_name,
                'default_cheque_no': self.cheque_no,
                'default_bank_ref': self.bank_ref,
                'default_token_refund_line_ids': [(0, 0, {
                    'token_fees': self.token_fees,
                    'category_id': self.token_line_ids.category_id.id,
                    'unit_category_type_id': self.token_line_ids.unit_category_type_id.id
                })]
            }
            return {
                'name': _('Token Refund'),
                'view_mode': 'form',
                'res_model': 'token.refund',
                'context': context,
                'res_id': False,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def cancel_token(self):
        # file = self.env['file'].search([('token_id', '=', self.id)])
        # if file:
        #     raise ValidationError('File is already created so token cannot be cancelled.')
        if self.token_generated == True and self.state != 'cancel':
            token_cancel = self.env.ref('real_estate.token_cancel')
            if self.token_paid:
                debit_vals = {
                    'debit': abs(self.token_fees),
                    'credit': 0.0,
                    'account_id': token_cancel.product_id.property_account_expense_id.id,
                    'company_id': self.env.company.id,
                }

                credit_vals = {
                    'debit': 0.0,
                    'credit': abs(self.token_fees),
                    'account_id': token_cancel.product_id.property_account_income_id.id,
                    'company_id': self.env.company.id,
                }

                vals = {
                    'journal_id': self.journal_id.id,
                    'ref': self.serial_number,
                    'partner_id': self._token_accounting_partner_id(),
                    'token_id': self.id,
                    'move_type': 'entry',
                    'date': self.date,
                    'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
                }
                move = self.env['account.move'].create(vals)
                move.action_post()
                self.state = 'cancel'
                self.validity_expire = False
                # investor tokens have no unit lines; their units live on the Deal
                if self.token_line_ids:
                    self.token_line_ids[0].inventory_id.state = 'avalible_for_sale'

    def unlink(self):
        for rec in self:
            if rec.token_paid or rec.token_generated:
                raise ValidationError("You cannot delete a token once it is paid.")
        return super(TokenMoney, self).unlink()


class TokenMoneyLine(models.Model):
    _name = 'token.money.line'
    _description = 'Token Money Line'

    phase_id = fields.Many2one('society', 'Phase', required=True, domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector', required=True)
    street_id = fields.Many2one('street')
    category_id = fields.Many2one('plot.category', required=True, store=True, related="inventory_id.category_id",
                                  readonly=False)
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product', required=True, store=True,
                                            related="inventory_id.unit_category_type_id", readonly=False)
    size_id = fields.Many2one('unit.size', related="inventory_id.size_id", store=True, readonly=False)
    unit_class_id = fields.Many2one('unit.class', 'Type', store=True, related="inventory_id.unit_class_id",
                                    readonly=False)
    inventory_id = fields.Many2one('plot.inventory', context={'active_model': 'token.money.line'},
                                   string='Unit')
    token_id = fields.Many2one('token.money')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(TokenMoneyLine, self).create(vals_list)
        for rec in res:
            inventory = self.env['plot.inventory'].search([
                ('society_id', '=', rec.token_id.society_id.id),
                ('phase_id', '=', rec.phase_id.id),
                ('sector_id', '=', rec.sector_id.id),
                ('category_id', '=', rec.category_id.id),
                ('unit_category_type_id', '=', rec.unit_category_type_id.id),
                ('state', '=', 'avalible_for_sale'),
            ], limit=1)
            if not rec.inventory_id:
                if inventory:
                    rec.inventory_id = inventory.id
                # else:
                    # raise ValidationError(_("Inventory of specified criteria didn't exist. "))
        return res

    @api.onchange('phase_id', 'sector_id', 'street_id', 'inventory_id')
    def _phase_domain(self):
        if self.inventory_id:
            self.street_id = self.inventory_id.street_id.id

        if self.street_id:
            return {'domain': {
                'inventory_id': [('street_id', '=', self.street_id.id), ('state', '=', 'avalible_for_sale')]
            }
            }
        else:
            return {'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.token_id.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'inventory_id': [('street_id', '=', self.street_id.id), ('state', '=', 'avalible_for_sale')]
            }
            }
