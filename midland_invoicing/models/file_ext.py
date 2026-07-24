# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# Maps installment_type → product.realestate XML ref
_INSTALLMENT_PRODUCT = {
    'down':                 'real_estate.downpayment_product',
    'installment':          'real_estate.installment_product',
    'balloon':              'real_estate.balloon_payment',
    'final':                'real_estate.final_product',
    'possession_amount':    'real_estate.possession_amount_product',
    'balloting_amount':     'real_estate.balloting_product',
    'confirmation_amount':  'real_estate.confirmation_amount_product',
}


class FileExt(models.Model):
    _inherit = 'file'

    midland_invoice_ids = fields.One2many(
        'midland.invoice', 'file_ids', string='Midland Invoices',
    )
    midland_invoice_count = fields.Integer(
        compute='_compute_midland_invoice_count', string='Invoices',
    )
    # Kept for view compatibility — referenced by a now-inactive DB view
    midland_payment_line_ids = fields.One2many(
        'midland.payment.line', 'file_id', string='Midland Payments',
    )

    @api.depends('midland_invoice_ids')
    def _compute_midland_invoice_count(self):
        for rec in self:
            rec.midland_invoice_count = len(rec.midland_invoice_ids)

    # ── Override: no_of_invoices now counts midland.invoice too ───────────────
    def _compute_no_of_invoices(self):
        super()._compute_no_of_invoices()
        for rec in self:
            rec.no_of_invoices += rec.midland_invoice_count

    # ── Helper: resolve xml ref → product.realestate ─────────────────────────
    def _resolve_product(self, xml_ref):
        prod = self.env.ref(xml_ref, raise_if_not_found=False)
        if not prod or prod._name != 'product.realestate':
            return self.env['product.realestate']
        return prod

    # ── Helper: resolve a product's Revenue Account for this file's own company ──
    # property_account_income_id is company_dependent, and the product is shared
    # across every company — always read it through the file's own company
    # (society_id.company_id), never the ambient env.company (wrong under cron).
    def _resolve_income_account(self, product):
        self.ensure_one()
        if not product:
            return self.env['account.account']
        company = self.society_id.company_id or self.env.company
        return product.with_company(company).property_account_income_id

    # ── Helper: paid member token knocks its fees off the Booking invoice ────
    # Mirrors investment_ext.InvestmentExt._token_adjustment_invoice_line() -
    # investor Deals already net a paid token off their Booking invoice this
    # way; member files had no equivalent, so the token sat uncredited.
    def _token_adjustment_invoice_line(self, plan):
        """Return (token_fees, minus invoice line) when this plan line is the
        Booking of a file whose member token is paid; (0, None) otherwise."""
        self.ensure_one()
        token = self.token_id
        if not token or token.state != 'paid' or plan.installment_type != 'down':
            return 0, None
        pp = self._resolve_product('real_estate.token_adjustment')
        return token.token_fees, (0, 0, {
            'product_id': pp.id if pp else False,
            'name': pp.name if pp else 'Token Adjustment',
            'account_id': self._resolve_income_account(pp).id,
            'quantity': 1.0,
            'price_unit': -token.token_fees,
        })

    def _settle_token_on_plan(self, plan, token_fees):
        """The token was received in advance; settle its share of the Booking
        plan line and mark the token adjusted."""
        if not token_fees:
            return
        new_paid = (plan.amount_paid or 0.0) + token_fees
        remaining = (plan.amount or 0.0) - new_paid
        plan.write({
            'amount_paid': min(new_paid, plan.amount or 0.0),
            'residual': max(remaining, 0.0),
            'payment_status': 'paid' if remaining <= 0 else 'in_payment',
        })
        self.token_id.state = 'adjusted'

    # ── Override: confirmation invoice → midland.invoice ─────────────────────
    def create_confirmation_invoice(self):
        for rec in self:
            conf_plan = rec.installment_plan_ids.filtered(
                lambda l: l.installment_name == 'Confirmation'
            )
            if not conf_plan or conf_plan.invoice_created:
                continue
            if not rec.confirmation_amount:
                continue

            pp = rec._resolve_product('real_estate.confirmation_amount_product')
            inv = self.env['midland.invoice'].create({
                'member_id': rec.membership_id.id,
                'partner_id': rec.membership_id.partner_id.id if rec.membership_id.partner_id else False,
                'invoice_date': conf_plan.date or fields.Date.today(),
                'property_invoice_type': 'confirmation_amount',
                'installment_id': conf_plan.id,
                'file_ids': rec.id,
                'currency_id': rec.currency_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': pp.id,
                    'name': pp.name or 'Confirmation Amount',
                    'account_id': rec._resolve_income_account(pp).id,
                    'quantity': 1.0,
                    'price_unit': rec.confirmation_amount,
                })],
            })
            inv.action_post()
            conf_plan.write({'invoice_created': True, 'invoice_id': inv.jv_id.id if inv.jv_id else False})

    # ── New: create first un-invoiced installment (cron handles the rest) ──────
    def action_generate_installment_invoices(self):
        for rec in self:
            already_invoiced = rec.midland_invoice_ids.mapped('installment_id').ids
            plans = rec.installment_plan_ids.filtered(
                lambda l: l.id not in already_invoiced and not l.invoice_created
            ).sorted('date')

            if not plans:
                raise ValidationError(_('All installments already have invoices, or no plan exists.'))

            # Generate only the first uninvoiced installment — cron handles the rest
            plan = plans[0]
            xml_ref = _INSTALLMENT_PRODUCT.get(plan.installment_type, 'real_estate.installment_product')
            pp = rec._resolve_product(xml_ref)

            invoice_lines = [(0, 0, {
                'product_id': pp.id if pp else False,
                'name': pp.name if pp else (plan.installment_name or 'Installment'),
                'account_id': rec._resolve_income_account(pp).id,
                'quantity': 1.0,
                'price_unit': plan.amount,
            })]
            token_fees, token_line = rec._token_adjustment_invoice_line(plan)
            if token_line:
                invoice_lines.append(token_line)

            inv = self.env['midland.invoice'].create({
                'member_id': rec.membership_id.id,
                'partner_id': rec.membership_id.partner_id.id if rec.membership_id.partner_id else False,
                'invoice_date': plan.date or fields.Date.today(),
                'property_invoice_type': plan.installment_type or 'installment',
                'installment_id': plan.id,
                'file_ids': rec.id,
                'currency_id': rec.currency_id.id,
                'invoice_line_ids': invoice_lines,
            })
            plan.write({
                'invoice_created': True,
                'invoice_id': inv.jv_id.id if inv.jv_id else False,
            })
            rec._settle_token_on_plan(plan, token_fees)
            if plan.installment_type == 'down' and rec.payment_states == 'draft':
                rec.payment_states = 'open'

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'midland.invoice',
            'view_mode': 'list,form',
            'domain': [('file_ids', '=', self.id)],
            'context': {'default_file_ids': self.id},
        }

    # ── Scheduled Action: auto-generate invoices for due installments ─────────
    @api.model
    def _cron_generate_due_installment_invoices(self):
        today = fields.Date.today()
        due_plans = self.env['installment.plan'].search([
            ('date', '<=', today),
            ('invoice_created', '=', False),
            ('file_id', '!=', False),
        ])

        # Group by file_id
        from collections import defaultdict
        plans_by_file = defaultdict(list)
        for plan in due_plans:
            plans_by_file[plan.file_id.id].append(plan)

        for file_id, plans in plans_by_file.items():
            file_rec = self.browse(file_id)
            already_invoiced = file_rec.midland_invoice_ids.mapped('installment_id').ids

            for plan in plans:
                if plan.id in already_invoiced:
                    continue

                xml_ref = _INSTALLMENT_PRODUCT.get(plan.installment_type, 'real_estate.installment_product')
                pp = file_rec._resolve_product(xml_ref)

                invoice_lines = [(0, 0, {
                    'product_id': pp.id if pp else False,
                    'name': pp.name if pp else (plan.installment_name or plan.installment_type or 'Installment'),
                    'account_id': file_rec._resolve_income_account(pp).id,
                    'quantity': 1.0,
                    'price_unit': plan.amount,
                })]
                token_fees, token_line = file_rec._token_adjustment_invoice_line(plan)
                if token_line:
                    invoice_lines.append(token_line)

                inv = self.env['midland.invoice'].create({
                    'member_id': file_rec.membership_id.id,
                    'partner_id': file_rec.membership_id.partner_id.id if file_rec.membership_id.partner_id else False,
                    'invoice_date': plan.date,
                    'property_invoice_type': plan.installment_type or 'installment',
                    'installment_id': plan.id,
                    'file_ids': file_rec.id,
                    'currency_id': file_rec.currency_id.id,
                    'invoice_line_ids': invoice_lines,
                })
                plan.write({
                    'invoice_created': True,
                    'invoice_id': inv.jv_id.id if inv.jv_id else False,
                })
                file_rec._settle_token_on_plan(plan, token_fees)

    # ── Smart button action ────────────────────────────────────────────────────
    def action_view_midland_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'midland.invoice',
            'view_mode': 'list,form',
            'domain': [('file_ids', '=', self.id)],
            'context': {'default_file_ids': self.id, 'default_member_id': self.membership_id.id},
        }
