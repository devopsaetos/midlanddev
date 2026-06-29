# -*- coding: utf-8 -*-

import random
import string
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class UnitSwappingRequestExt(models.Model):
    _inherit = 'unit.swapping.request'
    _description = "Unit Swapping Request"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'Confirmed'),
        ('printed', 'Request Printed'),
        ('approve', 'In Process'),
        ('file_printed', 'File Printed'),
        ('delivered', 'Delivered'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    paid_to = fields.Selection([
        ('company', 'Company'),
        ('dealer', 'Dealer'),
    ], tracking=True)
    document_number = fields.Char(string="Document #", tracking=True)
    cheque_name = fields.Char(string="Cheque Name", tracking=True)
    bank_name = fields.Char(string="Issuing Bank", tracking=True)
    other_relation = fields.Char(string="Other Relation", tracking=True)
    include_confirmation = fields.Boolean(string="Include Confirmation", tracking=True)
    installment_starting_date = fields.Date(string="Installment Starting Date", tracking=True)
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default="cash")
    sale_on = fields.Selection([
        ('old_price', 'Old Price'),
        ('new_price', 'New Price'),
    ], default="old_price", tracking=True)
    new_price = fields.Float(string="New Price", tracking=True)
    new_predefine_plan_id = fields.Many2one('predefine.plan', string="New Plan", tracking=True)
    change_payment_type = fields.Boolean(string='Change Payment Type ?', tracking=True)
    new_payment_type = fields.Selection([
        ('installments', 'Installment'),
        ('lump_sum', 'Lump Sum')], string='New Payment Type', tracking=True)
    validation_date = fields.Date(string="Valid Till", tracking=True)
    # Sub Dealer
    from_sub_investor = fields.Boolean(string="From Sub Dealer", tracking=True)
    sub_investor_id = fields.Many2one('res.investor', string="Sub Investor", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if vals.get('transaction_type') == 'open_file':
                    if self.env.company.id != 1:
                        random_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        vals['name'] = 'IFR - ' + random_num
                    else:
                        vals['name'] = self.env['ir.sequence'].next_by_code("investment.file.issuance.request") or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code("unit.swapping.request") or _('New')
        rec = super().create(vals_list)
        rec.check_for_duplicate_request_against_file()
        rec.change_installment_starting_date()
        rec.set_validation_date()
        # rec.change_open_file_status()

        return rec

    def check_for_duplicate_request_against_file(self):
        for rec in self:
            open_files = rec.unit_swapping_request_lines.mapped('investor_file_id.id')
            lines = self.env['unit.swapping.request.lines'].search(
                [('investor_file_id', 'in', open_files), ('unit_swapping_request_id.state', '!=', 'cancel'),
                 ('unit_swapping_request_id.id', '!=',
                  rec.id)])
            if lines:
                error = f"\n-----------------------------\nDUPLICATION DETECTED\n-----------------------------\n\nRequest against this File has already been created.\n" \
                        f"Request No. is : {lines[0].unit_swapping_request_id.name}"
                raise UserError(error)
            else:
                return True

    def change_installment_starting_date(self):
        for rec in self:
            if rec.appointment_date:
                confirmation_date = rec.appointment_date + relativedelta(days=+45)
                installment_date = confirmation_date + relativedelta(months=+1)
                if abs((installment_date.replace(day=1) - confirmation_date).days) > 15:
                    installment_date = installment_date.replace(day=1)
                else:
                    installment_date = installment_date.replace(day=1) + relativedelta(months=+1)
                # if abs((installment_date.replace(day=1) - installment_date).days) <= 15:
                #     installment_date = installment_date.replace(day=1)
                # else:
                #     installment_date = installment_date.replace(day=1) + relativedelta(months=+1)
                rec.installment_starting_date = installment_date

    def set_validation_date(self):
        for rec in self:
            rec.validation_date = datetime.today() + relativedelta(days=+15)

    def request_printed(self):
        for rec in self:
            rec.check_for_duplicate_request_against_file()
            rec.state = 'printed'
            rec.change_open_file_status()

    def change_open_file_status(self):
        for rec in self:
            if rec.transaction_type == 'open_file':
                for line in rec.unit_swapping_request_lines:
                    if line.investor_file_id.state in ['open', 'selected']:
                        line.investor_file_id.state = 'in_process'
                    line.investor_file_id.issuance_request_created = True
                    line.investor_file_id.issuance_request_id = rec.id
            else:
                pass

    def send_sms(self, number, message):
        # message = f"Your Five digit otp number is : {otp.auth_otp}"
        # number = otp.partner_id.mobile
        #self.env['tools.mixin'].sudo().simple_send(message, number)
        pass

    def in_process(self):
        self.state = 'in_process'
        # customer_message = f"Dear {self.transferee_partner_id.name}, Your Request for File - {self.unit_swapping_request_lines[0].investor_file_id.name} has been " \
        #                   f"Processed"
        # customer_number = self.transferee_partner_id.mobile
        # # #self.env['tools.mixin'].sudo().simple_send(message, number)
        # self.send_sms(customer_number, customer_message)
        # dealer_message = f"Dear {self.investor_id.name}, Your Request for File - {self.unit_swapping_request_lines[0].investor_file_id.name} has been " \
        #                   f"Processed"
        # dealer_number = self.investor_id.mobile
        # # #self.env['tools.mixin'].sudo().simple_send(message, number)
        # self.send_sms(dealer_number, dealer_message)

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
                if self.file_id.investor_file:
                    self.file_id.investor_file.issuance_request_id.request_cancel()
                    self.file_id.investor_file.is_transferee_partner = False
                    self.file_id.investor_file.transferee_partner_id = False
                    self.file_id.investor_file.transferee_cnic_number = False
                    self.file_id.investor_file.transferee_relation_name = False
                self.state = 'approve'
            if self.new_inventory_id and self.change_price == 'yes':
                paid_amount = sum(
                    self.file_id.installment_plan_ids.filtered(lambda l: l.invoice_created and l.payment_status == 'paid').mapped(
                        'amount_paid'))
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

                due_invoices = self.investment_id.investment_plan_ids.filtered(
                    lambda l: l.invoice_created == True and l.payment_status != 'paid')

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
                        (self.investment_id.investment_history_ids[-1].new_amount / len(
                            unassigned_files.filtered(lambda l: l.state == 'open'))) * len(open_files))
                    investment_history = self.investment_id.investment_history_ids.create({
                        'installment_number': self.investment_id.investment_history_ids[
                                                  -1].installment_number + 1,
                        'date': fields.Date.today(),
                        'transaction_type': 'cancel',
                        'amount': round(self.investment_id.investment_history_ids[-1].new_amount),
                        'new_amount': self.investment_id.investment_history_ids[-1].new_amount - amount_to_deduct,
                        'old_balance': self.investment_id.investment_history_ids[-1].new_balance,
                        'new_balance': self.investment_id.investment_history_ids[-1].new_balance - (
                                amount_to_deduct * self.investment_id.total_installment),
                        'investment_id': self.investment_id.id,
                    })

                    # Updating remaining installments amount
                    for line in self.investment_id.investment_plan_ids.filtered(
                            lambda l: l.invoice_created != True and l.balance_amount > 0):
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
                self.check_for_duplicate_request_against_file()
                if not self.is_transferee_partner and not all(
                        [self.transferee_name, self.transferee_mobile, self.transferee_relation_name, self.transferee_street,
                         self.transferee_country_id,
                         self.transferee_company_type, self.kin_name, self.kin_member_relation]):
                    raise ValidationError("Please fill the following fields to proceed: \n "
                                          "Name, Member Type, Mobile, Father/Spouse, Street, Country, Kin Name and Relation.")

                if not self.transferee_partner_id:
                    self.create_partner()
                else:
                    self.transferee_partner_id.project_type = self.investment_id.project_type

                # if self.investment_id.options == 'full':
                #     if self.investment_id.amount_paid == 0 or self.investment_id.investor_unit_price > self.investment_id.amount_paid:
                #         raise ValidationError('You cannot issue file due to insufficient balance.')
                if self.sale_on == 'new_price' and self.new_price < 1:
                    raise ValidationError('Please Enter some value to Change the Price')
                investor_files = self.unit_swapping_request_lines.mapped('investor_file_id')
                if self.sale_on == 'new_price' and investor_files:
                    if not self.new_predefine_plan_id:
                        raise ValidationError('Please Select the Predefine Plan')
                    for file in investor_files:
                        if self.change_payment_type and self.new_payment_type and self.new_payment_type == file.payment_type:
                            raise ValidationError(
                                'This Payment Type is already used on File, Please select the other one or change teh method.')
                        self.env['open.file.history'].create({
                            'investor_file_id': file.id,
                            'net_sale_amount': file.net_sale_amount,
                            'predefine_plan_id': file.predefine_plan_id.id,
                            'no_of_installments': file.total_installment,
                            # 'discount': file.discount,
                            'booking_marketing_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').marketing_share,
                            'booking_dealer_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').dealer_share,
                            'booking_rebate_amount': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').rebate_amount,
                            'confirmation_marketing_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').marketing_share,
                            'confirmation_dealer_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').dealer_share,
                            'confirmation_rebate_amount': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').rebate_amount,
                        })
                        file.sale_amount = self.new_price
                        file.ttl_sale_amount = self.new_price
                        file.net_sale_amount = self.new_price
                        file.predefine_plan_id = self.new_predefine_plan_id.id
                        file.initial_payment = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                            lambda l: l.product_id.id == self.env.ref('real_estate.downpayment_product').id).value
                        file.total_installment = self.new_predefine_plan_id.total_installment
                        file.interval_id = self.new_predefine_plan_id.interval_id.id
                        file._balloon_payment()
                        total_plan_amount = 0
                        for product in self.new_predefine_plan_id.predefine_plan_line_ids:
                            total_plan_amount += product.value * product.frequency
                        installment_amount = (self.new_price - total_plan_amount) / self.new_predefine_plan_id.total_installment
                        booking_line = file.installment_plan_ids.filtered(lambda l: l.installment_name == 'Booking')
                        if booking_line:
                            booking_line.previous_dealer_rebate = booking_line.dealer_share
                            booking_line.previous_marketing_rebate = booking_line.marketing_share
                            booking_line.previous_total_rebate = booking_line.rebate_amount
                        conf_line = file.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation')
                        if conf_line:
                            conf_line.previous_dealer_rebate = conf_line.dealer_share
                            conf_line.previous_marketing_rebate = conf_line.marketing_share
                            conf_line.previous_total_rebate = conf_line.rebate_amount
                        for line in file.installment_plan_ids:
                            if line.installment_name == 'Booking':
                                line.previous_amount = line.amount
                                line.amount = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                                    lambda l: l.product_id.id == self.env.ref('real_estate.downpayment_product').id).value
                                line.amount_paid = line.amount
                                line.amount_difference = line.amount - line.previous_amount
                                # Rebate
                                # line.previous_dealer_rebate = line.dealer_share
                                # line.previous_marketing_rebate = line.marketing_share
                                # line.previous_total_rebate = line.rebate_amount
                            if line.installment_name == 'Confirmation':
                                line.previous_amount = line.amount
                                line.amount = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                                    lambda l: l.product_id.id == self.env.ref('real_estate.confirmation_amount_product').id).value
                                line.amount_difference = line.amount - line.previous_amount
                                # Rebate
                                # line.previous_dealer_rebate = line.dealer_share
                                # line.previous_marketing_rebate = line.marketing_share
                                # line.previous_total_rebate = line.rebate_amount
                            if line.installment_name == 'Balloon':
                                line.previous_amount = line.amount
                                line.amount = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                                    lambda l: l.product_id.id == self.env.ref('real_estate.balloon_payment').id).value
                                line.amount_difference = line.amount - line.previous_amount
                            if line.installment_name == 'Balloting':
                                line.previous_amount = line.amount
                                line.amount = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                                    lambda l: l.product_id.id == self.env.ref('real_estate.balloting_product').id).value
                                line.amount_difference = line.amount - line.previous_amount
                            if line.installment_name == 'Possession':
                                line.previous_amount = line.amount
                                line.amount = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                                    lambda l: l.product_id.id == self.env.ref('real_estate.possession_amount_product').id).value
                                line.amount_difference = line.amount - line.previous_amount
                            if 'Installment' in line.installment_name:
                                line.previous_amount = line.amount
                                line.amount = installment_amount
                                line.amount_difference = line.amount - line.previous_amount
                            # line.previous_dealer_rebate = line.dealer_share
                            # line.previous_marketing_rebate = line.marketing_share
                            # line.previous_total_rebate = line.rebate_amount
                            file.compute_rebate_amount()
                            line.dealer_rebate_difference = line.dealer_share - line.previous_dealer_rebate
                            line.marketing_rebate_difference = line.marketing_share - line.previous_marketing_rebate
                            line.total_rebate_difference = line.rebate_amount - line.previous_total_rebate
                            # line.dealer_share = new_dealer_rebate
                            # line.marketing_share = new_marketing_rebate
                            # line.dealer_rebate_difference = line.dealer_share - line.previous_dealer_rebate
                            # line.marketing_rebate_difference = line.marketing_share - line.previous_marketing_rebate
                            # line.total_rebate_difference = new_rebate - line.rebate_amount
                            # line.rebate_amount = new_rebate
                            line.price_revised = True
                            line.compute_net_receivable()
                            line._invoice_id_data()
                            line.compute_net_payment()
                            line.compute_lps()
                        if self.change_payment_type and self.new_payment_type:
                            file.payment_type = self.new_payment_type
                if self.change_payment_type:
                    if not self.new_payment_type:
                        raise ValidationError('Select the Payment Type for the File to Change.')
                    if not self.new_predefine_plan_id:
                        raise ValidationError('Please select the New Plan for New Payment Type.')
                    for file in investor_files:
                        if self.change_payment_type and self.new_payment_type and self.new_payment_type == file.payment_type:
                            raise ValidationError(
                                'This Payment Type is already used on File, Please select the other one or change teh method.')
                        self.env['open.file.history'].create({
                            'investor_file_id': file.id,
                            'net_sale_amount': file.net_sale_amount,
                            'predefine_plan_id': file.predefine_plan_id.id,
                            'no_of_installments': file.total_installment,
                            # 'discount': file.discount,
                            'booking_marketing_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').marketing_share,
                            'booking_dealer_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').dealer_share,
                            'booking_rebate_amount': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Booking').rebate_amount,
                            'confirmation_marketing_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').marketing_share,
                            'confirmation_dealer_share': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').dealer_share,
                            'confirmation_rebate_amount': file.installment_plan_ids.filtered(
                                lambda l: l.installment_name == 'Confirmation').rebate_amount,
                        })
                        change_description = f"Change Payment Type from {file.payment_type} - To {self.new_payment_type}"
                        file.predefine_plan_id = self.new_predefine_plan_id.id
                        file.initial_payment = self.new_predefine_plan_id.predefine_plan_line_ids.filtered(
                            lambda l: l.product_id.id == self.env.ref('real_estate.downpayment_product').id).value or 0
                        file.total_installment = self.new_predefine_plan_id.total_installment
                        file.interval_id = self.new_predefine_plan_id.interval_id.id
                        file.reset_open_file_installment_plan()
                        file._balloon_payment()
                        file.create_installment_plan()
                        file.payment_type = self.new_payment_type
                        file.message_post(body=change_description)
                        self.message_post(body=change_description)
                for rec in self.unit_swapping_request_lines:
                    rec.investor_file_id.is_transferee_partner = True
                    rec.investor_file_id.transferee_partner_id = self.transferee_partner_id.id
                    rec.investor_file_id.starting_date = self.installment_starting_date
                    rec.investor_file_id.create_file()
                    new_file = self.env['file'].search([('investor_file', '=', rec.investor_file_id.id)])
                    new_file.issuance_request_id = self.id
                    new_file.recompute_lps_for_current_file()
                    # Add record to Request history
                    # new_file.file_request_history_ids
                    self.env['file.request.history'].create({
                        'transaction_type': self.transaction_type,
                        'transaction_date': fields.Date.today(),
                        'ref_number': self.name,
                        'file_id': new_file.id,
                    })
                    # file = self.env['file'].create({
                    #     'project_type': self.project_type,
                    #     'from_open_file': True,
                    #     'add_custom_value': True,
                    #     'investment_adjustment': False,
                    #     'tracking_id': rec.investor_file_id.name,
                    #     'membership_id': self.transferee_partner_id.id,
                    #     'membership_name': self.transferee_partner_id.name,
                    #     'booking_date': rec.investor_file_id.booking_date,
                    #     'investor_id': self.investor_id.id,
                    #     'investment_id': self.investment_id.id,
                    #     'investor_file': rec.investor_file_id.id,
                    #     'file_type': 'new',
                    #     'type': 'investor',
                    #     'state': 'available',
                    #     'society_id': rec.investor_file_id.society_id.id,
                    #     'phase_id': rec.investor_file_id.phase_id.id,
                    #     'sector_id': rec.investor_file_id.sector_id.id,
                    #     'street_id': rec.investor_file_id.street_id.id,
                    #     'category_id': rec.investor_file_id.category_id.id,
                    #     'unit_category_type_id': rec.investor_file_id.unit_category_type_id.id,
                    #     'size_id': rec.investor_file_id.size_id.id,
                    #     'unit_class_id': rec.investor_file_id.unit_class_id.id,
                    #     'inventory_id': rec.investor_file_id.inventory_id.id,
                    #     'unit_number': rec.investor_file_id.unit_number,
                    #     'payment_type': 'installments' if rec.investor_file_id.investment_id.options == 'down' else 'lump_sum',
                    #     'interval_id': rec.investor_file_id.interval_id.id,
                    #     'starting_date': rec.investor_file_id.starting_date,
                    #     'total_installment': rec.investor_file_id.total_installment,
                    #     'payment_states': 'open' if rec.investor_file_id.investment_id.options == 'down' else 'close',
                    #     'overall_status': 'open' if rec.investor_file_id.investment_id.options == 'down' else 'close',
                    #     'sale_amount': rec.investor_file_id.sale_amount,
                    #     'custom_sale_amount': rec.investor_file_id.sale_amount,
                    #     'ttl_sale_amount': rec.investor_file_id.ttl_sale_amount,
                    #     'net_sale_amount': rec.investor_file_id.net_sale_amount,
                    #     'initial_payment': rec.investor_file_id.initial_payment,
                    # })
                    #
                    # self.investment_id.amount_paid = self.investment_id.amount_paid - self.investment_id.investor_unit_price
                    # file.investment_adjustment = True
                    # # Creating down payment on file which is already paid by investor
                    # file.installment_plan_ids.create({
                    #     'date': rec.investor_file_id.booking_date,
                    #     'payment_date': rec.investor_file_id.booking_date,
                    #     'installment_type': 'down',
                    #     'invoice': 'Paid By Investor',
                    #     'invoice_created': True,
                    #     'investor_payment': True,
                    #     'installment_number': 0,
                    #     'amount': rec.investor_file_id.initial_payment,
                    #     'amount_paid': rec.investor_file_id.initial_payment,
                    #     'residual': 0,
                    #     'payment_status': 'paid',
                    #     'file_id': file.id
                    # })
                    #
                    # rec.investor_file_id.state = 'issued'
                    # rec.investor_file_id.inventory_id.state = 'sold'
                    # rec.investor_file_id.is_transferee_partner = True
                    # rec.investor_file_id.transferee_name = self.transferee_name
                    # rec.investor_file_id.transferee_partner_id = self.transferee_partner_id.id
                    # rec.investor_file_id.transferee_relation_name = self.transferee_relation_name
                    # rec.investor_file_id.transferee_cnic_number = self.transferee_cnic_number
                    #
                    # if self.investment_id.options == 'down':
                    #     investment_history = file.investment_id.investment_history_ids.create({
                    #         'installment_number': file.investment_id.investment_history_ids[-1].installment_number + 1 if file.investment_id.investment_history_ids[-1]
                    #         else 1,
                    #         'date': fields.Date.today(),
                    #         'transaction_type': 'customer',
                    #         'file_id': file.id,
                    #         'amount': round((file.investment_id.investment_history_ids[
                    #                              -1].new_balance / file.investment_id.total_installment)),
                    #         'new_amount': round(((file.investment_id.investment_history_ids[
                    #                                   -1].new_balance - file.balance_amount) / file.investment_id.remaining_installments)),
                    #         'old_balance': file.investment_id.investment_history_ids[-1].new_balance,
                    #         'new_balance': file.investment_id.investment_history_ids[
                    #                            -1].new_balance - file.balance_amount,
                    #         'investment_id': file.investment_id.id,
                    #     })
                    #
                    #     # Creating installments on files which are already paid by investor
                    #     installment_number = 1
                    #     for line in file.investment_id.investment_plan_ids:
                    #         if line.invoice_created and line.installment_type == 'installment':
                    #             file.installment_plan_ids.create({
                    #                 'date': line.date,
                    #                 'payment_date': line.payment_date,
                    #                 'installment_type': 'installment',
                    #                 'invoice': 'Paid By Investor',
                    #                 'invoice_created': True,
                    #                 'investor_payment': True,
                    #                 'installment_number': installment_number,
                    #                 'amount': round(file.balance_amount / file.investment_id.total_installment),
                    #                 'amount_paid': round(file.balance_amount / file.investment_id.total_installment),
                    #                 'residual': 0,
                    #                 'payment_status': 'paid',
                    #                 'file_id': file.id
                    #             })
                    #             installment_number = installment_number + 1
                    #         if not line.invoice_created and line.balance_amount > 0:
                    #             line.update({'file_adjusted_amount': line.file_adjusted_amount + (
                    #                     file.balance_amount / file.total_installment),
                    #                          'balance_amount': line.balance_amount - (
                    #                                  file.balance_amount / file.total_installment),
                    #                          'residual': line.balance_amount - (
                    #                                  file.balance_amount / file.total_installment)})
                    #
                    #     file.create_installment_plan()

                self.file_id.state = 'available'
                self.state = 'approve'
                self.investment_id.update_investment_related_payment_data()

            elif self.transaction_type == 'change_amount':

                due_invoices = self.investment_id.investment_plan_ids.filtered(
                    lambda l: l.invoice_created == True and l.payment_status != 'paid')
                available_installments = self.investment_id.investment_plan_ids.filtered(
                    lambda l: l.invoice_created != True and l.balance_amount > 0)
                old_price = sum(self.unit_swapping_request_lines.mapped('investor_unit_price'))
                new_price = sum(self.unit_swapping_request_lines.mapped('new_price'))

                if all(self.investment_id.investment_plan_ids.mapped('invoice_created')):
                    if new_price > old_price:
                        adjustment_amount = new_price - old_price
                        prod = [(0, 0, {
                            'product_id': self.env.ref('real_estate.investment_installment').id,
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

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'
            if rec.applicable_on == 'investment':
                for line in rec.unit_swapping_request_lines:
                    line.investor_file_id.state = 'open'
                    line.investor_file_id.issuance_request_created = False
                    line.investor_file_id.issuance_request_id = None
                    line.investor_file_id.is_transferee_partner = False
                    line.investor_file_id.transferee_cnic_number = False
                    line.investor_file_id.transferee_relation_name = False
                    line.investor_file_id.transferee_partner_id = False
            if rec.applicable_on == 'file':
                rec.file_id.state = 'available'

    def old_requests_id_to_file(self):
        request_lines = self.env['unit.swapping.request.lines'].search(
            [('investor_file_id.society_id.company_id.id', '=', 5), ('unit_swapping_request_id.state', '=', 'approve')])
        if request_lines:
            for line in request_lines:
                file = self.env['file'].search([('investor_file', '=', line.investor_file_id.id), ('issuance_request_id', '=', False)])
                if file:
                    file.issuance_request_id = line.unit_swapping_request_id.id

    def change_old_open_file_status(self):
        # request_lines = self.env['unit.swapping.request.lines'].search([('investor_file_id.society_id.company_id.id', '=', 5), ('unit_swapping_request_id.state', 'in', ['draft', 'in_process'])])
        # if request_lines:
        #     for line in request_lines:
        #         file = self.env['investor.file'].search([('id', '=', line.investor_file_id.id)])
        #         if file:
        #             # file.state = 'in_process'
        #             file.issuance_request_created = True
        #             file.issuance_request_id = line.unit_swapping_request_id.id
        all_request_lines = self.env['unit.swapping.request.lines'].search(
            [('investor_file_id.society_id.company_id.id', '=', 5), ('unit_swapping_request_id.state', '!=', 'cancel')])
        if all_request_lines:
            for line in all_request_lines:
                if line.investor_file_id:
                    line.investor_file_id.issuance_request_created = True
                    line.investor_file_id.issuance_request_id = line.unit_swapping_request_id.id

    def change_request_status_query(self):
        request_lines = self.env['unit.swapping.request.lines'].search([('unit_swapping_request_id.society_id.company_id.id', '=', 5)])
        if request_lines:
            for line in request_lines:
                if line.investor_file_id.state == 'in_process':
                    line.unit_swapping_request_id.state = 'printed'
                if line.investor_file_id.state == 'file_printed':
                    line.unit_swapping_request_id.state = 'file_printed'
                if line.investor_file_id.state == 'issued':
                    line.unit_swapping_request_id.state = 'approve'
                if line.investor_file_id.state in ['delivered', 'received']:
                    line.unit_swapping_request_id.state = 'delivered'
                if line.unit_swapping_request_id.state == 'printed':
                    line.investor_file_id.state = 'in_process'

    @api.model
    def validate_issuance_request_date(self):
        # date = self.env.ref('file_financials.ir_cron_file_issuance_request_expiry').till_date or fields.Date.today()
        date = fields.Date.today()
        for rec in self.search([('state', 'in', ['draft', 'in_process', 'printed'])]):
            if rec.validation_date and rec.validation_date < date:
                rec.request_cancel()
                message = f"Request Cancelled as per the Expiry Date"
                rec.message_post(body=message)
