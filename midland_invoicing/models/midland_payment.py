# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MidlandPayment(models.Model):
    _name = 'midland.payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Midland Payment'
    _rec_name = 'name'
    _order = 'date desc, id desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Payment Reference', required=True, copy=False,
        readonly=True, index=True,
        default=lambda self: _('New'), tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    # ── Left panel ────────────────────────────────────────────────────────────
    payment_for = fields.Selection([
        ('member', 'Member'),
        ('investor', 'Investor'),
    ], default='member', required=True, string='Payment For', tracking=True)
    file_id = fields.Many2one('file', string='File', tracking=True)
    payment_nature = fields.Selection([
        ('normal', 'Normal Payment'),
        ('on_account', 'On Account'),
    ], default='normal', string='Payment Nature', tracking=True)
    dealer_id = fields.Many2one('res.investor', string='Dealer', tracking=True)
    investment_id = fields.Many2one('investment', string='Investment', tracking=True)
    is_sub_dealer_payment = fields.Boolean(string='Sub Dealer Payment', tracking=True)
    member_id = fields.Many2one('res.member', string='Customer', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Accounting Partner',
        compute='_compute_partner_id', store=True, readonly=False,
    )
    journal_id = fields.Many2one(
        'account.journal', string='Payment Journal',
        domain="[('type', 'in', ['cash', 'bank'])]", tracking=True,
    )
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default='cash', string='Mode Of Payments', tracking=True)
    payment_amount = fields.Monetary(
        string='Payment Amount', currency_field='currency_id', tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    wht_amount = fields.Monetary(
        string='WHT Amount', currency_field='currency_id',
    )
    net_payment = fields.Monetary(
        string='Net Payment', compute='_compute_net_payment',
        store=True, currency_field='currency_id',
    )
    bank_amount = fields.Monetary(
        string='Bank Amount', compute='_compute_bank_amount',
        currency_field='currency_id',
        help='Actual amount that will hit the Bank/Cash account once '
             'confirmed — Net Payment minus any Confirmation dealer rebate '
             'netted against Dealer Clearance Advance instead of cash.',
    )

    # ── Right panel ───────────────────────────────────────────────────────────
    date = fields.Date(string='Date', default=fields.Date.today, tracking=True)
    branch_id = fields.Many2one('res.company', string='Branch', tracking=True)
    payment_amount_calculation = fields.Float(string='Payment Amount Calculation')
    allow_wo_lps = fields.Boolean(string='Allow W/O LPS')
    waive_lps = fields.Boolean(string='Waive LPS')
    override_wht = fields.Boolean(string='Override WHT')
    wht = fields.Float(string='WHT')
    remarks = fields.Char(string='Remarks', tracking=True)
    recovery_reference = fields.Char(string='Recovery Reference')
    internal_notes = fields.Text(string='Internal Notes')

    # ── Invoice Lines ─────────────────────────────────────────────────────────
    invoice_line_ids = fields.One2many(
        'midland.payment.line', 'payment_id', string='Invoices',
    )

    # ── Company ───────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )

    # ── JV link ───────────────────────────────────────────────────────────────
    jv_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False)

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends('payment_for', 'member_id', 'dealer_id')
    def _compute_partner_id(self):
        for rec in self:
            if rec.payment_for == 'investor':
                rec.partner_id = rec.dealer_id.partner_id if rec.dealer_id else False
            else:
                rec.partner_id = rec.member_id.partner_id if rec.member_id else False

    @api.depends('payment_amount', 'wht_amount')
    def _compute_net_payment(self):
        for rec in self:
            rec.net_payment = rec.payment_amount - rec.wht_amount

    @api.depends('net_payment', 'invoice_line_ids.invoice_id.rebate_total',
                 'invoice_line_ids.invoice_id.amount_paid')
    def _compute_bank_amount(self):
        for rec in self:
            confirmation_rebate = sum(
                rec._invoice_confirmation_rebate_amount(line.invoice_id)
                for line in rec.invoice_line_ids if line.invoice_id
            )
            rec.bank_amount = rec.net_payment - confirmation_rebate

    @api.onchange('payment_for')
    def _onchange_payment_for(self):
        if self.payment_for == 'member':
            self.investment_id = False
            self.dealer_id = False
        else:
            self.file_id = False
            self.member_id = False

    @api.onchange('file_id')
    def _onchange_file_id(self):
        if self.file_id:
            self.member_id = self.file_id.membership_id
            self.branch_id = self.file_id.society_id.company_id if self.file_id.society_id else False

    @api.onchange('member_id')
    def _onchange_member_id(self):
        if self.member_id:
            self.partner_id = self.member_id.partner_id

    @api.onchange('dealer_id')
    def _onchange_dealer_id(self):
        if self.investment_id and self.investment_id.partner_id != self.dealer_id:
            self.investment_id = False

    @api.onchange('invoice_line_ids', 'invoice_line_ids.payment_amount')
    def _onchange_invoice_line_ids(self):
        self.payment_amount = sum(self.invoice_line_ids.mapped('payment_amount'))

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('midland.payment') or _('New')
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _get_wht_account(self, company):
        return self.env['account.account'].search(
            [('account_type', '=', 'liability_current'),
             ('company_ids', 'in', company.ids)],
            limit=1
        )

    def _invoice_rebate_amount(self, inv):
        """Dealer rebate funded for `inv` under the Investor/Dealer Booking
        rebate flow (0.0 if that flow doesn't apply). Only returned once per
        invoice — guarded on `amount_paid` so a rebate already settled by an
        earlier payment isn't counted again."""
        self.ensure_one()
        # Booking invoices raised from the investor/dealer flow
        # (investment_ext.py) are always tagged property_invoice_type =
        # 'investment_installment' — the real Booking marker there is the
        # linked Investment Plan line's own installment_type.
        is_booking = (
            inv.property_invoice_type == 'down'
            or (inv.investment_installment_id and inv.investment_installment_id.installment_type == 'down')
        )
        if (self.payment_for == 'investor' and is_booking
                and inv.rebate_total > 0 and not inv.amount_paid):
            return inv.rebate_total
        return 0.0

    def _invoice_confirmation_rebate_amount(self, inv):
        """Dealer rebate to net out of the cash owed when a Confirmation
        invoice is paid — by Member or Investor, independent of the Booking
        rebate flow above. 0.0 if this isn't a Confirmation line or has no
        rebate. Only returned once per invoice (guarded on `amount_paid`)."""
        self.ensure_one()
        is_confirmation = (
            inv.property_invoice_type == 'confirmation_amount'
            or (inv.installment_id and inv.installment_id.installment_type == 'confirmation_amount')
            or (inv.investment_installment_id
                and inv.investment_installment_id.installment_type == 'confirmation_amount')
        )
        if is_confirmation and inv.rebate_total > 0 and not inv.amount_paid:
            return inv.rebate_total
        return 0.0

    def action_confirm(self):
        create_entry = self.env['ir.config_parameter'].sudo().get_param(
            'midland.create_invoice_entry', default='False'
        ) in ('True', '1', 'true')
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft payments can be confirmed.'))
            if not rec.invoice_line_ids:
                raise ValidationError(_('Add at least one invoice before confirming.'))
            if not rec.journal_id:
                raise ValidationError(_('Please select a Payment Journal.'))
            if not rec.payment_amount or rec.payment_amount <= 0:
                raise ValidationError(_('Payment Amount must be greater than zero.'))
            net_pay = rec.payment_amount - (rec.wht_amount or 0.0)
            if net_pay <= 0:
                raise ValidationError(
                    _('Net Payment (%.2f) must be greater than zero. '
                      'Payment Amount: %.2f, WHT: %.2f') % (
                        net_pay, rec.payment_amount, rec.wht_amount or 0.0)
                )

            if rec.payment_for == 'investor':
                partner = rec.partner_id or (rec.dealer_id.partner_id if rec.dealer_id else False)
                if not partner:
                    raise ValidationError(_('Please set a dealer.'))
            else:
                partner = rec.partner_id or (rec.member_id.partner_id if rec.member_id else False)
                if not partner:
                    raise ValidationError(_('Please set a customer.'))

            debit_account = (
                rec.journal_id.default_account_id
                or rec.journal_id.payment_credit_account_id
            )
            if not debit_account:
                raise ValidationError(
                    _('Journal "%s" has no default account configured.') % rec.journal_id.name
                )

            if create_entry:
                rec._confirm_with_entry(partner, debit_account)
            else:
                rec._confirm_no_entry(partner, debit_account)

            rec.state = 'confirmed'
            rec._create_installment_payment_records()

    # ── Mode: true — Dr Bank / Cr Receivable + reconcile ─────────────────────

    def _confirm_with_entry(self, partner, debit_account):
        rec = self
        credit_account = partner.property_account_receivable_id
        if not credit_account:
            raise ValidationError(
                _('Partner "%s" has no receivable account configured.') % partner.name
            )

        jv_lines = [
            (0, 0, {
                'account_id': debit_account.id,
                'partner_id': partner.id,
                'name': rec.name,
                'debit': rec.net_payment,
                'credit': 0.0,
            }),
            (0, 0, {
                'account_id': credit_account.id,
                'partner_id': partner.id,
                'name': rec.name,
                'debit': 0.0,
                'credit': rec.net_payment,
            }),
        ]

        # WHT lines
        if rec.wht_amount > 0:
            wht_account = rec._get_wht_account(rec.company_id)
            if wht_account:
                jv_lines += [
                    (0, 0, {
                        'account_id': credit_account.id,
                        'partner_id': partner.id,
                        'name': _('WHT - %s') % rec.name,
                        'debit': rec.wht_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': wht_account.id,
                        'partner_id': partner.id,
                        'name': _('WHT - %s') % rec.name,
                        'debit': 0.0,
                        'credit': rec.wht_amount,
                    }),
                ]

        jv = self.env['account.move'].create({
            'move_type': 'entry',
            'date': rec.date,
            'journal_id': rec.journal_id.id,
            'company_id': rec.company_id.id,
            'ref': rec.name,
            'line_ids': jv_lines,
        })
        jv.action_post()
        rec.jv_id = jv.id

        # Payment JV receivable credit line (for reconciliation)
        pay_recv_line = jv.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and l.credit > 0
        )

        for line in rec.invoice_line_ids:
            inv = line.invoice_id
            if not inv:
                continue

            # Reconcile payment credit line with invoice receivable debit line
            if inv.jv_id and pay_recv_line:
                inv_recv_line = inv.jv_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                              and l.debit > 0 and not l.reconciled
                )
                if inv_recv_line:
                    (inv_recv_line + pay_recv_line).reconcile()

            # Sync midland.invoice fields from JV after reconciliation
            self._sync_invoice_from_jv(inv, line.payment_amount)
            line.payment_amount_paid = line.payment_amount

    # ── Mode: false — single Dr Bank / Cr Revenue entry at payment time ───────

    def _confirm_no_entry(self, partner, debit_account):
        rec = self

        # Validate revenue accounts before building JV
        for line in rec.invoice_line_ids:
            inv = line.invoice_id
            if not inv:
                continue
            if not inv.invoice_line_ids:
                raise ValidationError(
                    _('Invoice "%s" has no lines. Cannot create payment entry.') % inv.name
                )
            if rec._invoice_rebate_amount(inv) > 0:
                # Rebate lines route to Advance from Dealer, not per-line Revenue.
                continue
            missing = [
                (inv_line.name or inv_line.product_id.name or '?')
                for inv_line in inv.invoice_line_ids
                if not inv_line.account_id
            ]
            if missing:
                raise ValidationError(
                    _('Invoice "%s" — the following lines have no Revenue Account:\n%s\n\n'
                      'Please set Revenue Account on the product (Real Estate Products → %s).')
                    % (inv.name, '\n'.join('• ' + m for m in missing),
                       ', '.join(missing))
                )

        jv_lines = [(0, 0, {
            'account_id': debit_account.id,
            'partner_id': partner.id,
            'name': rec.name,
            'debit': rec.net_payment,
            'credit': 0.0,
        })]

        total_allocated = 0.0
        total_rebate = 0.0
        total_confirmation_rebate = 0.0
        bank_correction = 0.0
        for line in rec.invoice_line_ids:
            inv = line.invoice_id
            if not inv or not inv.invoice_line_ids:
                continue

            total_confirmation_rebate += rec._invoice_confirmation_rebate_amount(inv)

            rebate = rec._invoice_rebate_amount(inv)
            if rebate > 0:
                rebate_account = rec.company_id.rebate_expense_account_id
                if not rebate_account:
                    raise ValidationError(
                        _('Please configure the "Rebate Expense Account" '
                          '(Settings → Invoicing → Midland Invoicing).')
                    )
                advance_account = rec.company_id.advance_from_dealer_account_id
                if not advance_account:
                    raise ValidationError(
                        _('Please configure the "Advance from Dealer Account" '
                          '(Settings → Invoicing → Midland Invoicing).')
                    )

                # Debit: Rebate Expense (before its matching credit below, so
                # the JV reads Bank Dr / Rebate Expense Dr / Advance Cr)
                jv_lines.append((0, 0, {
                    'account_id': rebate_account.id,
                    'partner_id': partner.id,
                    'name': _('Dealer Rebate - %s') % rec.name,
                    'debit': round(rebate, 2),
                    'credit': 0.0,
                }))
                total_rebate += rebate

                # Credit: Advance from Dealer — the invoice's own full
                # value, derived from the invoice itself (not line.payment_amount,
                # which may not have been reduced by the rebate yet if the
                # invoice was picked before Payment For/Dealer were set).
                # `not inv.amount_paid` was already required by
                # _invoice_rebate_amount, so amount_residual == amount_total here.
                cash_amount = round(inv.amount_total - rebate, 2)
                credit_amount = round(inv.amount_total, 2)
                jv_lines.append((0, 0, {
                    'account_id': advance_account.id,
                    'partner_id': partner.id,
                    'name': _('Advance (Booking Rebate) - %s') % inv.name,
                    'debit': 0.0,
                    'credit': credit_amount,
                }))
                total_allocated += credit_amount
                # Correct the header Bank debit for whatever this line's
                # payment_amount actually held vs. the true cash owed
                bank_correction += round(line.payment_amount - cash_amount, 2)
                continue

            ratio = line.payment_amount / inv.amount_total if inv.amount_total else 0.0
            for inv_line in inv.invoice_line_ids:
                revenue_account = inv_line.account_id
                if not revenue_account:
                    continue
                credit_amount = round(inv_line.price_subtotal * ratio, 2)
                if credit_amount <= 0:
                    continue
                jv_lines.append((0, 0, {
                    'account_id': revenue_account.id,
                    'partner_id': partner.id,
                    'name': inv_line.name or inv.name,
                    'debit': 0.0,
                    'credit': credit_amount,
                }))
                total_allocated += credit_amount

        # Fix the header Bank debit for any Booking-rebate line whose
        # payment_amount wasn't actually reduced by the rebate beforehand
        if bank_correction:
            bank_line = dict(jv_lines[0][2])
            bank_line['debit'] = round(bank_line['debit'] - bank_correction, 2)
            jv_lines[0] = (0, 0, bank_line)

        # Confirmation rebate — the customer only owes cash for (invoice
        # total − dealer rebate); the shortfall clears against the same
        # "Dealer Clearance Advance" liability the Dealer Confirmation flow
        # credits. Revenue/advance-to-customer crediting above is unaffected
        # — it still recognizes the invoice's full value.
        if total_confirmation_rebate > 0:
            clearance_account = rec.company_id.dealer_clearance_advance_account_id
            if not clearance_account:
                raise ValidationError(
                    _('Please configure the "Dealer Clearance Advance Account" '
                      '(Settings → Invoicing → Midland Invoicing).')
                )
            bank_line = dict(jv_lines[0][2])
            bank_line['debit'] = round(bank_line['debit'] - total_confirmation_rebate, 2)
            jv_lines[0] = (0, 0, bank_line)
            jv_lines.insert(1, (0, 0, {
                'account_id': clearance_account.id,
                'partner_id': partner.id,
                'name': _('Dealer Clearance - %s') % rec.name,
                'debit': round(total_confirmation_rebate, 2),
                'credit': 0.0,
            }))

        # Rounding correction on last credit line — jv_lines[-1] is always a
        # credit line here (each loop iteration ends by appending one,
        # whether the Advance from Dealer credit or a Revenue credit).
        # bank_correction is subtracted here because Booking-rebate lines
        # already self-balance exactly (cash_amount + rebate == credit_amount
        # by construction) — only non-Booking lines can leave rounding slack.
        diff = (rec.net_payment - bank_correction + total_rebate) - total_allocated
        if diff and len(jv_lines) > 1:
            last = dict(jv_lines[-1][2])
            last['credit'] = round(last['credit'] + diff, 2)
            jv_lines[-1] = (0, 0, last)

        # WHT lines
        if rec.wht_amount > 0:
            wht_account = rec._get_wht_account(rec.company_id)
            if wht_account:
                jv_lines += [
                    (0, 0, {
                        'account_id': debit_account.id,
                        'partner_id': partner.id,
                        'name': _('WHT - %s') % rec.name,
                        'debit': rec.wht_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': wht_account.id,
                        'partner_id': partner.id,
                        'name': _('WHT - %s') % rec.name,
                        'debit': 0.0,
                        'credit': rec.wht_amount,
                    }),
                ]

        jv = self.env['account.move'].create({
            'move_type': 'entry',
            'date': rec.date,
            'journal_id': rec.journal_id.id,
            'company_id': rec.company_id.id,
            'ref': rec.name,
            'line_ids': jv_lines,
        })
        jv.action_post()
        rec.jv_id = jv.id

        # No JV on invoice side — update midland.invoice and installment.plan manually
        for line in rec.invoice_line_ids:
            inv = line.invoice_id
            if not inv:
                continue
            rebate = rec._invoice_rebate_amount(inv)
            # For Booking-rebate lines, the invoice's own total is always
            # what gets settled (cash_amount + rebate == inv.amount_total),
            # regardless of what line.payment_amount happened to hold.
            paid_amount = round(inv.amount_total, 2) if rebate > 0 else line.payment_amount
            new_paid = inv.amount_paid + paid_amount
            if new_paid >= inv.amount_total:
                inv.write({'amount_paid': inv.amount_total, 'payment_state': 'paid'})
            else:
                inv.write({'amount_paid': new_paid, 'payment_state': 'partial'})
            if inv.installment_id:
                self._update_installment(inv.installment_id, paid_amount)
            if inv.investment_installment_id:
                self._update_investment_installment(inv.investment_installment_id, paid_amount,
                                                    invoice=inv)
            line.payment_amount_paid = paid_amount

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sync_invoice_from_jv(self, inv, payment_amount):
        jv_state = inv.jv_id.payment_state if inv.jv_id else False
        if jv_state in ('paid', 'in_payment'):
            paid_amt = inv.amount_total - (inv.jv_id.amount_residual or 0.0)
            inv.write({'payment_state': 'paid', 'amount_paid': paid_amt})
        elif jv_state == 'partial':
            paid_amt = inv.amount_total - (inv.jv_id.amount_residual or 0.0)
            inv.write({'payment_state': 'partial', 'amount_paid': paid_amt})
        else:
            # Fallback — no JV reconciliation happened
            new_paid = inv.amount_paid + payment_amount
            if new_paid >= inv.amount_total:
                inv.write({'amount_paid': inv.amount_total, 'payment_state': 'paid'})
            else:
                inv.write({'amount_paid': new_paid, 'payment_state': 'partial'})
            if inv.installment_id:
                self._update_installment(inv.installment_id, payment_amount)
            if inv.investment_installment_id:
                self._update_investment_installment(inv.investment_installment_id, payment_amount,
                                                    invoice=inv)

    def _update_installment(self, install, payment_amount):
        plan_total = (install.amount or 0.0) + (install.tax_amount or 0.0)
        new_plan_paid = (install.amount_paid or 0.0) + payment_amount
        remaining = plan_total - new_plan_paid
        if remaining <= 0:
            install.write({'payment_status': 'paid', 'amount_paid': plan_total, 'residual': 0.0})
        else:
            install.write({'payment_status': 'in_payment', 'amount_paid': new_plan_paid, 'residual': remaining})

    def _update_investment_installment(self, install, payment_amount, invoice=None):
        plan_total = install.amount or 0.0
        new_plan_paid = (install.amount_paid or 0.0) + payment_amount
        # a token adjustment line makes the invoice net of the plan amount; once
        # the net invoice is fully paid, the whole plan line is settled (the
        # difference was already received with the token)
        if invoice and invoice.payment_state == 'paid' and invoice.amount_total < plan_total:
            new_plan_paid = plan_total
        remaining = plan_total - new_plan_paid
        if remaining <= 0:
            install.write({'payment_status': 'paid', 'amount_paid': plan_total, 'residual': 0.0})
        else:
            install.write({'payment_status': 'in_payment', 'amount_paid': new_plan_paid, 'residual': remaining})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'confirmed' and rec.jv_id and rec.jv_id.state == 'posted':
                # Reverse the payment JV — this also unreconciles any matched lines
                rec.jv_id.button_draft()
                rec.jv_id.button_cancel()
            # Revert midland.invoice custom payment fields
            for line in rec.invoice_line_ids:
                inv = line.invoice_id
                if inv:
                    new_paid = max(0.0, inv.amount_paid - line.payment_amount_paid)
                    new_state = 'not_paid' if new_paid <= 0 else 'partial'
                    inv.write({'amount_paid': new_paid, 'payment_state': new_state})
            rec._delete_installment_payment_records()
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.jv_id and rec.jv_id.state == 'posted':
                raise ValidationError(
                    _('Cannot reset to draft: journal entry %s is posted.') % rec.jv_id.name
                )
            rec._delete_installment_payment_records()
            rec.write({'state': 'draft', 'jv_id': False})

    @api.model
    def _migrate_create_missing_installment_records(self):
        confirmed = self.search([('state', '=', 'confirmed'), ('file_id', '!=', False)])
        FIP = self.env['file.installment.payment']
        for payment in confirmed:
            existing = FIP.search([('midland_payment_line_id.payment_id', '=', payment.id)])
            if existing:
                # Update empty fields on already-created records
                for fip in existing:
                    mpl = fip.midland_payment_line_id
                    inv = mpl.invoice_id if mpl else False
                    vals = {}
                    if not fip.invoice_date and inv and inv.invoice_date:
                        vals['invoice_date'] = inv.invoice_date
                    if not fip.payment_date and payment.date:
                        vals['payment_date'] = payment.date
                    if not fip.property_invoice_type and inv and inv.property_invoice_type:
                        vals['property_invoice_type'] = inv.property_invoice_type
                    if not fip.midland_invoice_ref and inv and inv.name:
                        vals['midland_invoice_ref'] = inv.name
                    if vals:
                        fip.write(vals)
            else:
                payment._create_installment_payment_records()

    def _create_installment_payment_records(self):
        rec = self
        if not rec.file_id:
            return
        FIP = self.env['file.installment.payment']
        for line in rec.invoice_line_ids:
            inv = line.invoice_id
            if not inv:
                continue
            FIP.create({
                'midland_payment_line_id': line.id,
                'name': rec.name,
                'invoice_amount': inv.amount_total,
                'invoice_residual': inv.amount_residual,
                'payment_amount': line.payment_amount_paid or line.payment_amount,
                'file_id': rec.file_id.id,
                'invoice_date': inv.invoice_date,
                'payment_date': rec.date,
                'property_invoice_type': inv.property_invoice_type,
                'midland_invoice_ref': inv.name,
            })

    def _delete_installment_payment_records(self):
        rec = self
        fip = self.env['file.installment.payment'].search(
            [('midland_payment_line_id.payment_id', '=', rec.id)]
        )
        fip.unlink()

    def action_view_jv(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.jv_id.id,
        }

    def action_recompute_lps(self):
        pass

    def action_fix_reconciliation(self):
        """Re-run reconciliation for already-confirmed payments that missed it."""
        for rec in self:
            if rec.state != 'confirmed' or not rec.jv_id:
                continue
            pay_recv_line = rec.jv_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable' and l.credit > 0
            )
            if not pay_recv_line:
                continue
            for line in rec.invoice_line_ids:
                inv = line.invoice_id
                if not inv or not inv.jv_id:
                    continue
                inv_recv_line = inv.jv_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                              and l.debit > 0 and not l.reconciled
                )
                if inv_recv_line:
                    (inv_recv_line + pay_recv_line).reconcile()
                rec._sync_invoice_from_jv(inv, line.payment_amount_paid)


