# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MultiInvoicePayment(models.Model):
    # Extends the model default_payment already defines (see manifest depends) - was
    # incorrectly re-declared with _name, which left load order between the two modules
    # undefined and caused default_payment's fields to be missing during view validation.
    _inherit = "multi.invoice.payment"

    # Not required: standalone/advance payments (not reconciled against a specific bill)
    # legitimately have no invoice here - existing data already has such rows.
    invoice_id = fields.Many2one('account.move')
    payment_id = fields.Many2one('account.payment')
    partner_id = fields.Many2one('res.partner', related='invoice_id.partner_id', store=True)
    name = fields.Char(related='invoice_id.name')
    invoice_date = fields.Date(related='invoice_id.invoice_date')
    invoice_date_due = fields.Date(related='invoice_id.invoice_date_due')
    amount_total_signed = fields.Monetary(related='invoice_id.amount_total')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id')
    payment_due = fields.Monetary(compute='_compute_payment_due', store=True)
    payment_amount = fields.Monetary()

    @api.depends('invoice_id.amount_residual')
    def _compute_payment_due(self):
        for rec in self:
            rec.payment_due = rec.invoice_id.amount_residual if rec.invoice_id else 0.0

    @api.onchange('payment_due')
    def _onchange_payment_due(self):
        if not self.payment_amount:
            self.payment_amount = self.payment_due
