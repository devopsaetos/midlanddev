# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .file_ext import _INSTALLMENT_PRODUCT


class InvestmentExt(models.Model):
    _inherit = 'investment'

    midland_invoice_ids = fields.One2many(
        'midland.invoice', 'investment_id', string='Midland Invoices',
    )
    midland_invoice_count = fields.Integer(
        compute='_compute_midland_invoice_count', string='Invoices',
    )

    @api.depends('midland_invoice_ids')
    def _compute_midland_invoice_count(self):
        for rec in self:
            rec.midland_invoice_count = len(rec.midland_invoice_ids)

    # ── Helper: resolve xml ref → product.realestate ─────────────────────────
    def _resolve_product(self, xml_ref):
        prod = self.env.ref(xml_ref, raise_if_not_found=False)
        if not prod or prod._name != 'product.realestate':
            return self.env['product.realestate']
        return prod

    # ── New: create first un-invoiced installment (cron handles the rest) ──────
    def action_generate_installment_invoices(self):
        for rec in self:
            already_invoiced = rec.midland_invoice_ids.mapped('investment_installment_id').ids
            plans = rec.investment_plan_ids.filtered(
                lambda l: l.id not in already_invoiced and not l.invoice_created
            ).sorted('date')

            if not plans:
                raise ValidationError(_('All installments already have invoices, or no plan exists.'))

            # Generate only the first uninvoiced installment — cron handles the rest
            plan = plans[0]
            xml_ref = _INSTALLMENT_PRODUCT.get(plan.installment_type, 'real_estate.installment_product')
            pp = rec._resolve_product(xml_ref)

            inv = self.env['midland.invoice'].create({
                'partner_id': rec.partner_id.partner_id.id if rec.partner_id.partner_id else False,
                'invoice_date': plan.date or fields.Date.today(),
                'property_invoice_type': 'investment_installment',
                'investment_installment_id': plan.id,
                'investment_id': rec.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': pp.id if pp else False,
                    'name': pp.name if pp else (plan.installment_name or 'Installment'),
                    'account_id': pp.property_account_income_id.id if pp and pp.property_account_income_id else False,
                    'quantity': 1.0,
                    'price_unit': plan.amount,
                })],
            })
            plan.write({
                'invoice_created': True,
                'invoice_id': inv.jv_id.id if inv.jv_id else False,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'midland.invoice',
            'view_mode': 'list,form',
            'domain': [('investment_id', '=', self.id)],
            'context': {'default_investment_id': self.id},
        }

    # ── Scheduled Action: auto-generate invoices for due installments ─────────
    @api.model
    def _cron_generate_due_investment_installment_invoices(self):
        today = fields.Date.today()
        due_plans = self.env['investment.plan'].search([
            ('date', '<=', today),
            ('invoice_created', '=', False),
            ('investment_id', '!=', False),
        ])

        from collections import defaultdict
        plans_by_investment = defaultdict(list)
        for plan in due_plans:
            plans_by_investment[plan.investment_id.id].append(plan)

        for investment_id, plans in plans_by_investment.items():
            investment_rec = self.browse(investment_id)
            already_invoiced = investment_rec.midland_invoice_ids.mapped('investment_installment_id').ids

            for plan in plans:
                if plan.id in already_invoiced:
                    continue

                xml_ref = _INSTALLMENT_PRODUCT.get(plan.installment_type, 'real_estate.installment_product')
                pp = investment_rec._resolve_product(xml_ref)

                inv = self.env['midland.invoice'].create({
                    'partner_id': investment_rec.partner_id.partner_id.id if investment_rec.partner_id.partner_id else False,
                    'invoice_date': plan.date,
                    'property_invoice_type': 'investment_installment',
                    'investment_installment_id': plan.id,
                    'investment_id': investment_rec.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': pp.id if pp else False,
                        'name': pp.name if pp else (plan.installment_name or plan.installment_type or 'Installment'),
                        'account_id': pp.property_account_income_id.id if pp and pp.property_account_income_id else False,
                        'quantity': 1.0,
                        'price_unit': plan.amount,
                    })],
                })
                plan.write({
                    'invoice_created': True,
                    'invoice_id': inv.jv_id.id if inv.jv_id else False,
                })

    # ── Smart button action ────────────────────────────────────────────────────
    def action_view_midland_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'midland.invoice',
            'view_mode': 'list,form',
            'domain': [('investment_id', '=', self.id)],
            'context': {'default_investment_id': self.id},
        }
