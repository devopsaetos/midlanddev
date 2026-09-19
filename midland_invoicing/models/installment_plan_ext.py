# -*- coding: utf-8 -*-
from odoo import api, fields, models


class InstallmentPlanExt(models.Model):
    _inherit = 'installment.plan'

    midland_document_no = fields.Char(
        string='Document No.', compute='_compute_midland_document_no',
        help="Legacy invoice number, or the posted midland invoice number(s) "
             "for lines invoiced through midland_invoicing (which leave "
             "invoice_id/invoice empty).")

    @api.depends('invoice', 'invoice_id')
    def _compute_midland_document_no(self):
        invoices = self.env['midland.invoice'].sudo().search([
            ('installment_id', 'in', self.ids),
            ('state', '=', 'posted'),
        ])
        names = {}
        for inv in invoices:
            names.setdefault(inv.installment_id.id, []).append(inv.name)
        for rec in self:
            rec.midland_document_no = rec.invoice or ', '.join(names.get(rec.id, []))

    @api.depends('invoice_created', 'invoice_id', 'amount_paid')
    def _payment_date(self):
        """Lines invoiced through midland_invoicing have no invoice_id, so
        the base compute looks up multi.invoice.payment with
        invoice_id = False and picks up an unrelated payment's date (a paid
        Down Payment showing a date months before the actual payment). For
        those lines take the date of the latest confirmed midland payment
        instead; unpaid ones get no date.
        """
        super()._payment_date()
        midland_lines = self.filtered(lambda r: not r.invoice_id)
        if not midland_lines:
            return
        payment_lines = self.env['midland.payment.line'].sudo().search([
            ('invoice_id.installment_id', 'in', midland_lines.ids),
            ('payment_id.state', '=', 'confirmed'),
        ], order='payment_date, id')
        latest = {}
        for pl in payment_lines:
            latest[pl.invoice_id.installment_id.id] = pl.payment_date
        for rec in midland_lines:
            rec.payment_date = latest.get(rec.id) if rec.amount_paid > 0 else False
