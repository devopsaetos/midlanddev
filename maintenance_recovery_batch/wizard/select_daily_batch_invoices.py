# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SelectDailyBatchInvoices(models.TransientModel):
    _name = 'select.daily.batch.invoices'
    _description = 'Select Daily Batch Invoices'

    batch_maintenance_id = fields.Many2one('daily.maintenance.batch')
    house_ids = fields.Many2many('plot.inventory', string='House')
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    line_ids = fields.One2many('select.daily.batch.invoice.lines', 'batch_invoice_id')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    @api.onchange('house_ids', 'product_id')
    def search_invoices(self):
        for rec in self:
            if rec.house_ids and rec.product_id:
                rec.line_ids = [(5, 0, 0)]
                files = self.env['file'].search([('inventory_id', 'in', rec.house_ids.ids)])
                partners = files.mapped('membership_id')
                if rec.product_id.name == 'Maintenance Charges':
                    moves = self.env['account.move'].search(
                        [('property_invoice_type', '=', 'maintenance_charges'), ('amount_residual', '>', 0.0),
                         ('partner_id', 'in', partners.ids)])
                    for move in moves:
                        rec.line_ids = [(0, 0, {'invoice_id': move.id,
                                                "batch_invoice_id": rec.id})]

    def confirm_lines(self):
        pass


class SelectDailyBatchInvoiceLines(models.TransientModel):
    _name = 'select.daily.batch.invoice.lines'
    _description = 'Select Daily Batch Invoice Lines'

    batch_invoice_id = fields.Many2one('select.daily.batch.invoices')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    is_select = fields.Boolean(default=False)
