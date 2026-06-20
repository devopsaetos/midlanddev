# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, AccessError, ValidationError


class PurchaseOrderExt(models.Model):
    _inherit = 'purchase.order'
    _order = 'id desc'

    requisition_rfq_id = fields.Many2one('quotation.order', string="Purchase Quotation")
    requisition_po_id = fields.Many2many('material.purchase.requisition', string="Purchase Requisition")
    rfq_type = fields.Selection([
        ('standard', 'Standard'),
        ('bid', 'Bid RFQ')
    ], string='PO Type', default='standard', readonly=True)

    state = fields.Selection(selection_add=[
        ('draft', 'Draft'),
        ('sent', 'In Process'),
        ('to approve', 'To Approve'),
        ('manager_approval', 'Manager Approval'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)
    requisition_responsible_id = fields.Many2one('res.users', string="Requester", readonly=True,
                                                 default=lambda self: self.env.user and self.env.user.id or False)

    @api.model
    def default_get(self, fields_list):
        res = super(PurchaseOrderExt, self).default_get(fields_list)
        selected_products = self._context.get('request_line_ids')
        requisition_id = self._context.get('requisition_po_id')
        if selected_products:
            selected_line_ids = self.env['requisition.line'].browse(selected_products)
            values = []
            if selected_line_ids:
                for line in selected_line_ids:
                    result = {
                        'category_id': line.category_id and line.category_id.id or False,
                        'product_id': line.product_id and line.product_id.id or False,
                        'name': line.name or '',
                        'product_qty': line.remaining_quantity or 0.0,
                        'product_uom': line.uom_id and line.uom_id.id or False,
                        'price_unit': line.price_unit,
                        'date_planned': line.schedule_date or False,
                        'requisition_line_id': line.id,
                        'warehouse_id': line.warehouse_id.id or False,
                        'picking_type_id': line.warehouse_id.in_type_id.id if line.warehouse_id else False,
                    }
                    values.append((0, 0, result))
                res['state'] = 'draft'
                res['order_line'] = values
                res['requisition_po_id'] = [x for x in requisition_id] if requisition_id else False
                res['company_id'] = selected_line_ids[0].requisition_id.company_id.id or False
        return res

    def button_cancel(self):
        order_lines = self.order_line
        for line in order_lines:
            requisition_line = self.env['requisition.line'].search([('id', '=', line.requisition_line_id.id)])
            if requisition_line and requisition_line.qty_done != 0:
                requisition_line.write({
                    'remaining_quantity': requisition_line.remaining_quantity + line.product_uom_qty or 0.0,
                    'qty_done': requisition_line.qty_done - line.product_uom_qty or 0.0,
                    'state': 'approved',
                })
        return super(PurchaseOrderExt, self).button_cancel()


class PurchaseOrderLineExt(models.Model):
    _inherit = 'purchase.order.line'

    category_id = fields.Many2one('product.category', string="Item Category")
    product_expense = fields.Boolean(compute='_compute_product_expense')
    requisition_line_id = fields.Many2one('requisition.line')

    @api.depends('category_id')
    def _compute_product_expense(self):
        for record in self:
            record.product_expense = record.category_id.is_expense if record.category_id else False

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))
        return super(PurchaseOrderLineExt, self).write(values)

    @api.onchange('product_qty')
    def _onchange_line_quantity(self):
        if self.order_id.requisition_po_id:
            for rec in self.order_id.requisition_po_id.requisition_line_ids:
                if self.product_id == rec.product_id and self.product_qty > rec.qty:
                    raise UserError(_("You cannot exceed the quantity more than requested quantity"))