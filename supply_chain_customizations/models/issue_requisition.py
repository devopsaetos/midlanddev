from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class IssueRequistion(models.Model):
    _name = 'issue.requistion'
    _description = 'Issue Requistion'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.model
    def _default_picking_type(self):
        return self._get_picking_type(self.env.context.get('company_id') or self.env.company.id)

    request_by_id = fields.Many2one('res.users', default=lambda self: self.env.user, tracking=True)
    name = fields.Char(string="Service Number", readonly=True, required=True, copy=False, default='New', tracking=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    schedule_date = fields.Date(string='Schedule Date')
    operation_type = fields.Selection([('transfer', 'Transfer'), ('consumption', 'Consumption')], 'Operation',
                                      required=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)
    # branch_id = fields.Many2one('res.branch', string="Branch", default=lambda self: self.env.user.branch_id, tracking=True)
    location_id = fields.Many2one('stock.location', 'Source Location', domain="[('usage','=','internal')]",
                                  check_company=True, tracking=True)
    location_dest_id = fields.Many2one('stock.location', 'Destination Location', domain="[('usage','=','internal')]",
                                       check_company=True, tracking=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', states={'draft': [('readonly', False)]},
                                      default=_default_picking_type, domain="[('code','=','internal')]")

    warehouse_id = fields.Many2one('stock.warehouse', ondelete='restrict', tracking=True)
    line_ids = fields.One2many('issue.requistion.line', 'issue_requistion_id', copy=True, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('valid', 'Valid'), ('issue', 'Issued')],
                             string='Status', default='draft', tracking=True)
    maintenance_request_id = fields.Many2one('maintenance.request')


    @api.model
    def _get_picking_type(self, company_id):
        picking_type = self.env['stock.picking.type'].search(
            [('code', '=', 'internal'), ('warehouse_id.company_id', '=', company_id)])
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search(
                [('code', '=', 'internal'), ('warehouse_id', '=', False)])
        return picking_type[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'issue.requestion') or 'New'
        result = super().create(vals_list)
        return result


    def _get_stock_transaction_lines(self):
        lines = []
        for line in self.line_ids:
            rec_dict = {
                'product_id': line.product_id.id,
                'product_uom_id': line.uom_id.id,
                'scrap_qty': line.quantity,
                'total_req_qty': line.quantity,
                'check_req': True,
                'analytic_account_id': line.analytic_account_id.id or False,
                # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)] or False,
                'memo_text': line.memo_text or False
            }
            lines.append((0, 0, rec_dict))
        return lines

    def _get_stock_transaction(self):
        rec_dict = {'date': self.date,
                    'request_by_id': self.request_by_id.id or False,
                    'type': 'issue',
                    'legacy_ref_no': self.name,
                    'location_id': self.location_id.id or False,
                    'company_id': self.company_id.id or False,
                    # 'branch_id': self.branch_id.id or False,
                    'state': 'draft',
                    'line_ids': self._get_stock_transaction_lines()
                    }

        return rec_dict

    def _create_transaction_stock(self):
        stock_transaction = self.env['stock.transaction'].create(self._get_stock_transaction())
        return stock_transaction

    def _get_stock_picking_lines(self):
        lines = []
        for line in self.line_ids:
            rec_dict = {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.uom_id.id or False,
                'product_uom_qty': line.quantity or False,
                # 'branch_id': line.issue_requistion_id.branch_id.id or False,
                'location_id': line.issue_requistion_id.location_id.id or False,
                'location_dest_id': line.location_dest_id.id or False,
                'description_picking': line.product_id.name

            }
            lines.append((0, 0, rec_dict))
        return lines

    def _get_stock_picking(self):

        rec_dict = {'date': self.date,
                    'location_id': self.location_id.id or False,
                    'location_dest_id': self.location_dest_id.id or False,
                    # 'branch_id': self.branch_id.id or False,
                    'origin': self.name or False,
                    'picking_type_id': self.picking_type_id.id or False,
                    'partner_id': self.request_by_id.partner_id.id,
                    'state': 'draft',
                    'move_ids_without_package': self._get_stock_picking_lines()
                    }

        return rec_dict

    def _create_stock_picking(self):
        stock_picking = self.env['stock.picking'].create(self._get_stock_picking())
        return stock_picking.action_confirm()


    def action_set_confirm(self):
        return self.write({'state': 'valid'})

    def action_set_issued(self):
        if self.maintenance_request_id:
            self.maintenance_request_id.line_ids = self._get_lines()
        if self.operation_type == 'consumption':
            self._create_transaction_stock()
            for rec in self.line_ids:
                stock_transaction_line = rec.env['stock.transaction.line'].search(
                    [('product_id', '=', rec.product_id.id)])
                stock_transaction_line.fecth_product_location()
            return self.write({'state': 'issue'})
        else:
            if self.location_dest_id and self.picking_type_id:
                self._create_stock_picking()
                return self.write({'state': 'issue'})
            else:
                raise ValidationError("Please enter Source Location and Operation Type")

    def _get_lines(self):
        lines = []
        for rec in self.line_ids:
            lines.append((0, 0, {'product_id': rec.product_id.id,
                                 'uom_id': rec.uom_id.id,
                                 'quantity': rec.quantity,
                                 }))
        return lines

    @api.constrains('date')
    def _check_date(self):
        if self.date > fields.Datetime.now():
            raise ValidationError("Future Time and Date can't be selected")



class IssueRequistionLine(models.Model):
    _name = 'issue.requistion.line'
    _inherit = ['mail.thread']
    _description = 'Issue Requistion Line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.issue_requistion_id:
                record.issue_requistion_id.message_post(body=_("Product added: %s (Qty: %s)") % (record.product_id.display_name, record.quantity))
        return records

    def write(self, vals):
        if 'product_id' in vals or 'quantity' in vals:
            for record in self:
                product = self.env['product.product'].browse(vals.get('product_id', record.product_id.id))
                qty = vals.get('quantity', record.quantity)
                record.issue_requistion_id.message_post(body=_("Product updated: %s (Qty: %s)") % (product.display_name, qty))
        return super().write(vals)

    def _child_location_id(self):
        return self.env.context.get('location_dest_id')

    issue_requistion_id = fields.Many2one('issue.requistion', tracking=True)
    product_id = fields.Many2one('product.product', 'Product', required=True, tracking=True)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string="UoM", store=True, readonly=False, tracking=True)
    quantity = fields.Float(string="Quantity", default=1.0, tracking=True)
    onhand_quantity = fields.Float('On-hand Quantity', tracking=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', tracking=True)
    location_dest_id = fields.Many2one('stock.location', 'Location', tracking=True)
    # analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    memo_text = fields.Char(string="Remarks", tracking=True)
    cost_center_id = fields.Many2one(
        'account.cost.center',
        string='Cost Center', tracking=True)
    #
    @api.onchange('product_id')
    def onchange_onhand_quantity(self):
        for rec in self:
            if rec.product_id:
                quanty =sum( self.env['stock.quant'].search(
                    [('location_id.usage', '=', 'internal'), ('product_id', '=', rec.product_id.id)]).mapped(
                    'quantity'))
                rec.onhand_quantity = quanty

