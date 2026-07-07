from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_lot_serial = fields.Char(string='Lot/Serial', help='Lot or Serial number for tracking')
