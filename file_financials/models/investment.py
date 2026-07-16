import json
import base64
import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class InvestmentExt(models.Model):
    _inherit = 'investment'
    _description = 'Investment'

    files_created = fields.Boolean(default=False)
    marketing_company_id = fields.Many2one('res.partner', tracking=True)
    # rebate portion
    rebate_id = fields.Many2one('dealer.rebate')
    rebate_on_allotment_ids = fields.One2many('rebate.on.allotment', 'investment_id')
    rebate_amount = fields.Float(tracking=True, compute='calculate_rebate')
    separate_rebate = fields.Float(tracking=True)
    net_of_rebate = fields.Float(tracking=True)
    settlement_date = fields.Date()
    rebate_generated = fields.Boolean(default=False, tracking=True)
    rebate_settlement = fields.Selection([
        ('on_deal_start', 'Deal Start'),
        ('on_deal_close', 'Deal Close')
    ], default="on_deal_close", tracking=True)

    rebate_invoice_ids = fields.Many2many('account.move', tracking=True, string="Rebate Invoices")
    deal_rebate_invoice_created = fields.Boolean(default=False, tracking=True)
    deal_rebate_amount = fields.Float(tracking=True, compute='compute_invoiced_rebate', store=True, compute_sudo=False)
    sale_rebate_amount = fields.Float(tracking=True, compute='compute_invoiced_rebate', store=True, compute_sudo=False)
    invoiced_rebate_amount = fields.Float(tracking=True, compute='compute_invoiced_rebate', string="Total Rebate", store=True,
                                          compute_sudo=False)
    paid_rebate_amount = fields.Float(tracking=True, string="Rebate Paid")
    payable_rebate_amount = fields.Float(tracking=True, string="Rebate Remaining")
    total_rebate_amount = fields.Float(string="Total Rebate Amount", compute='calculate_rebate', store=True)
    dealer_rebate_amount = fields.Float(string="Dealer Rebate", compute='calculate_rebate', store=True)
    marketing_rebate_amount = fields.Float(string="Marketing Rebate", compute='calculate_rebate', store=True)
    down_payment = fields.Float('Booking Payment', required=True, tracking=True)
    balloting_amount = fields.Float()
    primary_amount = fields.Float()
    possession_amount = fields.Float()
    confirmation_amount = fields.Float()
    balloon_payment = fields.Float()
    deal_close_date = fields.Date(string='Deal Close Date')
    show_in_portal = fields.Boolean(default=False, string="Show in Portal")
    allow_old_prices = fields.Boolean(default=False, string="Allow Old Prices")
    allow_request_print = fields.Boolean(default=False, string="Allow Request Printing")
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch)
    launch_type_id = fields.Many2one('launch.type', string="Launch Type")

    multiple_plans = fields.Boolean(default=False, string="Multiple Plans")
    platter_id = fields.Many2one('investment.platter', string="Platter")
    payment_type = fields.Selection([('installments', 'Installment'), ('lump_sum', 'Lump Sum')], string='Payment Type',
                                    tracking=True)

    files_to_show = fields.Selection([
        ('paid', 'Paid'),
        ('all', 'All')
    ], default="all", tracking=True, string="Files to Show", required=True)
    allow_not_paid_requests = fields.Boolean(default=False, string="Allow Not Paid Requests", tracking=True)
    # payment_plan_ids = fields.One2many('payment.plan', 'investment_id', string="Payment Plan", tracking=True)
    development_charges_included = fields.Selection(
        string='Development Charges Included',
        selection=[('yes', 'Yes'), ('no', 'no')],
        default="yes",
        tracking=True)

    def reserve_inventory(self):
        # real_estate's base reserve_inventory() sets line.partner_id = self.partner_id.id,
        # assuming both are res.member. Here partner_id is res.investor (Dealer), so that
        # assignment is a cross-model id mismatch (plot.inventory.partner_id expects res.member,
        # the plot's owner). investment_id already links the plot to the Dealer via
        # investment_id.partner_id, so we replicate the method without that bad assignment.
        for rec in self:
            if rec.inventory_ids:
                for line in rec.inventory_ids:
                    if line:
                        line.state = 'investor'
                        line.investment_id = rec.id
            elif not rec.investment_line_ids:
                raise ValidationError(_('Please add inventory details.'))
        self.state = 'reserved'

    def set_net_payment_data(self):
        # confirmation_lines = self.env['investment.plan'].search([('installment_name', '=', 'Confirmation'), ('investment_id', '=', rec.id), ('company_id.id', '=', 5)])
        # if confirmation_lines:
        #     for line in confirmation_lines:
        #         line.compute_net_payment()
        for rec in self:
            booking_lines = self.env['investment.plan'].search(
                [('installment_type', '=', 'down'), ('investment_id', '=', rec.id), ('company_id.id', 'in', [5, 16])])
            if booking_lines:
                for line in booking_lines:
                    line.compute_net_receivable()
                    line.compute_net_payment()

    @api.onchange('platter_id')
    def fetch_and_populate_platter_data(self):
        if self.platter_id:
            if self.investment_line_ids:
                for line in self.investment_line_ids:
                    line.unlink()
            # for lines in self.platter_id.platter_line_ids:
            # self.investment_line_ids.create({
            self.investment_line_ids = False
            if self.reservation_type == 'bulk':
                self.investment_line_ids = [(0, 0, {
                    'sector_id': lines.sector_id.id,
                    'street_id': lines.street_id.id,
                    'size_id': lines.size_id.id,
                    'unit_category_type_id': lines.unit_category_type_id.id,
                    'unit_class_id': lines.unit_class_id.id,
                    'category_id': lines.category_id.id,
                    'inventory_id': lines.inventory_id.id,
                    'no_of_units': lines.no_of_units,
                    'list_price': lines.list_price,
                    'price_list_id': lines.price_list_id.id,
                    'investor_price': lines.investor_price,
                    'deal_price': lines.deal_price,
                    'own_plan': lines.own_plan,
                    'predefine_plan_id': lines.predefine_plan_id.id,
                    'booking_value': lines.booking_value,
                    'confirmation_value': lines.confirmation_value,
                    'posession_value': lines.posession_value,
                    'balloting_value': lines.balloting_value,
                    'final_value': lines.final_value,
                    'investment_id': self.id,
                }) for lines in self.platter_id.platter_line_ids]
            elif self.reservation_type == 'unit':
                self.inventory_ids = self._pick_platter_inventory()
                self.down_payment = sum(self.platter_id.platter_line_ids.mapped('booking_value'))

    def _pick_platter_inventory(self):
        """Auto-select available plot.inventory matching each platter line's
        criteria and quantity (no_of_units), for reservation_type == 'unit'."""
        self.ensure_one()
        PlotInventory = self.env['plot.inventory']
        picked = PlotInventory
        for line in self.platter_id.platter_line_ids:
            if line.inventory_id:
                line_units = line.inventory_id if line.inventory_id.state == 'avalible_for_sale' else PlotInventory
            else:
                domain = [('state', '=', 'avalible_for_sale'), ('id', 'not in', picked.ids)]
                for field_name in ('sector_id', 'street_id', 'category_id', 'unit_category_type_id', 'size_id', 'unit_class_id'):
                    value = line[field_name]
                    if value:
                        domain.append((field_name, '=', value.id))
                line_units = PlotInventory.search(domain, limit=line.no_of_units or 1)
            line_units.investor_unit_price = line.investor_price
            picked |= line_units
        return picked

    def rebate_invoices(self):
        if self.rebate_on_allotment_ids:
            return {
                'type': 'ir.actions.act_window',
                'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                          (self.env.ref('account.view_move_form').id, 'form')],
                'view_mode': 'list,form',
                'name': _('Rebate Invoices'),
                'res_model': 'account.move',
                'domain': [('id', 'in', self.rebate_on_allotment_ids.mapped('move_id.id'))],
                'context': {'default_name': self.name},
            }

    @api.onchange('multiple_plans')
    def change_values_in_investment_lines(self):
        if self.multiple_plans:
            for line in self.investment_line_ids:
                line.own_plan = True
                # if self.predefine_plan_id:
                #     line.predefine_plan_id = self.predefine_plan_id.id
        else:
            for line in self.investment_line_ids:
                line.own_plan = False
                line.predefine_plan_id = False

    @api.onchange('investment_line_ids', 'total_amount', 'multiple_plans')
    def change_booking_and_confirmation(self):
        if self.investment_line_ids and self.multiple_plans and self.reservation_type == 'bulk':
            booking_amount = 0
            confirmation_amount = 0
            balloting_amount = 0
            posession_amount = 0
            final_amount = 0
            balloon_amount = 0
            for line in self.investment_line_ids:
                line.own_plan = True
                booking_amount += line.booking_value
                confirmation_amount += line.confirmation_value
                balloting_amount += line.balloting_value
                posession_amount += line.posession_value
                final_amount += line.final_value
                balloon_amount += line.balloon_value
            self.down_payment = booking_amount
            # if self.options == 'full':
            #     self.down_payment = self.total_amount
            self.confirmation_amount = confirmation_amount
            self.balloting_amount = final_amount
            self.possession_amount = posession_amount
            self.primary_amount = balloting_amount
            self.balloon_payment = balloon_amount
        else:
            self._onchange_total_amount()

    def create_open_file(self):
        # open files copy payment_type from the investment but interval/installments
        # from the options, so a mismatched pair produces broken open files that
        # cannot generate an installment plan
        if self.options == 'full' and self.payment_type == 'installments':
            raise ValidationError(_(
                "Investment option 'Full Payment' cannot be combined with payment type "
                "'Installment'. Set Payment Type to 'Lump Sum', or use option 'Down Payment'."))
        if self.options == 'down' and self.payment_type == 'lump_sum':
            raise ValidationError(_(
                "Investment option 'Down Payment' cannot be combined with payment type "
                "'Lump Sum'. Set Payment Type to 'Installment', or use option 'Full Payment'."))
        inventory = self.env['plot.inventory'].search([('investment_id', '=', self.id)])
        prorate = self.down_payment / self.total_amount
        investor_file = self.env['investor.file']
        if self.reservation_type == 'bulk':
            for lines in self.investment_line_ids:
                for open_files in range(lines.no_of_units):
                    vals = {
                        'investor_id': self.partner_id.id,
                        'investment_id': self.id,
                        'development_charges_included': self.development_charges_included,
                        'state': 'open',
                        'society_id': self.society_id.id,
                        'phase_id': self.phase_id.id,
                        'sector_id': lines.sector_id.id,
                        'street_id': lines.street_id.id,
                        'category_id': lines.category_id.id,
                        'unit_category_type_id': lines.unit_category_type_id.id,
                        'size_id': lines.size_id.id,
                        # 'unit_class_id': inv.unit_class_id.id,
                        # 'inventory_id': inv.id,
                        # 'unit_number': inv.name,
                        # 'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                        'payment_type': self.payment_type,
                        'plan_type': self.plan_type,
                        'predefine_plan_id': lines.predefine_plan_id.id if lines.own_plan else self.predefine_plan_id.id,
                        'interval_id': lines.predefine_plan_id.interval_id.id if lines.own_plan else self.interval_id.id,
                        # 'starting_date': self.start_date,
                        'booking_date':self.booking_date,
                        'starting_date':self.installment_starting_date or self.start_date,
                        'total_installment': lines.predefine_plan_id.total_installment if lines.own_plan else self.total_installment,
                        'payment_states': 'open',
                        'sale_amount': lines.investor_price,
                        'ttl_sale_amount': lines.investor_price,
                        'net_sale_amount': lines.investor_price,
                        'initial_payment': round(
                            lines.investor_price * prorate) if self.options == 'down' else 0,
                        'balance_amount': lines.investor_price - round(
                            lines.investor_price * prorate) if self.options == 'down' else lines.investor_price,
                    }
                    investor_file.create(vals)
        else:
            for inv in inventory:
                vals = {
                    'investor_id': self.partner_id.id,
                    'investment_id': self.id,
                    'development_charges_included': self.development_charges_included,
                    'state': 'open',
                    'society_id': self.society_id.id,
                    'phase_id': self.phase_id.id,
                    'sector_id': inv.sector_id.id,
                    'street_id': inv.street_id.id,
                    'category_id': inv.category_id.id,
                    'unit_category_type_id': inv.unit_category_type_id.id,
                    'size_id': inv.size_id.id,
                    'unit_class_id': inv.unit_class_id.id,
                    'inventory_id': inv.id,
                    # 'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                    'plan_type': self.plan_type,
                    'predefine_plan_id': self.predefine_plan_id.id if self.predefine_plan_id else None,
                    'payment_type': self.payment_type,
                    'interval_id': self.interval_id.id if self.options == 'down' else False,
                    'starting_date': self.start_date,
                    'total_installment': self.total_installment if self.options == 'down' else 0,
                    'payment_states': 'open',
                    'sale_amount': inv.investor_unit_price,
                    'ttl_sale_amount': inv.investor_unit_price,
                    'net_sale_amount': inv.investor_unit_price,
                    'initial_payment': round(
                        inv.investor_unit_price * prorate) if self.options == 'down' else inv.investor_unit_price,
                    'balance_amount': inv.investor_unit_price - round(
                        inv.investor_unit_price * prorate) if self.options == 'down' else 0,
                }
                open_file = investor_file.create(vals)
                inv.investor_file_id = open_file.id
        self.update_booking_amount_on_open_files()
        self.files_created = True

    @api.depends('rebate_invoice_ids')
    def compute_invoiced_rebate(self):
        for rec in self:
            rec.invoiced_rebate_amount = 0
            rec.payable_rebate_amount = 0
            rec.paid_rebate_amount = 0
            if rec.rebate_invoice_ids:
                rec.invoiced_rebate_amount = sum(
                    inv.amount_total for inv in rec.rebate_invoice_ids.filtered(lambda invoice: invoice.state not in ('draft', 'cancel')))
                rec.payable_rebate_amount = sum(
                    inv.amount_residual for inv in
                    rec.rebate_invoice_ids.filtered(lambda invoice: invoice.state not in ('draft', 'cancel')))
                rec.paid_rebate_amount = rec.invoiced_rebate_amount - rec.payable_rebate_amount

    @api.constrains('rebate_on_allotment_ids')
    def category_constrains(self):
        for rec in self:
            net_off_data = self.rebate_on_allotment_ids.filtered(lambda s: s.settlement_option == 'net_off')
            if rec.rebate_settlement == 'on_deal_close' and len(net_off_data) >= 1:
                raise ValidationError(
                    _(f"You can't apply 'NET OFF' rebate in line when settlement type is Deal Close"))

    @api.onchange('rebate_id')
    def onchange_rebate(self):
        self.rebate_on_allotment_ids = [(5,)]
        if self.rebate_id:
            self.rebate_on_allotment_ids = [(0, 0, {
                'settlement_option': rec.settlement_option,
                'calculation_basis': rec.calculation_basis,
                'rate_calculation': rec.rate_calculation,
                'total_rebate': rec.total_rebate,
                'rebate_at_deal': rec.rebate_at_deal,
                'rebate_at_sale': rec.rebate_at_sale,
                'marketing_rebate_percentage': rec.marketing_rebate_percentage,
                'dealer_rebate_percentage': rec.dealer_rebate_percentage,
                'category_id': rec.category_id,
                'sector_id': rec.sector_id,
                'partner_id': rec.partner_id,
                'agent_type': rec.agent_type,
                'transaction_type': rec.transaction_type,
            }) for rec in self.rebate_id.rebate_line_ids]
        self.calculate_rebate()

    def calculate_fix_rebate(self, rec):
        record = self.env['investor.file'].search([('investment_id', '=', self.id)])
        calculated_rebate = 0.0
        # filtered out the required data from allotment lines
        if rec.sector_id:
            record = record.filtered(lambda line: line.category_id == rec.category_id and line.sector_id == rec.sector_id)
        if not rec.sector_id:
            record = record.filtered(lambda line: line.category_id == rec.category_id)
        if rec.rate_calculation == 'per_file':
            total_files = len(record)
            calculated_rebate = (total_files * rec.rebate_at_deal)
            for rebate in record:
                rebate.rebate_amount = rec.total_rebate
                if rec.rebate_at_sale > 0:
                    rebate.sale_rebate = rec.rebate_at_sale
                    rebate.is_sale_rebate_applied = True
        return calculated_rebate

    def calculate_percentage_rebate(self, rec):
        record = self.env['investor.file'].search([('investment_id', '=', self.id)])
        if rec.sector_id:
            record = record.filtered(lambda line: line.category_id == rec.category_id and line.sector_id == rec.sector_id)
        if not rec.sector_id:
            record = record.filtered(lambda line: line.category_id == rec.category_id)
        calculated_rebate = 0.0
        per_file_rebate = 0.0

        if rec.rate_calculation == 'per_marla':
            for file in record:
                file_area = file.unit_category_type_id.area_marla
                file_amount = file.sale_amount
                per_marla_amount = file_amount / file_area
                per_marla_rebate_value = per_marla_amount * (rec.rebate_at_deal / 100)
                rebate_value_of_file = per_marla_rebate_value * file_area
                calculated_rebate += rebate_value_of_file
                # per file rebate calculation
                per_file_rebate = file_area * (per_marla_amount * (rec.total_rebate / 100))
                file.rebate_amount = per_file_rebate
                if rec.rebate_at_sale > 0:
                    file.sale_rebate = (file_area * (per_marla_amount * (rec.rebate_at_sale / 100)))
                    file.is_sale_rebate_applied = True

        elif rec.rate_calculation == 'per_file':
            for file in record:
                file_amount = file.sale_amount
                rebate_value = file_amount * (rec.rebate_at_deal / 100)
                calculated_rebate += rebate_value
                per_file_rebate = (file_amount * (rec.total_rebate / 100))
                file.rebate_amount = per_file_rebate
                if rec.rebate_at_sale > 0:
                    file.sale_rebate = (file_amount * (rec.rebate_at_sale / 100))
                    file.is_sale_rebate_applied = True
        return calculated_rebate

    def calculate_rebate(self):
        for recs in self:
            recs.net_of_rebate = recs.separate_rebate = 0
            files_rebate = 0
            deal_rebate = 0
            dealer_rebate = 0
            marketing_rebate = 0
            # if recs.rebate_settlement == 'on_deal_start':
            #     for rec in recs.rebate_on_allotment_ids:
            #         if rec.settlement_option == 'net_off':
            #             if rec.calculation_basis == 'fix':
            #                 calculated_rebate = recs.calculate_fix_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += rec.rebate_at_deal
            #                 marketing_rebate += rec.marketing_rebate_percentage
            #                 dealer_rebate += rec.dealer_rebate_percentage
            #                 # recs.net_of_rebate = recs.net_of_rebate + calculated_rebate
            #             elif rec.calculation_basis == 'percentage':
            #                 calculated_rebate = recs.calculate_percentage_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += recs.total_amount * (rec.rebate_at_deal / 100)
            #                 # recs.net_of_rebate = recs.net_of_rebate + calculated_rebate
            #                 marketing_rebate += recs.total_amount * (rec.marketing_rebate_percentage / 100)
            #                 dealer_rebate += recs.total_amount * (rec.dealer_rebate_percentage / 100)
            #
            #         elif rec.settlement_option == 'separate':
            #             if rec.calculation_basis == 'fix':
            #                 calculated_rebate = recs.calculate_fix_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += rec.rebate_at_deal
            #                 # recs.separate_rebate = recs.separate_rebate + calculated_rebate
            #                 marketing_rebate += rec.marketing_rebate_percentage
            #                 dealer_rebate += rec.dealer_rebate_percentage
            #
            #             elif rec.calculation_basis == 'percentage':
            #                 calculated_rebate = recs.calculate_percentage_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += recs.total_amount * (rec.rebate_at_deal / 100)
            #                 # recs.separate_rebate = recs.separate_rebate + calculated_rebate
            #                 marketing_rebate += recs.total_amount * (rec.marketing_rebate_percentage / 100)
            #                 dealer_rebate += recs.total_amount * (rec.dealer_rebate_percentage / 100)
            # elif recs.rebate_settlement == 'on_deal_close':
            #     for rec in recs.rebate_on_allotment_ids:
            #         if rec.settlement_option == 'separate':
            #             if rec.calculation_basis == 'fix':
            #                 calculated_rebate = recs.calculate_fix_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += rec.rebate_at_deal
            #                 # recs.separate_rebate = recs.separate_rebate + calculated_rebate
            #                 marketing_rebate += rec.marketing_rebate_percentage
            #                 dealer_rebate += rec.dealer_rebate_percentage
            #
            #             elif rec.calculation_basis == 'percentage':
            #                 calculated_rebate = recs.calculate_percentage_rebate(rec)
            #                 files_rebate += calculated_rebate
            #                 deal_rebate += recs.total_amount * (rec.rebate_at_deal / 100)
            #                 # recs.separate_rebate = recs.separate_rebate + calculated_rebate
            #                 marketing_rebate += recs.total_amount * (rec.marketing_rebate_percentage / 100)
            #                 dealer_rebate += recs.total_amount * (rec.dealer_rebate_percentage / 100)

            # recs.rebate_amount = recs.net_of_rebate + recs.separate_rebate
            # if recs.rebate_settlement == 'on_deal_close':
            if recs.rebate_id and recs.rebate_on_allotment_ids:
                for line in recs.rebate_on_allotment_ids:
                    if line.agent_type == 'dealer':
                        if line.calculation_basis == 'percentage':
                            dealer_rebate += recs.total_amount * (line.total_rebate / 100)
                        if line.calculation_basis == 'fix':
                            dealer_rebate += line.total_rebate
                    if line.agent_type == 'marketing_company':
                        if line.calculation_basis == 'percentage':
                            marketing_rebate += recs.total_amount * (line.total_rebate / 100)
                        if line.calculation_basis == 'fix':
                            marketing_rebate += line.total_rebate
            recs.deal_rebate_amount = deal_rebate
            recs.sale_rebate_amount = files_rebate
            recs.rebate_amount = deal_rebate + files_rebate
            recs.dealer_rebate_amount = dealer_rebate
            recs.marketing_rebate_amount = marketing_rebate
            recs.total_rebate_amount = dealer_rebate + marketing_rebate

    def create_deal_rebate_bill(self):
        if not self.deal_rebate_amount > 0:
            raise ValidationError('Sorry, Cannot Create Rebate Invoice for Zero (0) Amount')
        if self.rebate_settlement == 'on_deal_close':
            if self.investment_plan_ids[0].installment_type == 'down' and self.investment_plan_ids[0].payment_status != 'paid':
                raise ValidationError('Please Pay your Booking Payment First...')
        if self.rebate_on_allotment_ids and not self.deal_rebate_invoice_created:
            rebate_type = self.rebate_on_allotment_ids[0].mapped('settlement_option')
            invoice_type = ''
            date = fields.Date.today()
            if rebate_type[0] == 'separate':
                invoice_type = 'in_invoice'
                date = self.booking_date
            else:
                invoice_type = 'out_refund'

            rebate_invoice = self.env['account.move'].create({
                'partner_id': self.partner_id.partner_id.id,
                # 'branch_id': self.env.branch.id,
                'type': invoice_type,
                'investment_id': self.id,
                'invoice_date': date,
                'property_invoice_type': 'dealer_rebate',
                # 'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                    'name': self.env.ref('unit_booking.dealer_rebate').name,
                    'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                    'price_unit': self.deal_rebate_amount,
                })],
            })
            rebate_invoice.action_post()
            self.rebate_invoice_ids = [(4, rebate_invoice.id)]
            self.deal_rebate_invoice_created = True

    def compute_rebate_amount_process(self):
        for rec in self:
            for lines in rec.investment_plan_ids:
                if lines.installment_type == 'down':
                    marketing_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'marketing_company' and l.transaction_type == 'booking')
                    dealer_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'dealer' and l.transaction_type == 'booking')
                    lines.marketing_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * rec.no_of_units
                        for l in marketing_lines
                    )
                    lines.dealer_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * rec.no_of_units
                        for l in dealer_lines
                    )
                    lines.rebate_amount = lines.marketing_share + lines.dealer_share
                if lines.installment_type == 'confirmation_amount':
                    marketing_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'marketing_company' and l.transaction_type == 'confirmation')
                    dealer_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'dealer' and l.transaction_type == 'confirmation')
                    lines.marketing_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * rec.no_of_units
                        for l in marketing_lines
                    )
                    lines.dealer_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * rec.no_of_units
                        for l in dealer_lines
                    )
                    lines.rebate_amount = lines.marketing_share + lines.dealer_share
            open_files = self.env['investor.file'].search([('investment_id', '=', rec.id)])
            if open_files:
                for file in open_files:
                    file.compute_rebate_amount()
                    if file.installment_plan_ids:
                        for plan_line in file.installment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation' and l.move_ids):
                            plan_line.calculate_rebate_given()
            confirmation_plan_line = rec.investment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation_amount')
            confirmation_plan_line.calculate_rebate_given_for_confirmation()

    def create_dealer_booking_rebate_bill(self):
        if self.investment_plan_ids.filtered(lambda ins: ins.installment_type == 'down' and ins.dealer_share > 0):
            dealer_share = self.investment_plan_ids.filtered(lambda ins: ins.installment_type == 'down').dealer_share
            if dealer_share > 0:
                date = fields.Date.today()
                invoice_type = 'out_refund'
                rebate_invoice = self.env['account.move'].create({
                    'partner_id': self.partner_id.partner_id.id,
                    'company_id': self.company_id.id,
                    # 'branch_id': self.env.branch.id,
                    'type': invoice_type,
                    'ref': self.name + 'INV',
                    'investment_id': self.id,
                    'invoice_date': date,
                    'property_invoice_type': 'dealer_rebate',
                    # 'journal_id': self.env.company.account_journal_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('unit_booking.dealer_rebate').id,
                        'name': self.env.ref('unit_booking.dealer_rebate').name,
                        'account_id': self.env.ref('unit_booking.dealer_rebate').property_account_income_id.id,
                        'price_unit': dealer_share,
                    })],
                })
                rebate_invoice.action_post()
                self.investment_plan_ids.filtered(lambda ins: ins.installment_type == 'down').move_ids = [(4, rebate_invoice.id)]
            self.investment_plan_ids.filtered(lambda ins: ins.installment_type == 'down').calculate_rebate_given_for_confirmation()

    def receive_payment(self):
        if not self.investment_plan_ids:
            raise ValidationError(_('Create Installment Plan first.'))
        if self.token_id and not self.token_id.token_paid:
            raise ValidationError(_('Please pay fees against this Token: %s .') % self.token_id.serial_number)
        if self.total_amount:
            _inv_ref = self.env.ref('real_estate.investment')
            first_plan = self.investment_plan_ids.filtered(lambda l: l.installment_number == 1)
            invoice_lines = [(0, 0, {
                'product_id': _inv_ref.id,
                'name': _inv_ref.name,
                # property_account_income_id is company_dependent and this product is
                # shared across every company — always resolve it through this
                # investment's own company, never the ambient env.company.
                'account_id': _inv_ref.with_company(self.company_id or self.env.company).property_account_income_id.id,
                'quantity': 1.0,
                'price_unit': self.down_payment if self.options == 'down' else self.total_amount,
            })]
            token_fees = 0
            if self.token_id and self.token_id.state == 'paid':
                # the investor already paid the token; knock it off the booking
                token_fees = self.token_id.token_fees
                _token_ref = self.env.ref('real_estate.token_adjustment')
                invoice_lines.append((0, 0, {
                    'product_id': _token_ref.id,
                    'name': _token_ref.name,
                    'account_id': _token_ref.with_company(
                        self.company_id or self.env.company).property_account_income_id.id,
                    'quantity': 1.0,
                    'price_unit': -token_fees,
                }))
            inv = self.env['midland.invoice'].create({
                'partner_id': self.partner_id.partner_id.id,
                'invoice_date': self.booking_date,
                'property_invoice_type': 'investment',
                'investment_id': self.id,
                'investment_installment_id': first_plan.id if first_plan else False,
                'invoice_line_ids': invoice_lines,
            })
            inv.action_post()
            if token_fees:
                self.token_id.state = 'adjusted'
                if first_plan:
                    # the token was received in advance; settle its share of the
                    # Booking plan line so only the net amount stays receivable
                    new_paid = (first_plan.amount_paid or 0.0) + token_fees
                    remaining = (first_plan.amount or 0.0) - new_paid
                    first_plan.write({
                        'amount_paid': min(new_paid, first_plan.amount),
                        'residual': max(remaining, 0.0),
                        'payment_status': 'paid' if remaining <= 0 else 'in_payment',
                    })

            for rec in self.investment_plan_ids:
                if rec.installment_number == 1 and rec.invoice_created != True:
                    rec.write({
                        'invoice_created': True,
                        'invoice_id': inv.jv_id.id if inv.jv_id else False,
                    })

            payment_type = self.env.company.payment_type
            if payment_type:
                if payment_type == 'osp':
                    # the token portion was already received with the token itself
                    net_amount = self.down_payment - token_fees
                    if net_amount > 0:
                        payment = self.env['midland.payment'].create({
                            'partner_id': self.partner_id.partner_id.id,
                            'investment_id': self.id,
                            'payment_amount': net_amount,
                            'currency_id': self.env.company.currency_id.id,
                            'journal_id': self.journal_id.id or self.env.company.account_journal_id.id,
                            'company_id': self.env.company.id,
                            'remarks': inv.name,
                            'invoice_line_ids': [(0, 0, {
                                'invoice_id': inv.id,
                                'payment_amount': net_amount,
                            })],
                        })
                        payment.action_confirm()

            self.amount_received = True
            for rec in self:
                # if rec.investment_line_ids and rec.state != 'reserved':
                #     for line in rec.investment_line_ids:
                #         for unit in range(0, line.no_of_units):
                #             inventory = rec.env['plot.inventory'].search([
                #                 ('society_id', '=', rec.society_id.id),
                #                 ('phase_id', '=', rec.phase_id.id),
                #                 ('sector_id', '=', line.sector_id.id),
                #                 ('category_id', '=', line.category_id.id),
                #                 ('unit_category_type_id', '=', line.unit_category_type_id.id),
                #                 ('state', '=', 'avalible_for_sale'),
                #             ], limit=1)
                #             if inventory:
                #                 inventory.state = 'investor'
                #                 inventory.investment_id = self.id
                #                 inventory.partner_id = self.partner_id.id
                #                 inventory.investor_unit_price = line.investor_price
                #             else:
                #                 raise ValidationError("Inventory you are trying to reserve is not available.")
                if rec.inventory_ids and rec.state != 'reserved':
                    for line in rec.inventory_ids:
                        if line:
                            line.state = 'investor'
                            line.investment_id = self.id
                            # line.deal_price = line.deal_price
                if rec.reservation_type != 'unit' and not rec.investment_line_ids:
                    raise ValidationError('Please add inventory details.')
                if rec.reservation_type == 'unit' and not rec.inventory_ids:
                    raise ValidationError('Please add inventory details.')

            self.investment_history_ids.create({
                'installment_number': 1,
                'date': fields.Date.today(),
                'transaction_type': 'investor',
                'amount': 0,
                'new_amount': round(self.balance_amount / self.total_installment) if self.total_installment > 0 else 0,
                'old_balance': self.total_amount,
                'new_balance': round(self.balance_amount),
                'payment_received': 0,
                'investment_id': self.id,
            })
            self.state = 'payment'
            self.payment_states = 'open'
        self.compute_rebate_amount_process()
        self.create_dealer_booking_rebate_bill()

    def create_installment_plan(self):
        if self.payment_type == 'installments' and not self.down_payment:
            raise ValidationError('Please enter booking payment amount.')

        if self.payment_type == 'installments':
            # Clear lines that are neither invoiced nor paid before regenerating,
            # so re-running the plan does not duplicate them
            existing = self.investment_plan_ids.filtered(
                lambda l: not l.invoice_created and l.payment_status not in ('in_payment', 'paid'))
            if existing:
                existing.unlink()
            self.installment_created = False

            # refresh schedule parameters from the plan lines, so a plan edited
            # after the investment was created still schedules correctly
            if self.predefine_plan_id:
                for pre_plan in self.predefine_plan_id.predefine_plan_line_ids:
                    product_id = pre_plan.product_id.id
                    if product_id == self.env.ref('real_estate.balloon_payment').id:
                        self.balloon_payment_interval = pre_plan.interval
                        self.balloon_payment_frequency = pre_plan.frequency
                        self.balloon_payment_start = pre_plan.start_from
                        self.include_installment = pre_plan.include_installment
                    if product_id == self.env.ref('real_estate.additional_balloon').id:
                        self.add_balloon_interval = pre_plan.interval
                        self.add_balloon_frequency = pre_plan.frequency
                    if product_id == self.env.ref('real_estate.possession_amount_product').id:
                        self.possession_amount_interval = pre_plan.interval
                        self.possession_amount_frequency = pre_plan.frequency
                    if product_id == self.env.ref('real_estate.confirmation_amount_product').id:
                        self.confirmation_amount_interval = pre_plan.interval
                        self.confirmation_amount_frequency = pre_plan.frequency
                    if product_id == self.env.ref('real_estate.balloting_product').id:
                        self.primary_amount_interval = pre_plan.interval
                        self.primary_amount_frequency = pre_plan.frequency

            self.investment_plan_ids.create({
                'date': self.booking_date,
                'installment_type': 'down',
                'installment_name': 'Booking',
                'installment_number': 1,
                'amount': self.down_payment,
                'amount_paid': 0,
                'balance_amount': self.down_payment,
                'residual': self.down_payment,
                'payment_status': 'not_paid',
                'investment_id': self.id
            })

            # confirmation payment line

            if self.predefine_plan_id \
                    and self.env.ref('real_estate.confirmation_amount_product').id \
                    in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                installment_number = 3
                # confirmation_date = self.start_date
                confirmation_date = self.booking_date
                if self.grace_period_type == 'days':
                    confirmation_date = self.booking_date + relativedelta(days=+self.grace_period)
                if self.grace_period_type == 'months':
                    confirmation_date = self.booking_date + relativedelta(months=+self.grace_period)
                if self.grace_period_type == 'years':
                    confirmation_date = self.booking_date + relativedelta(years=+self.grace_period)
                self.investment_plan_ids.create({
                    # 'date': self.start_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period),
                    'date': confirmation_date,
                    'installment_number': 2,
                    'installment_type': 'confirmation_amount',
                    'installment_name': 'Confirmation',
                    'payment_status': 'not_paid',
                    'amount_paid': 0,
                    'balance_amount': self.confirmation_amount,
                    'amount': self.confirmation_amount,
                    'residual': self.confirmation_amount,
                    'investment_id': self.id
                })
            else:
                installment_number = 2

            if self.balance_amount > 0:
                # if all([self.installment_starting_date, self.interval_id, self.total_installment]):
                #     start_date = self.installment_starting_date
                if all([self.start_date, self.interval_id, self.total_installment]):
                    start_date = self.start_date
                    dates = [fields.Date.from_string(start_date)]

                    interval = 0
                    possession_interval = 0
                    add_balloon_interval = 0
                    primary_interval = 0
                    # When no explicit "Start From" is configured on the Balloon Payment
                    # plan line (start_from=0, the default), the recurring balloon check
                    # below must be active from the first installment - otherwise it never
                    # fires (0 is falsy) and every balloon slot silently becomes a regular
                    # installment instead.
                    start_balloon_payment = not self.balloon_payment_start
                    installment_count = 1
                    balloon_interval = self.balloon_payment_interval
                    balance = self.balance_amount - self.balloting_amount

                    if self.predefine_plan_id:
                        for rec in self.predefine_plan_id.predefine_plan_line_ids:
                            if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
                                balance = balance - (self.balloon_payment *
                                                     self.balloon_payment_frequency)

                            if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
                                balance = balance - (self.possession_amount * self.possession_amount_frequency)

                            if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
                                balance = balance - (self.confirmation_amount *
                                                     self.confirmation_amount_frequency)

                            if rec.product_id.id == rec.env.ref('real_estate.balloting_product').id:
                                balance = balance - (self.primary_amount *
                                                     self.primary_amount_frequency)

                            # Used for "Additional Balloon" Product
                            if rec.product_id.id == rec.env.ref('real_estate.additional_balloon').id:
                                balance = balance - (self.add_balloon_amount *
                                                     self.add_balloon_frequency)

                        if self.predefine_plan_id.include_in_plan == 'no':
                            # Used for total installment.plan dates calculation. Also included "additional balloon" frequency
                            for rec in range(1, (self.total_installment + self.balloon_payment_frequency +
                                                 self.possession_amount_frequency + self.primary_amount_frequency + self.add_balloon_frequency)):
                                dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                        else:
                            for rec in range(1, self.total_installment):
                                dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                    else:
                        for rec in range(1, self.total_installment):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))

                    # balloons replace installment slots only when the plan treats them as
                    # installments; treated as balloons they come on top of the regular ones
                    balloon_uses_slots = (not self.include_installment and self.predefine_plan_id
                                          and self.predefine_plan_id.include_in_plan == 'yes'
                                          and self.predefine_plan_id.treat_balloon_as == 'installment')
                    installment_amount = round(balance / (
                            self.total_installment - self.balloon_payment_frequency)) if balloon_uses_slots else round(
                        balance / self.total_installment)

                    # with include_installment the balloon is a separate line and every
                    # month still gets its own installment line
                    expected_installments = self.total_installment
                    if balloon_uses_slots:
                        expected_installments = self.total_installment - self.balloon_payment_frequency

                    def _pending_plan_events():
                        # regular installments and balloon/possession/balloting lines whose
                        # slot falls beyond the generated dates still have to be scheduled
                        if not self.predefine_plan_id:
                            return False
                        if installment_count <= expected_installments:
                            return True
                        plan_products = self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids
                        if (self.env.ref('real_estate.balloon_payment').id in plan_products
                                and interval < self.balloon_payment_frequency):
                            return True
                        if (self.env.ref('real_estate.possession_amount_product').id in plan_products
                                and possession_interval < self.possession_amount_frequency):
                            return True
                        if (self.env.ref('real_estate.additional_balloon').id in plan_products
                                and add_balloon_interval < self.add_balloon_frequency):
                            return True
                        if (self.env.ref('real_estate.balloting_product').id in plan_products
                                and primary_interval < self.primary_amount_frequency):
                            return True
                        return False

                    date_index = 0
                    while date_index < len(dates) or (_pending_plan_events()
                                                      and len(dates) < self.total_installment + 120):
                        if date_index >= len(dates):
                            dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
                        rec = dates[date_index]
                        date_index += 1
                        if self.balloon_payment_start and not start_balloon_payment:
                            if installment_number == self.balloon_payment_start:
                                if balance:
                                    amount = self.balloon_payment if balance > installment_amount else balance
                                else:
                                    amount = 0
                                self.investment_plan_ids.create({
                                    'date': rec,
                                    'installment_number': installment_number,
                                    'installment_type': 'balloon',
                                    'installment_name': 'Installment' + ' ' + str(
                                        installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                    'payment_status': 'not_paid',
                                    'balance_amount': amount,
                                    'residual': amount,
                                    'amount': amount,
                                    'investment_id': self.id
                                })
                                if self.predefine_plan_id.treat_balloon_as == 'installment':
                                    installment_count += 1
                                interval = interval + 1
                                # with include_installment the balloon occupies an extra row,
                                # so the next balloon slot shifts one number further
                                balloon_interval += self.balloon_payment_start + (1 if self.include_installment else 0)
                                start_balloon_payment = True
                                installment_number = installment_number + 1
                                if self.include_installment:
                                    # the installment of this month is a separate line
                                    # on the same date, so do not consume the date slot
                                    date_index -= 1
                                continue

                        # for product 'Additional Balloon' used in predefined plan. Same as others defined previously
                        if self.predefine_plan_id \
                                and self.env.ref('real_estate.additional_balloon').id \
                                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                            try:
                                installment_number % self.add_balloon_interval == 0
                            except Exception as e:
                                raise ValidationError(_('%s Additional Balloon Interval should be greater than 0:' % (e)))
                            else:
                                if installment_number % self.add_balloon_interval == 0 \
                                        and add_balloon_interval < self.add_balloon_frequency:
                                    if balance:
                                        amount = self.add_balloon_amount if balance > installment_amount else balance
                                    else:
                                        amount = 0
                                    self.investment_plan_ids.create({
                                        'date': rec,
                                        'installment_number': installment_number,
                                        'installment_type': 'balloon',
                                        'installment_name': 'Balloon',
                                        'payment_status': 'not_paid',
                                        'amount_paid': 0,
                                        'balance_amount': amount,
                                        'residual': amount,
                                        'amount': amount,
                                        'investment_id': self.id
                                    })
                                    add_balloon_interval += 1
                                    installment_number = installment_number + 1
                                    continue

                        if self.predefine_plan_id \
                                and self.env.ref('real_estate.possession_amount_product').id \
                                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                            try:
                                installment_number % self.possession_amount_interval == 0
                            except Exception as e:
                                raise ValidationError(_('%s Possession Interval should be greater than 0:' % (e)))
                            else:
                                if installment_number % self.possession_amount_interval == 0 \
                                        and possession_interval < self.possession_amount_frequency:
                                    if balance:
                                        amount = self.possession_amount if balance > installment_amount else balance
                                    else:
                                        amount = 0
                                    self.investment_plan_ids.create({
                                        'date': rec,
                                        'installment_number': installment_number,
                                        'installment_type': 'possession_amount',
                                        'installment_name': 'Possession',
                                        'payment_status': 'not_paid',
                                        'amount_paid': 0,
                                        'balance_amount': amount,
                                        'residual': amount,
                                        'amount': amount,
                                        'investment_id': self.id
                                    })
                                    possession_interval += 1
                                    installment_number = installment_number + 1
                                    continue

                        if self.predefine_plan_id \
                                and self.env.ref('real_estate.balloting_product').id \
                                in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
                            try:
                                installment_number % self.primary_amount_interval == 0
                            except Exception as e:
                                raise ValidationError(_('%s Balloting Interval should be greater than 0:' % (e)))
                            else:
                                if installment_number % self.primary_amount_interval == 0 \
                                        and primary_interval < self.primary_amount_frequency:
                                    if balance:
                                        amount = self.primary_amount if balance > installment_amount else balance
                                    else:
                                        amount = 0
                                    self.investment_plan_ids.create({
                                        'date': rec,
                                        'installment_number': installment_number,
                                        'installment_type': 'balloting_amount',
                                        'installment_name': 'Balloting',
                                        'payment_status': 'not_paid',
                                        'amount_paid': 0,
                                        'balance_amount': amount,
                                        'residual': amount,
                                        'amount': amount,
                                        'investment_id': self.id
                                    })
                                    primary_interval += 1
                                    installment_number = installment_number + 1
                                    continue

                        if (self.predefine_plan_id and self.env.ref(
                                'real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped(
                            'product_id').ids and (installment_number % balloon_interval == 0
                                                   and interval < self.balloon_payment_frequency and start_balloon_payment)):
                            if balance:
                                amount = self.balloon_payment if balance > installment_amount else balance
                            else:
                                amount = 0
                            self.investment_plan_ids.create({
                                'date': rec,
                                'installment_number': installment_number,
                                'installment_type': 'balloon',
                                'installment_name': 'Installment' + ' ' + str(
                                    installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
                                'payment_status': 'not_paid',
                                'amount_paid': 0,
                                'balance_amount': amount,
                                'residual': amount,
                                'amount': amount,
                                'investment_id': self.id
                            })
                            if self.predefine_plan_id.treat_balloon_as == 'installment':
                                installment_count += 1
                            interval = interval + 1
                            balloon_interval += self.balloon_payment_interval + (1 if self.include_installment else 0)
                            installment_number = installment_number + 1
                            if self.include_installment:
                                # the installment of this month is a separate line
                                # on the same date, so do not consume the date slot
                                date_index -= 1
                            continue
                        else:
                            if self.predefine_plan_id and installment_count > expected_installments:
                                # all regular installment slots are filled; keep the slot
                                # numbering and dates moving so later balloon/possession
                                # slots land on their configured positions
                                installment_number = installment_number + 1
                                continue
                            self.investment_plan_ids.create({
                                'date': rec,
                                'installment_type': 'installment',
                                'installment_number': installment_number,
                                'installment_name': 'Installment' + ' ' + str(installment_count),
                                'amount': installment_amount,
                                'balance_amount': installment_amount,
                                'amount_paid': 0,
                                'residual': installment_amount,
                                'payment_status': 'not_paid',
                                'investment_id': self.id
                            })
                            installment_count += 1
                            installment_number = installment_number + 1
                    # total = sum(self.investment_plan_ids.mapped('amount'))
                    # if total < self.total_amount:
                    #     price = self.total_amount - total
                    #     self.investment_plan_ids.search([])[-1].update({
                    #         'amount': round(self.balance_amount / self.total_installment) + price,
                    #         'balance_amount': round(self.balance_amount / self.total_installment) + price,
                    #         'residual': round(self.balance_amount / self.total_installment) + price,
                    #     })
                    # elif total > self.total_amount:
                    #     price = total - self.total_amount
                    #     self.investment_plan_ids.search([])[-1].update({
                    #         'amount': round(self.balance_amount / self.total_installment) - price,
                    #         'balance_amount': round(self.balance_amount / self.total_installment) - price,
                    #         'residual': round(self.balance_amount / self.total_installment) - price,
                    #     })
                    # del installment_number

                    plan = self.env['investment.plan'].search([('investment_id', '=', self.id)])
                    if self.balloting_amount:
                        plan.create({
                            'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
                            'installment_type': 'final',
                            'payment_status': 'not_paid',
                            'installment_number': installment_number,
                            'installment_name': 'Final',
                            'amount_paid': 0,
                            'amount': self.balloting_amount,
                            'residual': self.balloting_amount,
                            'balance_amount': self.balloting_amount,
                            'investment_id': self.id
                        })
                        installment_count += 1

                    total = sum(self.investment_plan_ids.mapped('amount'))
                    last_line = self.investment_plan_ids[-1]
                    if total < self.total_amount:
                        price = self.total_amount - total
                        last_line.update({
                            'amount': last_line.amount + price,
                            'residual': last_line.residual + price,
                            'balance_amount': last_line.balance_amount + price,
                        })
                    elif total > self.total_amount:
                        price = total - self.total_amount
                        last_line.update({
                            'amount': last_line.amount - price,
                            'residual': last_line.residual - price,
                            'balance_amount': last_line.balance_amount - price,
                        })
                    del installment_number

                    self.installment_created = True
                else:
                    raise ValidationError(
                        _("Installment Starting Date,Interval and total installments should be there."))

            self.compute_rebate_amount_process()
        if self.plan_type == 'predefine' and self.payment_type == 'lump_sum' and self.env.ref('real_estate.lump_sum_product').id in \
                self.predefine_plan_id.predefine_plan_line_ids.mapped(
                    'product_id').ids:
            if len(self.predefine_plan_id.predefine_plan_line_ids) == 1 or self.predefine_plan_id.total_installment == 1:
                installment_date = self.booking_date
                if self.grace_period_type == 'days':
                    installment_date = self.booking_date + relativedelta(days=+self.grace_period)
                if self.grace_period_type == 'months':
                    installment_date = self.booking_date + relativedelta(months=+self.grace_period)
                if self.grace_period_type == 'years':
                    installment_date = self.booking_date + relativedelta(years=+self.grace_period)
                self.investment_plan_ids.create({
                    'date': installment_date,
                    'installment_type': 'down',
                    'installment_name': 'Lump Sum',
                    'installment_number': 1,
                    'amount': self.total_amount,
                    'amount_paid': 0,
                    'balance_amount': self.total_amount,
                    'residual': self.total_amount,
                    'payment_status': 'not_paid',
                    'investment_id': self.id
                })
            # else:
            #     if not self.down_payment:
            #         raise ValidationError('Please enter some amount for Down Payment')
            #     self.investment_plan_ids.create({
            #         'date': self.booking_date,
            #         'installment_type': 'down',
            #         'installment_name': 'Booking',
            #         'installment_number': 1,
            #         'amount': self.down_payment,
            #         'amount_paid': 0,
            #         'balance_amount': self.down_payment,
            #         'residual': self.down_payment,
            #         'payment_status': 'not_paid',
            #         'investment_id': self.id
            #     })
            #     if self.env.ref('real_estate.confirmation_amount_product').id in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            #         installment_number = 3
            #         # confirmation_date = self.start_date
            #         confirmation_date = self.booking_date
            #         if self.grace_period_type == 'days':
            #             confirmation_date = self.booking_date + relativedelta(days=+self.grace_period)
            #         if self.grace_period_type == 'months':
            #             confirmation_date = self.booking_date + relativedelta(months=+self.grace_period)
            #         if self.grace_period_type == 'years':
            #             confirmation_date = self.booking_date + relativedelta(years=+self.grace_period)
            #         self.investment_plan_ids.create({
            #             # 'date': self.start_date + relativedelta(months=+self.predefine_plan_id.confirmation_amount_period),
            #             'date': confirmation_date,
            #             'installment_number': 2,
            #             'installment_type': 'confirmation_amount',
            #             'installment_name': 'Confirmation',
            #             'payment_status': 'not_paid',
            #             'amount_paid': 0,
            #             'balance_amount': self.confirmation_amount,
            #             'amount': self.confirmation_amount,
            #             'residual': self.confirmation_amount,
            #             'investment_id': self.id
            #         })
            #     else:
            #         installment_number = 2
            #
            #     if self.balance_amount > 0:
            #         # if all([self.installment_starting_date, self.interval_id, self.total_installment]):
            #         #     start_date = self.installment_starting_date
            #         if all([self.start_date, self.interval_id, self.total_installment]):
            #             start_date = self.start_date
            #             dates = [fields.Date.from_string(start_date)]
            #
            #             interval = 0
            #             possession_interval = 0
            #             primary_interval = 0
            #             start_balloon_payment = False
            #             installment_count = 1
            #             balloon_interval = self.balloon_payment_interval
            #             balance = self.balance_amount - self.balloting_amount
            #
            #             if self.predefine_plan_id:
            #                 for rec in self.predefine_plan_id.predefine_plan_line_ids:
            #                     if rec.product_id.id == rec.env.ref('real_estate.balloon_payment').id:
            #                         balance = balance - (self.balloon_payment *
            #                                              self.balloon_payment_frequency)
            #
            #                     if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
            #                         balance = balance - (self.possession_amount * self.possession_amount_frequency)
            #
            #                     if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
            #                         balance = balance - (self.confirmation_amount *
            #                                              self.confirmation_amount_frequency)
            #
            #                     if rec.product_id.id == rec.env.ref('real_estate.balloting_product').id:
            #                         balance = balance - (self.primary_amount *
            #                                              self.primary_amount_frequency)
            #
            #                 if self.predefine_plan_id.include_in_plan == 'no':
            #                     for rec in range(1, (self.total_installment + self.balloon_payment_frequency +
            #                                          self.possession_amount_frequency + self.primary_amount_frequency)):
            #                         dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
            #                 else:
            #                     for rec in range(1, self.total_installment):
            #                         dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
            #             else:
            #                 for rec in range(1, self.total_installment):
            #                     dates.append(dates[-1] + relativedelta(months=+self.interval_id.nom))
            #
            #             installment_amount = round(balance / (
            #                     self.total_installment - self.balloon_payment_frequency)) if not self.include_installment and self.predefine_plan_id and self.predefine_plan_id.include_in_plan == 'yes' else round(
            #                 balance / self.total_installment)
            #
            #             for rec in dates:
            #                 if self.balloon_payment_start and not start_balloon_payment:
            #                     if installment_number == self.balloon_payment_start:
            #                         if balance:
            #                             amount = self.balloon_payment if balance > installment_amount else balance
            #                         else:
            #                             amount = 0
            #                         self.investment_plan_ids.create({
            #                             'date': rec,
            #                             'installment_number': installment_number,
            #                             'installment_type': 'balloon',
            #                             'installment_name': 'Installment' + ' ' + str(
            #                                 installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
            #                             'payment_status': 'not_paid',
            #                             'balance_amount': amount + installment_amount if self.include_installment else amount,
            #                             'residual': amount + installment_amount if self.include_installment else amount,
            #                             'amount': amount + installment_amount if self.include_installment else amount,
            #                             'investment_id': self.id
            #                         })
            #                         if self.predefine_plan_id.treat_balloon_as == 'installment':
            #                             installment_count += 1
            #                         interval = interval + 1
            #                         balloon_interval += self.balloon_payment_start
            #                         start_balloon_payment = True
            #                         installment_number = installment_number + 1
            #                         continue
            #
            #                 if self.plan_type == 'predefine' \
            #                         and self.env.ref('real_estate.possession_amount_product').id \
            #                         in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            #                     try:
            #                         installment_number % self.possession_amount_interval == 0
            #                     except Exception as e:
            #                         raise ValidationError(_('%s Possession Interval should be greater than 0:' % (e)))
            #                     else:
            #                         if installment_number % self.possession_amount_interval == 0 \
            #                                 and possession_interval < self.possession_amount_frequency:
            #                             if balance:
            #                                 amount = self.possession_amount if balance > installment_amount else balance
            #                             else:
            #                                 amount = 0
            #                             self.investment_plan_ids.create({
            #                                 'date': rec,
            #                                 'installment_number': installment_number,
            #                                 'installment_type': 'possession_amount',
            #                                 'installment_name': 'Possession',
            #                                 'payment_status': 'not_paid',
            #                                 'amount_paid': 0,
            #                                 'balance_amount': amount,
            #                                 'residual': amount,
            #                                 'amount': amount,
            #                                 'investment_id': self.id
            #                             })
            #                             possession_interval += 1
            #                             installment_number = installment_number + 1
            #                             continue
            #
            #                 if self.plan_type == 'predefine' \
            #                         and self.env.ref('real_estate.balloting_product').id \
            #                         in self.predefine_plan_id.predefine_plan_line_ids.mapped('product_id').ids:
            #                     try:
            #                         installment_number % self.primary_amount_interval == 0
            #                     except Exception as e:
            #                         raise ValidationError(_('%s Balloting Interval should be greater than 0:' % (e)))
            #                     else:
            #                         if installment_number % self.primary_amount_interval == 0 \
            #                                 and primary_interval < self.primary_amount_frequency:
            #                             if balance:
            #                                 amount = self.primary_amount if balance > installment_amount else balance
            #                             else:
            #                                 amount = 0
            #                             self.investment_plan_ids.create({
            #                                 'date': rec,
            #                                 'installment_number': installment_number,
            #                                 'installment_type': 'balloting_amount',
            #                                 'installment_name': 'Balloting',
            #                                 'payment_status': 'not_paid',
            #                                 'amount_paid': 0,
            #                                 'balance_amount': amount,
            #                                 'residual': amount,
            #                                 'amount': amount,
            #                                 'investment_id': self.id
            #                             })
            #                             primary_interval += 1
            #                             installment_number = installment_number + 1
            #                             continue
            #
            #                 if (self.plan_type == 'predefine' and self.env.ref(
            #                         'real_estate.balloon_payment').id in self.predefine_plan_id.predefine_plan_line_ids.mapped(
            #                     'product_id').ids and (installment_number % balloon_interval == 0
            #                                            and interval < self.balloon_payment_frequency and start_balloon_payment)):
            #                     if balance:
            #                         amount = self.balloon_payment if balance > installment_amount else balance
            #                     else:
            #                         amount = 0
            #                     self.investment_plan_ids.create({
            #                         'date': rec,
            #                         'installment_number': installment_number,
            #                         'installment_type': 'balloon',
            #                         'installment_name': 'Installment' + ' ' + str(
            #                             installment_count) if self.predefine_plan_id.treat_balloon_as == 'installment' else 'Balloon',
            #                         'payment_status': 'not_paid',
            #                         'amount_paid': 0,
            #                         'balance_amount': amount + installment_amount if self.include_installment else amount,
            #                         'residual': amount + installment_amount if self.include_installment else amount,
            #                         'amount': amount + installment_amount if self.include_installment else amount,
            #                         'investment_id': self.id
            #                     })
            #                     if self.predefine_plan_id.treat_balloon_as == 'installment':
            #                         installment_count += 1
            #                     interval = interval + 1
            #                     balloon_interval += self.balloon_payment_interval
            #                     installment_number = installment_number + 1
            #                     continue
            #                 else:
            #                     self.investment_plan_ids.create({
            #                         'date': rec,
            #                         'installment_type': 'installment',
            #                         'installment_number': installment_number,
            #                         'installment_name': 'Installment' + ' ' + str(installment_count),
            #                         'amount': installment_amount,
            #                         'balance_amount': installment_amount,
            #                         'amount_paid': 0,
            #                         'residual': installment_amount,
            #                         'payment_status': 'not_paid',
            #                         'investment_id': self.id
            #                     })
            #                     installment_count += 1
            #                     installment_number = installment_number + 1
            #             # total = sum(self.investment_plan_ids.mapped('amount'))
            #             # if total < self.total_amount:
            #             #     price = self.total_amount - total
            #             #     self.investment_plan_ids.search([])[-1].update({
            #             #         'amount': round(self.balance_amount / self.total_installment) + price,
            #             #         'balance_amount': round(self.balance_amount / self.total_installment) + price,
            #             #         'residual': round(self.balance_amount / self.total_installment) + price,
            #             #     })
            #             # elif total > self.total_amount:
            #             #     price = total - self.total_amount
            #             #     self.investment_plan_ids.search([])[-1].update({
            #             #         'amount': round(self.balance_amount / self.total_installment) - price,
            #             #         'balance_amount': round(self.balance_amount / self.total_installment) - price,
            #             #         'residual': round(self.balance_amount / self.total_installment) - price,
            #             #     })
            #             # del installment_number
            #
            #             plan = self.env['investment.plan'].search([('investment_id', '=', self.id)])
            #             if self.balloting_amount:
            #                 plan.create({
            #                     'date': dates[-1] + relativedelta(months=+self.interval_id.nom),
            #                     'installment_type': 'final',
            #                     'payment_status': 'not_paid',
            #                     'installment_number': installment_number,
            #                     'installment_name': 'Final',
            #                     'amount_paid': 0,
            #                     'amount': self.balloting_amount,
            #                     'residual': self.balloting_amount,
            #                     'balance_amount': self.balloting_amount,
            #                     'investment_id': self.id
            #                 })
            #                 installment_count += 1
            #
            #             total = sum(self.investment_plan_ids.mapped('amount'))
            #             if total < self.total_amount:
            #                 price = self.total_amount - total
            #                 self.investment_plan_ids.search([])[-1].update({
            #                     'amount': self.investment_plan_ids.search([])[-1].amount + price,
            #                     'residual': self.investment_plan_ids.search([])[-1].residual + price,
            #                     'balance_amount': self.investment_plan_ids.search([])[-1].balance_amount + price,
            #                 })
            #             elif total > self.total_amount:
            #                 price = total - self.total_amount
            #                 self.investment_plan_ids.search([])[-1].update({
            #                     'amount': self.investment_plan_ids.search([])[-1].amount - price,
            #                     'residual': self.investment_plan_ids.search([])[-1].residual - price,
            #                     'balance_amount': self.investment_plan_ids.search([])[-1].balance_amount - price,
            #                 })
            #             del installment_number
            #
            #             self.installment_created = True
            #         else:
            #             raise ValidationError(
            #                 _("Installment Starting Date,Interval and total installments should be there."))

            self.compute_rebate_amount_process()

    def update_booking_amount_on_open_files(self):
        for rec in self:
            booking_line = rec.investment_plan_ids.filtered(lambda l: l.installment_type == 'down')
            if booking_line and booking_line.amount_paid > 0:
                open_files = self.env['investor.file'].search([('investment_id', '=', rec.id), ('state', '!=', 'cancel')])
                for file in open_files:
                    file.update_rebate_values_for_booking()
                if rec.company_id.id != 1:
                    rec.set_net_payment_data()
                    booking_line = rec.investment_plan_ids.filtered(lambda l: l.installment_type == 'down')
                    if booking_line:
                        # booking_balance = booking_line.amount_paid - booking_line.dealer_share
                        booking_balance = booking_line.net_payment
                        # if rec.reservation_type == 'bulk':
                        all_installments = self.env['installment.plan'].search(
                            [('investor_file_id.investment_id', '=', rec.id), ('payment_status', 'in', ['not_paid', 'in_payment']),
                             ('installment_type', '=', 'down'), ('residual', '>', 0)])
                        adjustment_amount = booking_balance
                        if all_installments:
                            if adjustment_amount > 0:
                                for lines in all_installments.sorted(
                                        key=lambda r: (r.investor_file_id.file_created, r.investor_file_id.issuance_request_created),
                                        reverse=True):
                                    diff = adjustment_amount - lines.residual
                                    if adjustment_amount > 0:
                                        if not diff < 0:
                                            lines.amount_paid += lines.residual
                                            adjustment_amount -= lines.residual
                                        else:
                                            lines.amount_paid += adjustment_amount
                                            adjustment_amount = 0
                                        lines.residual = lines.amount - lines.amount_paid
                                        if lines.residual == 0:
                                            lines.payment_status = 'paid'
                                        else:
                                            if lines.amount_paid > 0:
                                                lines.payment_status = 'in_payment'
                                    lines.net_payment = lines.amount_paid - lines.dealer_share
                                    lines.compute_net_payment()

    def update_booking_amount_on_open_files_remaining(self, amount):
        for rec in self:
            if rec.company_id.id != 1:
                booking_balance = amount
                if rec.reservation_type == 'bulk':
                    all_installments = self.env['installment.plan'].search(
                        [('investor_file_id.investment_id', '=', rec.id), ('payment_status', 'in', ['not_paid', 'in_payment']),
                         ('installment_type', '=', 'down'),
                         ('residual', '>', 0)])
                    adjustment_amount = booking_balance
                    if all_installments:
                        if adjustment_amount > 0:
                            for lines in all_installments.sorted(key=lambda r: r.investor_file_id.issuance_request_created, reverse=True):
                                diff = adjustment_amount - lines.residual
                                if adjustment_amount > 0:
                                    if not diff < 0:
                                        lines.amount_paid += lines.residual
                                        adjustment_amount -= lines.residual
                                    else:
                                        lines.amount_paid += adjustment_amount
                                        adjustment_amount = 0
                                    lines.residual = lines.amount - lines.amount_paid
                                    if lines.residual == 0:
                                        lines.payment_status = 'paid'
                                    else:
                                        if lines.amount_paid > 0:
                                            lines.payment_status = 'in_payment'
                                lines.net_payment = lines.amount_paid - lines.dealer_share
                                lines.compute_net_payment()

    # def update_investment_related_payment_data(self, amount):
    #     # For Current
    #     for investment in self:
    #         investment.set_net_payment_data()
    #         investment.update_booking_amount_on_open_files_remaining(amount)
    def update_investment_related_payment_data(self):
        # For Current
        for investment in self:
            investment.set_net_payment_data()
            investment.update_booking_amount_on_open_files()

    def update_investment_related_data_query(self):
        # For All
        investments = self.env['investment'].search([('company_id.id','in', [5, 16])])
        for investment in investments:
            investment.compute_rebate_amount_process()
            investment.set_net_payment_data()
            investment.update_booking_amount_on_open_files()


class LaunchType(models.Model):
    _name = 'launch.type'
    _description = 'Launch Type'

    name = fields.Char('Name', required=True)


class InvestmentPaymentExt(models.TransientModel):
    _inherit = 'investment.payment'

    # investment.partner_id now points to res.investor (Dealer), not res.member.
    partner_id = fields.Many2one('res.investor', string="Investor", related='investment_id.partner_id', store=True)
