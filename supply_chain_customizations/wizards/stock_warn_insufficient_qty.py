# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare


class StockTransactionInsufficientQty(models.TransientModel):
    _name = 'stock.insufficient.transaction'
    _description = 'Warn Insufficient Quantity transaction'

    product_id = fields.Many2one('product.product', 'Product', required=True)
    location_id = fields.Many2one( 'stock.location', 'Location', domain="[('usage', '=', 'internal')]", required=True)
    quant_ids = fields.Many2many('stock.quant', compute='_compute_quant_ids')



    @api.depends('product_id')
    def _compute_quant_ids(self):
        for quantity in self:
            quantity.quant_ids = self.env['stock.quant'].search([
                ('product_id', '=', quantity.product_id.id),
                ('location_id.usage', '=', 'internal'),
                ('company_id', '=', quantity.env.user.company_id.id)
            ])

    def action_done(self):
        raise NotImplementedError()

