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
                    'account_id': pp.property_account_income_id.id,
                    'quantity': 1.0,
                    'price_unit': rec.confirmation_amount,
                })],
            })
            inv.action_post()
            conf_plan.write({'invoice_created': True, 'invoice_id': inv.jv_id.id if inv.jv_id else False})

    # ── New: create midland.invoice for every un-invoiced installment ─────────
    def action_generate_installment_invoices(self):
        for rec in self:
            already_invoiced = rec.midland_invoice_ids.mapped('installment_id').ids
            plans = rec.installment_plan_ids.filtered(
                lambda l: l.id not in already_invoiced and not l.invoice_created
            )
            if not plans:
                raise ValidationError(_('All installments already have invoices, or no plan exists.'))

            for plan in plans:
                xml_ref = _INSTALLMENT_PRODUCT.get(plan.installment_type, 'real_estate.installment_product')
                pp = rec._resolve_product(xml_ref)

                inv = self.env['midland.invoice'].create({
                    'member_id': rec.membership_id.id,
                    'partner_id': rec.membership_id.partner_id.id if rec.membership_id.partner_id else False,
                    'invoice_date': plan.date or fields.Date.today(),
                    'property_invoice_type': plan.installment_type or 'installment',
                    'installment_id': plan.id,
                    'file_ids': rec.id,
                    'currency_id': rec.currency_id.id,
                        'invoice_line_ids': [(0, 0, {
                        'product_id': pp.id if pp else False,
                        'name': pp.name if pp else (plan.installment_name or 'Installment'),
                        'account_id': pp.property_account_income_id.id if pp and pp.property_account_income_id else False,
                        'quantity': 1.0,
                        'price_unit': plan.amount,
                    })],
                })
                # Set payment_states to open on first (down) invoice
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
