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
    header_plan_required = fields.Boolean(compute='_compute_header_plan_required')

    @api.depends('plan_type', 'multiple_plans', 'reservation_type',
                 'investment_line_ids.predefine_plan_id', 'inventory_ids.predefine_plan_id')
    def _compute_header_plan_required(self):
        # The header Plan Name is only a FALLBACK for lines/units that don't
        # pick their own plan (see _get_installment_plan_groups()) - once
        # every line already has its own predefine plan, the header one has
        # nothing left to apply to and shouldn't block saving.
        for rec in self:
            if rec.plan_type != 'predefine':
                rec.header_plan_required = False
                continue
            if rec.multiple_plans and rec.reservation_type == 'bulk' and rec.investment_line_ids:
                lines = rec.investment_line_ids
            elif rec.multiple_plans and rec.reservation_type == 'unit' and rec.inventory_ids:
                lines = rec.inventory_ids
            else:
                lines = rec.env['investment.line']
            rec.header_plan_required = not (lines and all(l.predefine_plan_id for l in lines))

    single_product = fields.Boolean(compute='_compute_single_product')

    @api.depends('reservation_type', 'investment_line_ids.unit_category_type_id',
                 'inventory_ids.unit_category_type_id')
    def _compute_single_product(self):
        # Once the deal's lines/units span more than one Product (5 Marla +
        # 3 Marla + ...), a single header-level plan can no longer represent
        # them all - each product needs its own plan, so the header Plan Name
        # selector should get out of the way rather than imply one plan
        # covers everything.
        for rec in self:
            if rec.reservation_type == 'bulk':
                lines = rec.investment_line_ids
            elif rec.reservation_type == 'unit':
                lines = rec.inventory_ids
            else:
                lines = rec.env['investment.line']
            products = set(lines.filtered('unit_category_type_id').mapped('unit_category_type_id').ids)
            rec.single_product = len(products) <= 1

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

    @staticmethod
    def _schedule_field_changed(rec, key, value):
        # _compute_combined_schedule_fields() returns write-safe values (a
        # raw id/False for Many2one fields, e.g. interval_id), but rec[key]
        # returns the field in read form (a recordset for Many2one) - compare
        # ids on both sides so a Many2one field isn't always seen as
        # "changed" (recordset != int is never equal) and doesn't trigger a
        # redundant write every single time.
        current = rec[key]
        if hasattr(current, 'id'):
            return (current.id or False) != (value or False)
        return current != value

    def write(self, vals):
        res = super().write(vals)
        # Booking Payment and every other schedule field (Confirmation/
        # Balloting/Possession/Balloon amounts, Interval, No. of Installments,
        # balloon timing...) are otherwise only ever refreshed by the
        # change_booking_and_confirmation() onchange during live editing,
        # which doesn't reliably cascade up from a field edited on a line
        # nested inside inventory_ids/investment_line_ids. Recompute them
        # directly on every save for multi-plan deals so the stored/displayed
        # values are correct even if that onchange never fired client-side.
        if not self.env.context.get('skip_down_payment_recompute'):
            for rec in self:
                # Not gated on rec.multiple_plans: _compute_combined_schedule_fields()
                # already returns {} for the plain single-plan case (nothing to
                # override), so this is a safe no-op there and only actually
                # updates anything when units/lines carry their own per-unit
                # predefine_plan_id (own_plan) - which happens regardless of
                # whether the Multiple Plans checkbox is ticked.
                updates = rec._compute_combined_schedule_fields()
                updates = {k: v for k, v in updates.items() if rec._schedule_field_changed(rec, k, v)}
                if updates:
                    rec.with_context(skip_down_payment_recompute=True).write(updates)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            updates = rec._compute_combined_schedule_fields()
            updates = {k: v for k, v in updates.items() if rec._schedule_field_changed(rec, k, v)}
            if updates:
                rec.with_context(skip_down_payment_recompute=True).write(updates)
        return records

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
        for rec in self:
            net_off_lines = self.env['investment.plan'].search(
                [('installment_type', 'in', ['down', 'confirmation_amount']), ('investment_id', '=', rec.id),
                 ('company_id.id', 'in', [5, 16])])
            if net_off_lines:
                for line in net_off_lines:
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

    def action_open_file_creation_wizard(self):
        # bulk deals have no per-unit identity to select against (a line is
        # "N units of a size", not N distinct records) - they keep the old
        # all-at-once behavior. Unit deals go through the selective wizard
        # instead of creating every remaining unit's file in one call.
        self.ensure_one()
        if self.reservation_type == 'bulk':
            return self.create_open_file()
        return {
            'name': _('Create Open File'),
            'type': 'ir.actions.act_window',
            'res_model': 'investment.file.creation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_investment_id': self.id},
        }

    def action_open_add_inventory_wizard(self):
        # inventory_ids is fully readonly once state='reserved' (see
        # real_estate.investment_view_form), so there's no way to add more
        # units to the deal from the main form at all past that point -
        # this wizard writes inventory_ids/plot.inventory directly, same
        # trick as action_open_assign_plan_wizard below.
        self.ensure_one()
        return {
            'name': _('Add Inventory'),
            'type': 'ir.actions.act_window',
            'res_model': 'investment.add.inventory.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_investment_id': self.id},
        }

    def action_open_assign_plan_wizard(self):
        # investment_line_ids/inventory_ids become fully readonly once the
        # deal is state='reserved' (see real_estate.investment_view_form), so
        # a still-missing Plan on a row can no longer be picked from the main
        # form at all - this wizard is the one place left to set it, touching
        # only predefine_plan_id (and the values it drives) on those rows.
        self.ensure_one()
        return {
            'name': _('Assign Plan'),
            'type': 'ir.actions.act_window',
            'res_model': 'investment.assign.plan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_investment_id': self.id},
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

    def _auto_assign_predefine_plan(self, lines):
        """A line/unit whose Product (unit_category_type_id) matches exactly
        one 'per product' predefine.plan gets that plan filled in automatically,
        instead of relying on the user picking it by hand on every row - which
        is no longer possible at all once the deal reaches state 'reserved'
        (investment_line_ids/inventory_ids become readonly at that point)."""
        if self.plan_type != 'predefine':
            return
        for line in lines:
            if line.predefine_plan_id or not line.unit_category_type_id:
                continue
            plan = self.env['predefine.plan'].search([
                ('unit_category_type_id', '=', line.unit_category_type_id.id),
                ('project_type', '=', self.project_type),
            ])
            if len(plan) == 1:
                line.predefine_plan_id = plan.id

    @api.onchange('investment_line_ids', 'inventory_ids', 'total_amount', 'multiple_plans')
    def change_booking_and_confirmation(self):
        if self.reservation_type == 'bulk':
            lines = self.investment_line_ids
        elif self.reservation_type == 'unit':
            lines = self.inventory_ids
        else:
            lines = self.env['investment.line']

        self._auto_assign_predefine_plan(lines)

        # Picking a plan on any individual line/unit IS what makes this a
        # multi-plan deal - the user shouldn't also have to remember to flip
        # the "Multiple Plans" checkbox separately for it to take effect.
        if lines.filtered(lambda l: l.predefine_plan_id):
            self.multiple_plans = True

        if lines and self.multiple_plans:
            booking_amount = 0
            confirmation_amount = 0
            balloting_amount = 0
            posession_amount = 0
            final_amount = 0
            balloon_amount = 0
            for line in lines:
                if line.predefine_plan_id:
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

    def create_open_file(self, inventory=None):
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
        # inventory may be passed in by the selective-creation wizard to
        # restrict this run to just the chosen units - otherwise (and always
        # for reservation_type=='bulk', which has no per-unit identity to
        # restrict against) fall back to every unit that doesn't already
        # have an open file, so repeat calls never recreate one.
        inventory = inventory or self.env['plot.inventory'].search(
            [('investment_id', '=', self.id), ('investor_file_id', '=', False)])
        # Prorate off the deal's actual generated Booking/Down Payment installment
        # lines (investment_plan_ids), not the deal's own down_payment/
        # down_payment_amount header fields - those are only kept fresh by the
        # _onchange_total_amount UI onchange, so any deal created/copied without
        # that onchange firing (duplicate, bulk import, etc.) would silently
        # prorate off a stale/wrong header value while the real installment plan
        # (built from predefine.plan.get_schedule_params()) already has the
        # correct amounts.
        booking_total = sum(self.investment_plan_ids.filtered(
            lambda l: l.installment_type == 'down' and l.installment_name == 'Booking').mapped('amount'))
        down_payment_total = sum(self.investment_plan_ids.filtered(
            lambda l: l.installment_type == 'down_payment').mapped('amount'))
        booking_prorate = (booking_total / self.total_amount) if self.total_amount else 0.0
        down_payment_prorate = (down_payment_total / self.total_amount) if self.total_amount else 0.0
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
                        'bucket_id': lines.bucket_id.id,
                        'category_id': lines.category_id.id,
                        'unit_category_type_id': lines.unit_category_type_id.id,
                        'size_id': lines.size_id.id,
                        # 'unit_class_id': inv.unit_class_id.id,
                        # 'inventory_id': inv.id,
                        # 'unit_number': inv.name,
                        # 'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                        'payment_type': self.payment_type,
                        'plan_type': self.plan_type,
                        'predefine_plan_id': lines.predefine_plan_id.id or self.predefine_plan_id.id,
                        'interval_id': lines.predefine_plan_id.interval_id.id if lines.predefine_plan_id else self.interval_id.id,
                        # 'starting_date': self.start_date,
                        'booking_date':self.booking_date,
                        'starting_date':self.installment_starting_date or self.start_date,
                        'total_installment': lines.predefine_plan_id.total_installment if lines.predefine_plan_id else self.total_installment,
                        'payment_states': 'open',
                        'sale_amount': lines.investor_price,
                        'ttl_sale_amount': lines.investor_price,
                        'net_sale_amount': lines.investor_price,
                        'initial_payment': round(
                            lines.investor_price * booking_prorate) if self.options == 'down' else 0,
                        'down_payment_amount': round(
                            lines.investor_price * down_payment_prorate) if self.options == 'down' else 0,
                        'balance_amount': lines.investor_price - round(
                            lines.investor_price * booking_prorate) - round(
                            lines.investor_price * down_payment_prorate) if self.options == 'down' else lines.investor_price,
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
                    'bucket_id': inv.bucket_id.id,
                    'category_id': inv.category_id.id,
                    'unit_category_type_id': inv.unit_category_type_id.id,
                    'size_id': inv.size_id.id,
                    'unit_class_id': inv.unit_class_id.id,
                    'inventory_id': inv.id,
                    # 'payment_type': 'installments' if self.options == 'down' else 'lump_sum',
                    'plan_type': self.plan_type,
                    'predefine_plan_id': (inv.predefine_plan_id.id or self.predefine_plan_id.id) or None,
                    'payment_type': self.payment_type,
                    'interval_id': ((inv.predefine_plan_id.interval_id.id if inv.predefine_plan_id else self.interval_id.id)
                                    if self.options == 'down' else False),
                    'starting_date': self.start_date,
                    'total_installment': ((inv.predefine_plan_id.total_installment if inv.predefine_plan_id else self.total_installment)
                                          if self.options == 'down' else 0),
                    'payment_states': 'open',
                    'sale_amount': inv.investor_unit_price,
                    'ttl_sale_amount': inv.investor_unit_price,
                    'net_sale_amount': inv.investor_unit_price,
                    'initial_payment': round(
                        inv.investor_unit_price * booking_prorate) if self.options == 'down' else inv.investor_unit_price,
                    'down_payment_amount': round(
                        inv.investor_unit_price * down_payment_prorate) if self.options == 'down' else 0,
                    'balance_amount': inv.investor_unit_price - round(
                        inv.investor_unit_price * booking_prorate) - round(
                        inv.investor_unit_price * down_payment_prorate) if self.options == 'down' else 0,
                }
                open_file = investor_file.create(vals)
                inv.investor_file_id = open_file.id
        self.update_booking_amount_on_open_files()
        self.update_confirmation_amount_on_open_files()
        if self.reservation_type == 'unit':
            # only every unit having its own open file means there's nothing
            # left to select in the creation wizard - bulk deals have no
            # per-unit identity to check this way, so they stay all-or-nothing.
            self.files_created = not self.env['plot.inventory'].search_count(
                [('investment_id', '=', self.id), ('investor_file_id', '=', False)])
        else:
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
                # rebate_on_allotment_ids.rebate_amount is the source of truth
                # per line (scoped to that line's Booking/Confirmation amount)
                # — sum it here instead of re-deriving against total_amount,
                # so the header totals never drift from the line list.
                recs.rebate_on_allotment_ids.compute_rebate_amount()
                dealer_rebate = sum(recs.rebate_on_allotment_ids.filtered(
                    lambda l: l.agent_type == 'dealer').mapped('rebate_amount'))
                marketing_rebate = sum(recs.rebate_on_allotment_ids.filtered(
                    lambda l: l.agent_type == 'marketing_company').mapped('rebate_amount'))
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
            # A multi-bucket deal can have one Booking row per plan-group -
            # require ALL of them paid, not just whichever one happened to be
            # first in the recordset.
            booking_lines = self.investment_plan_ids.filtered(lambda l: l.installment_type in ('down', 'down_payment'))
            if booking_lines and any(l.payment_status != 'paid' for l in booking_lines):
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
            # Refresh the Rebate tab's own per-line amounts and header totals
            # (Total/Dealer/Marketing Rebate) too — they used to only update
            # once, on picking the rebate template, using the old wrong
            # total_amount-based formula, and never tracked this button.
            rec.calculate_rebate()
            for lines in rec.investment_plan_ids:
                if lines.installment_type in ('down', 'down_payment'):
                    # Fixed-basis rebates are per-unit — use THIS row's own
                    # group's unit count (via investment_line_ids), not the
                    # deal's total no_of_units, or a multi-bucket deal with N
                    # Booking rows applies the fixed amount N times over.
                    # Legacy rows (empty investment_line_ids) fall back to the
                    # deal total exactly as before.
                    group_units = sum(lines.investment_line_ids.mapped('no_of_units')) or rec.no_of_units
                    txn_type = 'down_payment' if lines.installment_name == 'Down Payment' else 'booking'
                    marketing_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'marketing_company' and l.transaction_type == txn_type)
                    dealer_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'dealer' and l.transaction_type == txn_type)
                    # Percentage rebates (Booking and Confirmation alike) apply
                    # against the deal's Total Deal Amount, not this
                    # installment line's own amount.
                    lines.marketing_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * group_units
                        for l in marketing_lines
                    )
                    lines.dealer_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * group_units
                        for l in dealer_lines
                    )
                    lines.rebate_amount = lines.marketing_share + lines.dealer_share
                if lines.installment_type == 'confirmation_amount':
                    group_units = sum(lines.investment_line_ids.mapped('no_of_units')) or rec.no_of_units
                    marketing_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'marketing_company' and l.transaction_type == 'confirmation')
                    dealer_lines = rec.rebate_on_allotment_ids.filtered(
                        lambda l: l.agent_type == 'dealer' and l.transaction_type == 'confirmation')
                    lines.marketing_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * group_units
                        for l in marketing_lines
                    )
                    lines.dealer_share = sum(
                        (l.total_rebate / 100) * rec.total_amount if l.calculation_basis == 'percentage'
                        else l.total_rebate * group_units
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
        # One combined credit note for the deal's total dealer share across
        # every Booking/Down Payment row (no 1:1 constraint on account.move
        # the way there is on midland.invoice, so no need for one credit
        # note per group).
        booking_lines = self.investment_plan_ids.filtered(lambda ins: ins.installment_type in ('down', 'down_payment'))
        if booking_lines.filtered(lambda ins: ins.dealer_share > 0):
            dealer_share = sum(booking_lines.mapped('dealer_share'))
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
                booking_lines.move_ids = [(4, rebate_invoice.id)]
            booking_lines.calculate_rebate_given_for_confirmation()

    def receive_payment(self):
        if not self.investment_plan_ids:
            raise ValidationError(_('Create Installment Plan first.'))
        if self.token_id and not self.token_id.token_paid:
            raise ValidationError(_('Please pay fees against this Token: %s .') % self.token_id.serial_number)
        if not self.total_amount:
            self.compute_rebate_amount_process()
            return

        _inv_ref = self.env.ref('real_estate.investment')
        # A multi-bucket deal has one Booking row per plan-group -
        # midland.invoice.investment_installment_id is a strict 1:1 link to a
        # single investment.plan row, so this creates one midland.invoice per
        # Booking row instead of one shared invoice.
        booking_lines = self.investment_plan_ids.filtered(lambda l: l.installment_type == 'down')

        if booking_lines and all(l.invoice_created for l in booking_lines):
            # Booking invoice(s) already exist — either this button was
            # already clicked once, or the invoice was generated through
            # the installment-invoice flow instead. Don't recreate them or
            # repeat the one-time side effects below (auto-payment,
            # history, inventory reservation) — just make sure the
            # deal's state catches up so Create Open File can show.
            if self.state != 'payment':
                self.write({
                    'amount_received': True,
                    'state': 'payment',
                    'payment_states': 'open',
                })
            self.compute_rebate_amount_process()
            return

        # The token is a single deal-wide advance, not per-bucket - split it
        # proportionally across each group's own Booking share, remainder to
        # the last group (avoids rounding leaving a fraction unaccounted for).
        token_fees_total = self.token_id.token_fees if (self.token_id and self.token_id.state == 'paid') else 0
        pending_lines = booking_lines.filtered(lambda l: not l.invoice_created)
        booking_total = sum(pending_lines.mapped('amount')) or self.down_payment

        invoices = self.env['midland.invoice']
        remaining_token = token_fees_total
        for index, booking_line in enumerate(pending_lines):
            is_last = index == len(pending_lines) - 1
            if is_last:
                token_fees = remaining_token
            else:
                line_share = (booking_line.amount / booking_total) if booking_total else 0
                token_fees = round(token_fees_total * line_share)
            remaining_token -= token_fees

            invoice_lines = [(0, 0, {
                'product_id': _inv_ref.id,
                'name': _inv_ref.name,
                # property_account_income_id is company_dependent and this product is
                # shared across every company — always resolve it through this
                # investment's own company, never the ambient env.company.
                'account_id': _inv_ref.with_company(self.company_id or self.env.company).property_account_income_id.id,
                'quantity': 1.0,
                'price_unit': booking_line.amount,
            })]
            if token_fees:
                # the investor already paid the token; knock it off the booking
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
                'investment_installment_id': booking_line.id,
                'invoice_line_ids': invoice_lines,
            })
            inv.action_post()
            invoices |= inv

            booking_line.write({
                'invoice_created': True,
                'invoice_id': inv.jv_id.id if inv.jv_id else False,
            })

            if token_fees:
                # the token was received in advance; settle its share of this
                # group's Booking line so only the net amount stays receivable
                new_paid = (booking_line.amount_paid or 0.0) + token_fees
                remaining = (booking_line.amount or 0.0) - new_paid
                booking_line.write({
                    'amount_paid': min(new_paid, booking_line.amount),
                    'residual': max(remaining, 0.0),
                    'payment_status': 'paid' if remaining <= 0 else 'in_payment',
                })

        if token_fees_total:
            self.token_id.state = 'adjusted'

        # Compute the dealer's Booking rebate before the auto-payment below,
        # so its rebate JV (Bank Dr / Rebate Expense Dr / Advance from
        # Dealer Cr) has a real investment_installment_id.dealer_share to
        # read — otherwise it would fall through to a plain revenue entry.
        self.compute_rebate_amount_process()

        payment_type = self.env.company.payment_type
        if payment_type and payment_type == 'osp' and invoices:
            # Dealer's rebate on each group's Booking line — funded by the
            # dealer rather than cash, so it's netted out of what we ask for
            # in cash below. Wrapped in one midland.payment with one
            # invoice_line per group's invoice (payment_type== 'osp' auto-payment).
            payment_lines = []
            total_net = 0.0
            for inv in invoices:
                dealer_rebate = inv.investment_installment_id.dealer_share or 0.0
                net_amount = inv.amount_total - dealer_rebate
                if net_amount > 0:
                    payment_lines.append((0, 0, {'invoice_id': inv.id, 'payment_amount': net_amount}))
                    total_net += net_amount
            if payment_lines:
                payment = self.env['midland.payment'].create({
                    'payment_for': 'investor',
                    'dealer_id': self.partner_id.id,
                    'partner_id': self.partner_id.partner_id.id,
                    'investment_id': self.id,
                    'payment_amount': total_net,
                    'currency_id': self.env.company.currency_id.id,
                    'journal_id': self.journal_id.id or self.env.company.account_journal_id.id,
                    'company_id': self.env.company.id,
                    'remarks': ', '.join(invoices.mapped('name')),
                    'invoice_line_ids': payment_lines,
                })
                payment.action_confirm()

        self.amount_received = True
        for rec in self:
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
        # NOTE: create_dealer_booking_rebate_bill() used to post a separate
        # dealer rebate credit note here — that's now handled by the
        # midland.payment JV (Bank Dr / Rebate Expense Dr / Advance from
        # Dealer Cr) above, so calling it too would both double-post the
        # rebate and crash (it creates account.move with the removed 'type'
        # field instead of 'move_type').

    def _get_installment_plan_groups(self):
        """A multi-bucket deal (units of different sizes, each with its own
        predefine.plan - own_plan=True) still generates exactly ONE combined
        schedule: one Booking row, one Confirmation row, one recurring series -
        not a separate schedule per plan. Every distinct plan's own
        product-by-product amounts (Booking/Confirmation/Balloon/Possession/
        Balloting) are summed together; the schedule's structure (interval,
        installment count, balloon timing - which products exist at all) is
        borrowed from the first plan encountered, since every plan on a deal
        is expected to share the same schedule shape and only differ in the
        amounts. Source of the units depends on reservation_type: bulk deals
        use investment_line_ids (investment.line), unit deals - where units
        are hand-picked one by one instead of specified by count - use
        inventory_ids (plot.inventory) instead. Activates under multiple_plans,
        and also whenever the header has no single predefine_plan_id of its own
        to fall back on - a deal whose units were assigned their own plans
        (via the Assign Plan wizard) but never had multiple_plans ticked would
        otherwise silently use no plan at all instead of combining the units'
        own plans. When the header does have its own plan, that explicit
        choice is trusted as-is and this per-unit combining is skipped."""
        self.ensure_one()
        if not self.multiple_plans and self.predefine_plan_id:
            return super()._get_installment_plan_groups()
        if self.reservation_type == 'bulk' and self.investment_line_ids:
            source_lines = self.investment_line_ids
        elif self.reservation_type == 'unit' and self.inventory_ids:
            source_lines = self.inventory_ids
        else:
            return super()._get_installment_plan_groups()

        own_plan_lines = source_lines.filtered(lambda l: l.predefine_plan_id)
        if not own_plan_lines:
            return super()._get_installment_plan_groups()
        fallback_lines = source_lines - own_plan_lines

        seen = {}
        for line in own_plan_lines:
            seen.setdefault(line.predefine_plan_id.id, self.env[source_lines._name])
            seen[line.predefine_plan_id.id] |= line

        amount_keys = ('down_payment', 'down_payment_amount', 'confirmation_amount', 'balloting_amount',
                       'possession_amount', 'primary_amount', 'balloon_payment')
        combined = {k: 0.0 for k in amount_keys}
        combined_sub_total = 0.0
        template_plan = None
        for plan_id, lines in seen.items():
            plan = self.env['predefine.plan'].browse(plan_id)
            sub_total = sum(lines.mapped('deal_price'))
            no_of_units = len(lines) if lines._name == 'plot.inventory' else (sum(lines.mapped('no_of_units')) or self.no_of_units)
            params = plan.get_schedule_params(sub_total, no_of_units)
            for key in amount_keys:
                combined[key] += params[key]
            combined_sub_total += sub_total
            if template_plan is None:
                template_plan = plan

        if fallback_lines and self.predefine_plan_id:
            fb_sub_total = sum(fallback_lines.mapped('deal_price'))
            fb_no_of_units = len(fallback_lines) if fallback_lines._name == 'plot.inventory' else (sum(fallback_lines.mapped('no_of_units')) or self.no_of_units)
            fb_params = self.predefine_plan_id.get_schedule_params(fb_sub_total, fb_no_of_units)
            for key in amount_keys:
                combined[key] += fb_params[key]
            combined_sub_total += fb_sub_total

        return [{
            'predefine_plan_id': template_plan,
            'lines': source_lines,
            'sub_total': combined_sub_total,
            'amount_overrides': combined,
        }]

    def create_installment_plan(self):
        # down_payment (and every other schedule field) is otherwise only
        # ever refreshed by the change_booking_and_confirmation() onchange
        # during live editing - editing a field on a line nested inside
        # inventory_ids/investment_line_ids doesn't reliably cascade that
        # onchange up to the parent record, so a deal can sit at
        # down_payment == 0 despite every line already having its own plan.
        # Recompute the real values directly here instead of trusting that
        # onchange having run.
        if self.multiple_plans:
            updates = self._compute_combined_schedule_fields()
            if updates:
                self.write(updates)
        if self.payment_type == 'installments' and not self.down_payment and not self.down_payment_amount:
            raise ValidationError('Please enter booking payment amount.')
        if self.multiple_plans and self.payment_type == 'lump_sum':
            raise ValidationError(_(
                "Lump Sum payment is not supported together with Multiple Plans / bucket deals."))

        if self.payment_type == 'installments':
            # Clear lines that are neither invoiced nor paid before regenerating,
            # so re-running the plan does not duplicate them
            existing = self.investment_plan_ids.filtered(
                lambda l: not l.invoice_created and l.payment_status not in ('in_payment', 'paid'))
            if existing:
                existing.unlink()
            self.installment_created = False
            # Runs the shared per-group generator (real_estate/models/investment.py) -
            # _get_installment_plan_groups() above decides how many groups this
            # deal has and create_installment_plan() calls
            # _create_installment_plan_for_group() once per group. No need to
            # pre-sync balloon/possession/confirmation interval-frequency fields
            # onto self here anymore: predefine.plan.get_schedule_params() (called
            # per-group, including the single-group case) derives them fresh from
            # the plan every time instead of relying on stale self.* values.
            super().create_installment_plan()

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

    def _group_available_pool(self, booking_balance, installment_type='down'):
        # booking_balance (the deal-level line's net_payment) is
        # cumulative/monotonic - it reflects ALL cash ever received against
        # the group's invoice, not just what's new since the last call. Every
        # installment.plan row of this installment_type already credited
        # (whether fully 'paid' or partially 'in_payment') has to be
        # subtracted back out here, otherwise a second call re-spends the
        # same cash on top of what an earlier call already gave out -
        # harmless while every open file was always created in one batch,
        # but a real over-credit once files get created incrementally across
        # several calls.
        #
        # NOT filtered by investor_file_id.predefine_plan_id: a multi-plan
        # deal's units keep their OWN individual predefine_plan_id
        # (create_open_file()'s vals), but _get_installment_plan_groups()
        # always collapses the whole deal into exactly ONE combined Booking/
        # Confirmation row regardless - so a unit whose own plan differs from
        # the row's plan_id still draws from the same single pool. Matching
        # on that plan_id here would silently exclude such units from ever
        # being topped up/marked paid, no matter how much cash comes in.
        group_installments = self.env['installment.plan'].search(
            [('investor_file_id.investment_id', '=', self.id),
             ('installment_type', '=', installment_type)])
        already_distributed = sum(group_installments.mapped('amount_paid'))
        return group_installments, booking_balance - already_distributed

    def _distribute_installment_pool(self, installment_type):
        for rec in self:
            # Even on a multi-plan deal, _get_installment_plan_groups() always
            # collapses the whole deal into ONE combined row per type - units
            # keep their own individual predefine_plan_id, but they all draw
            # from this single deal-wide pool, not a per-plan-group one.
            pool_lines = rec.investment_plan_ids.filtered(
                lambda l: l.installment_type == installment_type and l.amount_paid > 0)
            if not pool_lines or rec.company_id.id == 1:
                continue
            rec.set_net_payment_data()
            for pool_line in pool_lines:
                # amount_paid already reflects the invoice's true paid amount,
                # whether settled by cash or by a rebate netted off against it -
                # a rebate-settled invoice is just as usable to fund open files'
                # installment lines as a cash-settled one, so the full
                # amount_paid is distributed, same as the Open File eligibility
                # check in file_creation_wizard.py.
                pool = pool_line.amount_paid
                group_installments, adjustment_amount = rec._group_available_pool(
                    pool, installment_type)
                all_installments = group_installments.filtered(
                    lambda l: l.payment_status in ('not_paid', 'in_payment') and l.residual > 0)
                if not all_installments or adjustment_amount <= 0:
                    continue
                for lines in all_installments.sorted(
                        key=lambda r: (r.investor_file_id.file_created, r.investor_file_id.issuance_request_created),
                        reverse=True):
                    if adjustment_amount <= 0:
                        break
                    diff = adjustment_amount - lines.residual
                    if not diff < 0:
                        lines.amount_paid += lines.residual
                        adjustment_amount -= lines.residual
                    else:
                        lines.amount_paid += adjustment_amount
                        adjustment_amount = 0
                    lines.residual = lines.amount - lines.amount_paid
                    if lines.residual == 0:
                        lines.payment_status = 'paid'
                    elif lines.amount_paid > 0:
                        lines.payment_status = 'in_payment'
                    lines.net_payment = lines.amount_paid - lines.dealer_share
                    lines.compute_net_payment()

    def update_booking_amount_on_open_files(self):
        for rec in self:
            booking_lines = rec.investment_plan_ids.filtered(
                lambda l: l.installment_type in ('down', 'down_payment') and l.amount_paid > 0)
            if not booking_lines:
                continue
            open_files = self.env['investor.file'].search(
                [('investment_id', '=', rec.id), ('state', '!=', 'cancel')])
            for file in open_files:
                file.update_rebate_values_for_booking()
        self._distribute_installment_pool('down')
        self._distribute_installment_pool('down_payment')

    def update_confirmation_amount_on_open_files(self):
        self._distribute_installment_pool('confirmation_amount')

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
