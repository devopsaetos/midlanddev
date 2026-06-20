# -*- coding: utf-8 -*-
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from collections import OrderedDict


class ChargeType(models.Model):
    _name = 'charge.type'
    _description = 'Charge Type'

    name = fields.Char(string="Charge Type", required=True)
    account_control_id = fields.Many2one('account.account', string="Account Allowed")


class StockTransaction(models.Model):
    _name = 'stock.transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Stock Transaction'
    _order = 'id desc'

    def _get_default_scrap_location_id(self):
        company_id = self.env.context.get('default_company_id') or self.env.company.id
        return self.env['stock.location'].search(
            [('usage', '=', 'inventory'), ('company_id', 'in', [company_id, False])], limit=1).id

    name = fields.Char('Transaction#', required=True, index=True, copy=False, default='New', readonly=True, tracking=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True, tracking=True)
    type = fields.Selection(selection=[('issue', 'Issue'), ('return', 'Return'), ('transfer_in', 'Transfer IN'),
                                       ('transfer_out', 'Transfer Out')], default='issue', required=True, tracking=True)

    legacy_ref_no = fields.Char('Ref', tracking=True)

    @api.onchange('legacy_ref_no')
    def _onchange_legacy_ref_no(self):
        if self.legacy_ref_no:
            old_transaction = self.env['stock.transaction'].search([
                ('name', '=', self.legacy_ref_no)
            ], limit=1)
            if old_transaction and old_transaction.line_ids:
                lines = [(5, 0, 0)]
                for line in old_transaction.line_ids:
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'charge_type': line.charge_type.id,
                        'scrap_qty': line.scrap_qty,
                        'source_location_id': line.source_location_id.id,
                        'analytic_account_id': line.analytic_account_id.id,
                        'cost_center_id': line.cost_center_id.id,
                        'memo_text': line.memo_text,
                    }))
                self.line_ids = lines
                

    scrap_location_id = fields.Many2one(
        'stock.location', 'Scrap Location', default=_get_default_scrap_location_id,
        domain="[('usage', '=', 'inventory'), ('company_id', 'in', [company_id, False])]", required=True,
        state={'confirm': [('readonly', True)]}, check_company=True)
    request_by_id = fields.Many2one('res.users')
    # branch_id = fields.Many2one('res.branch', string="Branch", default=lambda self: self.env.user.branch_id, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Source Warehouse', tracking=True)
    target_warehouse_id = fields.Many2one('stock.warehouse', 'Target Warehouse',tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)
    location_id = fields.Many2one('stock.location', 'Location', domain="[('usage', '=', 'internal')]", state={'confirm': [('readonly', True)]}, tracking=True)
    state = fields.Selection(
        [('draft', 'New'), ('confirm', 'Done'), ('cancelled', 'Cancelled'), ('rejected', 'Rejected')], string='Status',
        default='draft', tracking=True)
    cost_center_id = fields.Char(string='Cost Center')
    line_ids = fields.One2many(comodel_name='stock.transaction.line',
                               inverse_name='transaction_id',
                               string='Product Details',
                               required=False, tracking=True)
    location_updated = fields.Boolean(compute='_update_locations')
    returned_by = fields.Char('Returned By')

    # Issue Requisition Fields
    parent_transtion_id = fields.Many2one('stock.transaction', required=False)
    check_req = fields.Boolean()
    total_back_order = fields.Integer('Back Orders', compute='_get_total_back_order')

    def _get_total_back_order(self):
        for rec in self:
            rec.total_back_order = len(self.env['stock.transaction'].search([('parent_transtion_id', '=', rec.id)]))

    def button_view_suborders(self):
        context = dict(self._context or {})
        return {
            'name': _('Sub Contract'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'stock.transaction',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('parent_transtion_id', '=', self.id)],
            'context': context,
        }

    def create_back_order_stock_move(self, lines):
        stock_move_lines = [(0, 0, {
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom_id.id,
            'scrap_qty': line.total_req_qty - line.scrap_qty,
            'total_req_qty': line.total_req_qty - line.scrap_qty,
            'check_req': True,
            'analytic_account_id': line.analytic_account_id.id or False,
            # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)] or False,
            'memo_text': line.memo_text or False
        }) for line in lines]
        stock_transaction = {'date': self.date,
                             'parent_transtion_id': self.id,
                             'type': 'issue',
                             'legacy_ref_no': self.legacy_ref_no,
                             'location_id': self.location_id.id or False,
                             'company_id': self.company_id.id or False,
                             # 'branch_id': self.branch_id.id or False,
                             'state': 'draft',
                             'line_ids': stock_move_lines
                             }
        back_order = self.env['stock.transaction'].create(stock_transaction)

    def action_print_st_return_report(self):
        report = self.env.ref('supply_chain_customizations.action_stock_transactions_return_note').report_action(self)
        return report

    @api.depends('line_ids.product_id', 'line_ids.product_location_ids')
    def _update_locations(self):
        for rec in self:
            rec.location_updated = any(line.product_location_ids for line in rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'stock.transaction') or 'New'
        return super(StockTransaction, self).create(vals_list)

    def _get_product_acount_id(self, line):
        return line.product_id.categ_id.property_stock_valuation_account_id.id

    def _prepare_stock_move_values(self, line):
        self.ensure_one()
        cost_price = self.env['product.price.history'].search(
            [('product_id', '=', line.product_id.id), ('datetime', '<=', line.transaction_id.date), ], order="id desc",
            limit=1).cost
        inventory_out = False
        if self.type in ('issue', 'transfer_out'):
            inventory_out = True
        return {
            'origin': line.transaction_id.name,
            'company_id': line.transaction_id.company_id.id,
            'product_id': line.product_id.id,
            'product_uom': line.product_uom_id.id,
            'price_unit': cost_price,
            'date': self.date,
            'date_deadline': self.date,
            'state': 'draft',
            'product_uom_qty': line.scrap_qty,
            'location_id': line.source_location_id.id if inventory_out else line.transaction_id.scrap_location_id.id,
            'location_dest_id': line.transaction_id.scrap_location_id.id if inventory_out else line.source_location_id.id,
            'stock_transaction_id': line.transaction_id.id,
            'stock_transaction_line_id': line.id,
            'move_line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'quantity': line.scrap_qty,
                'location_id': line.source_location_id.id if inventory_out else line.transaction_id.scrap_location_id.id,
                'location_dest_id': line.transaction_id.scrap_location_id.id if inventory_out else line.source_location_id.id,
            })],
            'picked': True,
        }

    def set_to_confirm(self):
        return self.write({'state': 'confirm'})

    def _prepare_account_move_values(self, line, move):
        cost_price = self.env['product.price.history'].sudo().search(
            [('product_id', '=', line.product_id.id), ('datetime', '<=', line.transaction_id.date), ], order="id desc",
            limit=1).cost
        if self.type in ('issue', 'transfer_out'):
            debit_account_id = line.charge_type.account_control_id.id
            credit_account_id = line.transaction_id._get_product_acount_id(line)
        else:
            credit_account_id = line.charge_type.account_control_id.id
            debit_account_id = line.transaction_id._get_product_acount_id(line)
        move_id = move.sudo().account_move_id
        if move_id:
            move_id.sudo().write({'state': 'draft',
                                  'date': line.transaction_id.date,
                                  'amount_total': cost_price * line.scrap_qty})
            for val in move_id.sudo().line_ids:
                if val.debit == False or 0.00:
                    val.sudo().write({'account_id': credit_account_id,
                                      'amount_currency': -1 * (cost_price * line.scrap_qty)})
                if val.credit == False or 0.00:
                    val.sudo().write({'account_id': debit_account_id,
                                      'amount_currency': cost_price * line.scrap_qty})
            move_id.sudo().action_post()

    def _check_availability(self):
        available = False
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self.line_ids.filtered(lambda x: x.state == 'draft'):
            available_qty = sum(self.env['stock.quant']._gather(line.product_id, line.source_location_id,
                                                                strict=True).mapped('quantity'))
            scrap_qty = line.product_uom_id._compute_quantity(line.scrap_qty, line.product_id.uom_id)
            if float_compare(available_qty, scrap_qty, precision_digits=precision) >= 0:
                available = True
            else:
                available = False
                break
        return available

    def action_create_moves(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        # Check availability for all lines first
        for line in self.line_ids.filtered(lambda x: x.state == 'draft'):
            if self.type in ('issue', 'transfer_out'):
                if not line.source_location_id:
                    raise UserError(_("Please select a Source Location for product %s") % line.product_id.display_name)
                
                available_qty = sum(self.env['stock.quant']._gather(line.product_id, line.source_location_id,
                                                                    strict=True).mapped('quantity'))
                scrap_qty = line.product_uom_id._compute_quantity(line.scrap_qty, line.product_id.uom_id)
                if float_compare(available_qty, scrap_qty, precision_digits=precision) < 0:
                    ctx = dict(self.env.context)
                    ctx.update({
                        'default_product_id': line.product_id.id,
                        'default_location_id': line.source_location_id.id,
                        'default_quantity': scrap_qty,
                        'default_product_uom_name': line.product_uom_id.name
                    })
                    return {
                        'name': line.product_id.display_name + _(': Insufficient Quantity To Scrap'),
                        'view_mode': 'form',
                        'res_model': 'stock.warn.insufficient.qty.scrap',
                        'view_id': self.env.ref('stock.stock_warn_insufficient_qty_scrap_form_view').id,
                        'type': 'ir.actions.act_window',
                        'context': ctx,
                        'target': 'new'
                    }

        # If we reached here, all draft lines are available or it's a return
        summary = _("Transaction Confirmed:\n")
        for line in self.line_ids.filtered(lambda x: x.state == 'draft'):
            summary += _("- %s: %s %s\n") % (line.product_id.display_name, line.scrap_qty, line.product_uom_id.name)
            move = self.env['stock.move'].sudo().create(self._prepare_stock_move_values(line))
            move.sudo().with_context(is_scrap=self.type in ('issue', 'transfer_out'))._action_done()
            self.sudo()._prepare_account_move_values(line, move)
            line.write({'state': 'confirm'})

        self.message_post(body=summary)
        self.set_to_confirm()

    @api.constrains('date')
    def _check_date(self):
        if self.date > fields.Datetime.now():
            raise ValidationError("Future Time and Date can't be selected")

    @api.onchange('warehouse_id')
    def location_id_domain(self):
        if self.warehouse_id:
            res = {'domain': {'location_id': [('id', '=', self.warehouse_id.lot_stock_id.id)]}}
            if not self.location_id:
                self.location_id = self.warehouse_id.lot_stock_id.id
            for line in self.line_ids:
                # If the line's source location is not in the new warehouse, clear it or set it to default
                if line.source_location_id and line.source_location_id.warehouse_id != self.warehouse_id:
                    line.source_location_id = self.warehouse_id.lot_stock_id.id
                elif not line.source_location_id:
                    line.source_location_id = self.warehouse_id.lot_stock_id.id
            return res

    def action_get_stock_move_lines(self):
        action = self.env['ir.actions.act_window']._for_xml_id('supply_chain_customizations.custom_stock_move_action')
        action['domain'] = [('stock_transaction_id', '=', self.id)]
        return action


class StockTransactionLine(models.Model):
    _name = 'stock.transaction.line'
    _inherit = ['mail.thread']
    _description = 'Stock Transaction Line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.transaction_id:
                record.transaction_id.message_post(body=_("Product added: %s (Qty: %s)") % (record.product_id.display_name, record.scrap_qty))
        return records

    def write(self, vals):
        if 'product_id' in vals or 'scrap_qty' in vals:
            for record in self:
                product = self.env['product.product'].browse(vals.get('product_id', record.product_id.id))
                qty = vals.get('scrap_qty', record.scrap_qty)
                record.transaction_id.message_post(body=_("Product updated: %s (Qty: %s)") % (product.display_name, qty))
        return super().write(vals)

    def _get_default_charge_type(self):
        return self.env['charge.type'].search(
            [('name', 'in', ('default', 'Default'))], limit=1).id

    charge_type = fields.Many2one('charge.type', string="Charge Type", default=_get_default_charge_type, tracking=True)
    product_id = fields.Many2one('product.product', 'Product', required=True, tracking=True)
    # product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)

    transaction_id = fields.Many2one('stock.transaction', string="Issuance Return Id", ondelete='cascade')
    legacy_ref_no = fields.Char('Legacy reference no.', tracking=True)
    scrap_qty = fields.Float('Quantity', default=1.0, required=True, tracking=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string='UoM', tracking=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', tracking=True)
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    source_location_id = fields.Many2one('stock.location', 'Source Location', ondelete='restrict', tracking=True)
    onhand_quantity = fields.Float('On-hand Qty', tracking=True)
    # free_qty = fields.Float('Free to Use Qty', store=True, related='product_id.free_qty')
    reserved_qty = fields.Float('Reserved Qty', tracking=True)
    state = fields.Selection([('draft', 'New'), ('confirm', 'Done')], string='Status', default='draft', tracking=True)
    product_location_ids = fields.Many2many('stock.location', string='locations', compute='_compute_product_location_ids')
    memo_text = fields.Char(string="Remarks", tracking=True)
    cost_center_id = fields.Many2one(
        'account.cost.center',
        string='Cost Center', tracking=True)

    # Issue Requisition Fields
    total_req_qty = fields.Float('Required Quantity')
    check_req = fields.Boolean()
    ''' This was not giving the right value for reserved_qty'''

    @api.depends('transaction_id.warehouse_id')
    def _compute_product_location_ids(self):
        for rec in self:
            warehouse = rec.transaction_id.warehouse_id
            # branch = rec.transaction_id.branch_id
            if warehouse:
                # If a specific warehouse is selected, only show its internal locations
                locations = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('warehouse_id', '=', warehouse.id)
                ])
                rec.product_location_ids = locations.ids
            elif branch:
                # If no warehouse but a branch is selected, show all internal locations for all warehouses in that branch
                # warehouses = self.env['stock.warehouse'].search([('branch_id', '=', branch.id)])
                locations = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('warehouse_id', 'in', warehouses.ids)
                ])
                rec.product_location_ids = locations.ids
            else:
                rec.product_location_ids = self.env['stock.location'].browse()

    def fecth_product_location(self):
        # This method is now redundant as product_location_ids is a compute field.
        # We keep it for compatibility with calls from other models.
        pass

    @api.onchange('product_id')
    def onchange_product_id_change(self):
        for rec in self:
            if rec.product_id:
                # rec.transaction_id._update_locations()  # No longer needed as it's computed
                if not rec.source_location_id and rec.transaction_id.warehouse_id:
                    rec.source_location_id = rec.transaction_id.warehouse_id.lot_stock_id.id

    @api.onchange('source_location_id')
    def onchange_source_location_id(self):
        if self.source_location_id and self.product_id:
            quantity = self.env['stock.quant'].search(
                [('product_id', '=', self.product_id.id), ('location_id', '=', self.source_location_id.id)]).mapped(
                'quantity')
            if self.transaction_id.type in ('issue', 'transfer_out'):
                if quantity and quantity[0] < 0.01:
                    raise UserError(_("Quantity is less than 0.01 please enter positive quantity value"))
            if quantity:
                self.onhand_quantity = quantity[0]
            else:
                self.onhand_quantity = 0.0

    def fecth_product_location_old(self):
        # Renamed and kept for reference, but should not be called.
        pass

    @api.onchange('source_location_id')
    def onchange_onhand_quantity(self):
        # for rec in self:

        if self.product_id:
            quantitys = self.env['stock.quant'].search(
                [('product_id', '=', self.product_id.id), ('location_id', '=', self.source_location_id.id)]).mapped(
                'quantity')
            return {'domain': {'onhand_quantity': [('quantity', '=', quantitys)]}}
        print("Done")
