# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DealerConfirmation(models.Model):
    _name = 'dealer.confirmation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Dealer Confirmation Review'
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, index=True, default=lambda self: _('New'),
        tracking=True,
    )
    date = fields.Date(string='Date', default=fields.Date.today, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], default='draft', required=True, tracking=True, copy=False)
    dealer_id = fields.Many2one('res.investor', string='Dealer', required=True, tracking=True)
    investment_id = fields.Many2one(
        'investment', string='Deal', required=True, tracking=True,
        domain="[('partner_id', '=', dealer_id)]",
    )
    journal_id = fields.Many2one('account.journal', string='Journal', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        'dealer.confirmation.line', 'confirmation_id', string='Files',
    )
    confirmation_total = fields.Float(
        string='Confirmation Total', compute='_compute_totals',
    )
    confirmation_paid = fields.Float(
        string='Confirmation Paid', compute='_compute_totals',
    )
    rebate_amount = fields.Float(
        string='Rebate Amount', compute='_compute_totals',
    )
    bank_amount = fields.Float(
        string='Bank Amount', compute='_compute_totals',
        help='Actual cash collected — Confirmation Total minus Rebate.',
    )
    jv_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False)

    @api.depends('line_ids.confirmation_total', 'line_ids.confirmation_paid', 'line_ids.rebate_amount')
    def _compute_totals(self):
        for rec in self:
            rec.confirmation_total = sum(rec.line_ids.mapped('confirmation_total'))
            rec.confirmation_paid = sum(rec.line_ids.mapped('confirmation_paid'))
            rec.rebate_amount = sum(rec.line_ids.mapped('rebate_amount'))
            rec.bank_amount = rec.confirmation_total - rec.confirmation_paid - rec.rebate_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dealer.confirmation') or _('New')
        return super().create(vals_list)

    @api.onchange('dealer_id')
    def _onchange_dealer_id(self):
        self.investment_id = False
        self.line_ids = False

    @api.onchange('investment_id')
    def _onchange_investment_id(self):
        self.line_ids = False
        if not self.investment_id:
            return
        files = self.env['file'].search([
            ('investment_id', '=', self.investment_id.id),
            ('membership_id', '!=', False),  # transferred to a member
            ('file_status', 'in', ('lock', 'approve')),  # locked / approved
            ('investor_file.state', '=', 'issued'),  # issued from the investor file
        ])
        lines = []
        for f in files:
            # only files whose Confirmation installment has actually been
            # invoiced, and that still have an outstanding balance to
            # collect and/or a rebate not yet settled
            conf = f.installment_plan_ids.filtered(
                lambda l: l.installment_type == 'confirmation_amount' and l.invoice_created
                          and (l.amount_paid < l.amount
                               or l.dealer_share > (l.dealer_rebate_given or 0.0))
            )[:1]
            if not conf:
                continue
            lines.append((0, 0, {
                'file_id': f.id,
                'confirmation_total': conf.amount,
                'confirmation_paid': conf.amount_paid,
                'rebate_amount': max(0.0, conf.dealer_share - (conf.dealer_rebate_given or 0.0)),
            }))
        self.line_ids = lines

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft confirmations can be posted.'))
            if not rec.line_ids:
                raise ValidationError(_('Add at least one file before confirming.'))
            if not rec.journal_id:
                raise ValidationError(_('Please select a Journal.'))

            debit_account = (
                rec.journal_id.default_account_id
                or rec.journal_id.payment_credit_account_id
            )
            if not debit_account:
                raise ValidationError(
                    _('Journal "%s" has no default account configured.') % rec.journal_id.name
                )

            # Re-check everything against the LIVE installment.plan /
            # midland.invoice state (not the cached line values), so two
            # drafts racing on the same file can never both settle it.
            # (conf, inv, partner, cash_amount, pending_rebate, has_residual)
            to_settle = []
            skipped = []
            for line in rec.line_ids:
                f = line.file_id
                conf = f.installment_plan_ids.filtered(
                    lambda l: l.installment_type == 'confirmation_amount' and l.invoice_created
                )[:1]
                if not conf:
                    skipped.append(f.name)
                    continue

                residual = round(conf.amount - conf.amount_paid, 2)
                pending_rebate = round(max(0.0, conf.dealer_share - (conf.dealer_rebate_given or 0.0)), 2)
                has_residual = residual > 0

                if not has_residual and pending_rebate <= 0:
                    # nothing left to collect, and rebate already settled
                    skipped.append(f.name)
                    continue

                inv = self.env['midland.invoice'].search(
                    [('installment_id', '=', conf.id)], limit=1
                )
                partner = f.membership_id.partner_id
                if not inv or not partner or (has_residual and not inv.invoice_line_ids):
                    skipped.append(f.name)
                    continue

                if has_residual:
                    pending_rebate = min(pending_rebate, residual)
                    cash_amount = round(residual - pending_rebate, 2)
                else:
                    # invoice was already fully paid (e.g. before rebate
                    # netting existed) — nothing to collect, only the
                    # rebate itself still needs to be recognized
                    cash_amount = 0.0

                to_settle.append((conf, inv, partner, cash_amount, pending_rebate, has_residual))

            if not to_settle:
                raise ValidationError(
                    _('No files with an outstanding Confirmation balance or pending rebate to settle.')
                )

            has_any_rebate = any(pending_rebate > 0 for *_, pending_rebate, _has in to_settle)
            clearance_account = None
            if has_any_rebate:
                clearance_account = rec.company_id.dealer_clearance_advance_account_id
                if not clearance_account:
                    raise ValidationError(
                        _('Please configure the "Dealer Clearance Advance Account" '
                          '(Settings → Invoicing → Midland Invoicing).')
                    )
            rebate_account = None
            if any(not has_residual and pending_rebate > 0 for *_, pending_rebate, has_residual in to_settle):
                rebate_account = rec.company_id.rebate_expense_account_id
                if not rebate_account:
                    raise ValidationError(
                        _('Please configure the "Rebate Expense Account" '
                          '(Settings → Invoicing → Midland Invoicing) — needed for files '
                          'already fully paid whose rebate is still pending.')
                    )

            jv_lines = []
            for conf, inv, partner, cash_amount, pending_rebate, has_residual in to_settle:
                if cash_amount > 0:
                    jv_lines.append((0, 0, {
                        'account_id': debit_account.id,
                        'partner_id': partner.id,
                        'name': _('Confirmation - %s') % conf.file_id.name,
                        'debit': cash_amount,
                        'credit': 0.0,
                    }))

                if not has_residual:
                    # already fully paid — just recognize and clear the
                    # rebate, no invoice re-crediting
                    if pending_rebate > 0:
                        jv_lines.append((0, 0, {
                            'account_id': rebate_account.id,
                            'partner_id': partner.id,
                            'name': _('Confirmation Rebate - %s') % conf.file_id.name,
                            'debit': pending_rebate,
                            'credit': 0.0,
                        }))
                        jv_lines.append((0, 0, {
                            'account_id': clearance_account.id,
                            'partner_id': rec.dealer_id.partner_id.id or partner.id,
                            'name': _('Confirmation Rebate - %s') % conf.file_id.name,
                            'debit': 0.0,
                            'credit': pending_rebate,
                        }))
                    continue

                if pending_rebate > 0:
                    # cash collected is short of the invoice total by the
                    # rebate amount — that shortfall clears against Dealer
                    # Clearance Advance (not a fresh expense — the rebate
                    # was already recognized when this file's Booking was
                    # settled, or will be via a separate confirmation line)
                    jv_lines.append((0, 0, {
                        'account_id': clearance_account.id,
                        'partner_id': partner.id,
                        'name': _('Confirmation Rebate - %s') % conf.file_id.name,
                        'debit': pending_rebate,
                        'credit': 0.0,
                    }))

                # Credit: the invoice's own revenue/advance accounts,
                # prorated to (cash collected + rebate settled)
                total_settled = cash_amount + pending_rebate
                ratio = total_settled / inv.amount_total if inv.amount_total else 0.0
                credit_lines = []
                allocated = 0.0
                for inv_line in inv.invoice_line_ids:
                    if not inv_line.account_id:
                        continue
                    credit_amount = round(inv_line.price_subtotal * ratio, 2)
                    if credit_amount <= 0:
                        continue
                    credit_lines.append((0, 0, {
                        'account_id': inv_line.account_id.id,
                        'partner_id': partner.id,
                        'name': inv_line.name or inv.name,
                        'debit': 0.0,
                        'credit': credit_amount,
                    }))
                    allocated += credit_amount
                diff = round(total_settled - allocated, 2)
                if diff and credit_lines:
                    last = dict(credit_lines[-1][2])
                    last['credit'] = round(last['credit'] + diff, 2)
                    credit_lines[-1] = (0, 0, last)
                jv_lines += credit_lines

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
            rec.state = 'confirmed'

            # Update invoice / installment paid tracking, and mark the
            # rebate portion as given so it can't be settled again
            for conf, inv, partner, cash_amount, pending_rebate, has_residual in to_settle:
                if has_residual:
                    # only advance amount_paid when cash/rebate was actually
                    # applied against an outstanding balance — a file that
                    # was already fully paid before this confirm has nothing
                    # new to record here beyond the rebate itself, below
                    paid_amount = cash_amount + pending_rebate
                    new_inv_paid = inv.amount_paid + paid_amount
                    if new_inv_paid >= inv.amount_total:
                        inv.write({'amount_paid': inv.amount_total, 'payment_state': 'paid'})
                    else:
                        inv.write({'amount_paid': new_inv_paid, 'payment_state': 'partial'})

                    new_conf_paid = conf.amount_paid + paid_amount
                    if new_conf_paid >= conf.amount:
                        conf.write({'payment_status': 'paid', 'amount_paid': conf.amount, 'residual': 0.0})
                    else:
                        conf.write({
                            'payment_status': 'in_payment', 'amount_paid': new_conf_paid,
                            'residual': conf.amount - new_conf_paid,
                        })
                if pending_rebate > 0:
                    conf.write({
                        'dealer_rebate_given': (conf.dealer_rebate_given or 0.0) + pending_rebate,
                        'rebate_given': (conf.rebate_given or 0.0) + pending_rebate,
                    })

            if skipped:
                rec.message_post(
                    body=_('Skipped (no outstanding balance, or missing invoice/customer): %s')
                    % ', '.join(skipped)
                )

    def action_reset_to_draft(self):
        for rec in self:
            if rec.jv_id and rec.jv_id.state == 'posted':
                raise ValidationError(
                    _('Cannot reset to draft: journal entry %s is posted. Reverse it first.')
                    % rec.jv_id.name
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


class DealerConfirmationLine(models.Model):
    _name = 'dealer.confirmation.line'
    _description = 'Dealer Confirmation Review Line'

    confirmation_id = fields.Many2one(
        'dealer.confirmation', string='Dealer Confirmation',
        required=True, ondelete='cascade', index=True,
    )
    file_id = fields.Many2one('file', string='File', required=True)
    confirmation_total = fields.Float(string='Confirmation Total')
    confirmation_paid = fields.Float(string='Confirmation Paid')
    rebate_amount = fields.Float(string='Rebate Amount')

    @api.onchange('file_id')
    def _onchange_file_id(self):
        if not self.file_id:
            self.confirmation_total = self.confirmation_paid = self.rebate_amount = 0.0
            return
        conf = self.file_id.installment_plan_ids.filtered(
            lambda l: l.installment_type == 'confirmation_amount' and l.invoice_created
        )[:1]
        self.confirmation_total = conf.amount if conf else 0.0
        self.confirmation_paid = conf.amount_paid if conf else 0.0
        self.rebate_amount = (
            max(0.0, conf.dealer_share - (conf.dealer_rebate_given or 0.0)) if conf else 0.0
        )