class MidlandPaymentLine(models.Model):
    _name = 'midland.payment.line'
    _description = 'Midland Payment Line'

    payment_id = fields.Many2one(
        'midland.payment', string='Payment',
        required=True, ondelete='cascade', index=True,
    )
    invoice_id = fields.Many2one('midland.invoice', string='Invoice', required=True)
    file_id = fields.Many2one('file', related='payment_id.file_id', store=True, index=True, string='File')

    number = fields.Char(related='invoice_id.name', string='Number', store=True)
    invoice_date = fields.Date(related='invoice_id.invoice_date', store=True)
    payment_date = fields.Date(related='payment_id.date', store=True, string='Payment Date')
    currency_id = fields.Many2one(related='invoice_id.currency_id', store=True)
    due_date = fields.Date(string='Due Date')
    total = fields.Monetary(
        related='invoice_id.amount_total', string='Total',
        currency_field='currency_id', store=True,
    )
    amount_due = fields.Monetary(
        related='invoice_id.amount_residual', string='Amount Due',
        currency_field='currency_id', store=True,
    )
    rebate_amount = fields.Monetary(
        related='invoice_id.rebate_total', string='Rebate',
        currency_field='currency_id', readonly=True,
    )
    payment_amount = fields.Monetary(
        string='Payment Amount', currency_field='currency_id',
    )
    payment_amount_paid = fields.Monetary(
        string='Paid', currency_field='currency_id', readonly=True,
    )

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            rebate = (
                self.payment_id._invoice_rebate_amount(self.invoice_id)
                if self.payment_id else 0.0
            )
            self.payment_amount = self.invoice_id.amount_residual - rebate
