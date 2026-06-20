# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import get_lang


class MaterialPurchaseRequisition(models.Model):
    _name = "material.purchase.requisition"
    _description = "Material Purchase Requisition"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'sequence'

    @api.model
    def default_get(self, flds):
        result = super(MaterialPurchaseRequisition, self).default_get(flds)
        result['requisition_date'] = datetime.now()
        return result

    def action_cancel(self):
        res = self.write({'state': 'cancel'})
        for line in self.requisition_line_ids:
            line.write({'state': 'cancel'})
        return res

    def _get_purchase_order_count(self):
        for po in self:
            po_ids = self.env['purchase.order'].search([('requisition_po_id', '=', po.id)])
            po.purchase_order_count = len(po_ids)

    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string="Requested By", required=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id')
    requisition_responsible_id = fields.Many2one('res.users', string="Prepared By",
                                                 default=lambda self: self.env.user, readonly=True)
    requisition_date = fields.Datetime(string="Requisition Date", default=datetime.now(), readonly=True)
    received_date = fields.Date(string="Received Date", readonly=True)
    schedule_date = fields.Date(string="Schedule Date")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('department', 'Department Approval'),
        ('hod', 'HOD Approval'),
        ('ceo', 'CEO Approval'),
        ('approved', 'Approved'),
        ('reject', 'Rejected'),
        ('cancel', 'Cancel'),
        ('expire', 'Expire'),
    ], string='Stage', default="draft", tracking=True)
    requisition_line_ids = fields.One2many('requisition.line', 'requisition_id', string="Requisition Line ID")
    requisition_details = fields.One2many('requisition.line', 'requisition_id', string='Requisition Details')
    confirmed_by_id = fields.Many2one('res.users', string="Confirmed By")
    department_manager_id = fields.Many2one('res.users', string="Department Manager")
    hod_id = fields.Many2one('res.users', string="HOD")
    ceo_id = fields.Many2one('res.users', string="CEO")
    rejected_by = fields.Many2one('res.users', string="Rejected By")
    confirmed_date = fields.Date(string="Confirmed Date")
    department_approval_date = fields.Date(string="Department Approval Date")
    hod_approval_date = fields.Date(string="HOD Approval Date")
    ceo_approval_date = fields.Date(string="CEO Approval Date")
    rejected_date = fields.Date(string="Rejected Date")
    reason_for_requisition = fields.Text(string="Reason For Requisition")
    internal_picking_id = fields.Many2one('stock.picking', string="Internal Picking")
    purchase_order_count = fields.Integer('Purchase Order', compute='_get_purchase_order_count')
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.company)
    # branch_id = fields.Many2one('res.branch', string="Branch", required=True, default=lambda self: self.env.branch)
    currency_id = fields.Many2one('res.currency', string="Currency",
                                  default=lambda self: self.env.company.currency_id)
    amount_untaxed = fields.Monetary(string='Total Amount', store=True, readonly=True, tracking=True,
                                     compute="_amount_all")
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute="_amount_all")
    requisition_description = fields.Text(string="Description")
    line_number = fields.Integer("Line Number", default=1)
    exchange_rate = fields.Char('Exchange Rate')
    currency_check = fields.Boolean()
    warehouse_id = fields.Many2one('stock.warehouse', string='Ship To')

    @api.onchange('currency_id')
    def on_change_currency_validation(self):
        if self.currency_id == self.env.company.currency_id:
            self.currency_check = True
        else:
            self.currency_check = False

    @api.constrains('requisition_line_ids')
    def _check_product_exist_in_line(self):
        for requisition in self:
            exist_product_list = []
            for line in requisition.requisition_line_ids:
                if line.product_id:
                    if line.product_id.id in exist_product_list:
                        raise ValidationError(_('Product should be one per line.'))
                    exist_product_list.append(line.product_id.id)

    @api.onchange('requisition_line_ids')
    def line_number_default(self):
        self.line_number = len(self.requisition_line_ids) + 1

    @api.depends('requisition_line_ids.total_val')
    def _amount_all(self):
        for requisition in self:
            amount_untaxed = 0.0
            for line in requisition.requisition_line_ids:
                amount_untaxed += line.total_val
            requisition.amount_untaxed = round(amount_untaxed)
            requisition.amount_total = amount_untaxed

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                vals['sequence'] = self.env['ir.sequence'].with_company(
                    vals['company_id']).next_by_code('material.purchase.requisition') or _('New')
            else:
                vals['sequence'] = self.env['ir.sequence'].next_by_code(
                    'material.purchase.requisition') or _('New')
        return super(MaterialPurchaseRequisition, self).create(vals_list)

    def unlink(self):
        if any(move.state not in ('draft', 'cancel') for move in self):
            raise UserError(_('You can only delete in draft state.'))
        return super(MaterialPurchaseRequisition, self).unlink()

    @api.constrains('schedule_date')
    def _check_schedule_date(self):
        for scheduler in self:
            if scheduler.schedule_date:
                if scheduler.schedule_date < fields.Date.today():
                    raise ValidationError(_('Please select a date that does not fall in the past.'))

    def approval_validation(self):
        # Skip validation for admin/superuser
        if self.env.user.has_group('base.group_system'):
            return
        approval_hierarchy_obj = self.env['approval.hierarchy.line'].search([("user_id", "=", self.env.user.id)], limit=1)
        if not approval_hierarchy_obj:
            raise UserError(_('Please provide approval limit for %s') % self.env.user.name)
        if approval_hierarchy_obj.max_limit < self.amount_untaxed:
            raise UserError(
                _("You can't approve requisition worth greater than %s") % approval_hierarchy_obj.max_limit)

    def department_approval(self):
        self.approval_validation()
        return self.write({
            'state': 'hod',
            'department_manager_id': self.env.user.id,
            'department_approval_date': fields.Date.today(),
        })

    def hod_approval(self):
        self.approval_validation()
        return self.write({
            'state': 'ceo',
            'hod_id': self.env.user.id,
            'hod_approval_date': fields.Date.today(),
        })

    def ceo_approval(self):
        self.approval_validation()
        res = self.write({
            'state': 'approved',
            'ceo_id': self.env.user.id,
            'ceo_approval_date': fields.Date.today(),
        })
        for line in self.requisition_line_ids:
            line.write({'state': 'approved'})
        return res

    def confirm_requisition(self):
        self.approval_validation()
        res = self.write({
            'state': 'department',
            'confirmed_by_id': self.env.user.id,
            'confirmed_date': fields.Date.today(),
        })
        for line in self.requisition_line_ids:
            line.write({'state': 'confirm'})

        all_users = self.env['res.users'].search([('share', '=', False)])
        group_xmlids = [
            'purchase_requisitions.group_purchase_requisition_administrator',
            'purchase_requisitions.group_purchase_requisition_department_head',
            'purchase_requisitions.group_purchase_requisition_ceo',
        ]
        users = all_users.filtered(
            lambda u: u.id == self.requisition_responsible_id.user_manager.id
            or any(u.has_group(g) for g in group_xmlids)
        )
        partner_ids = users.mapped('partner_id').ids

        self.message_post(
            body='This Purchase Requisition has been Confirmed Please Approve it!',
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=partner_ids,
        )
        return res

    def reject_requisition(self):
        return self.write({
            'state': 'reject',
            'rejected_by': self.env.user.id,
            'rejected_date': fields.Date.today(),
        })

    def cancel_requisition(self):
        res = self.write({'state': 'cancel'})
        for line in self.requisition_line_ids:
            line.write({'state': 'cancel'})
        return res

    def action_reset_draft(self):
        res = self.write({'state': 'draft'})
        for line in self.requisition_line_ids:
            line.write({'state': 'draft'})
        return res

    def view_lines_status(self):
        return {
            'name': _('Lines Status'),
            'res_model': 'requisition.line',
            'type': 'ir.actions.act_window',
            'view_type': 'list',
            'view_mode': 'list',
            'view_id': self.env.ref('purchase_requisitions.requisition_line_tree_view').id,
            'target': 'new',
            'domain': [('id', 'in', self.requisition_line_ids.ids)],
        }


class RequisitionLine(models.Model):
    _name = "requisition.line"
    _description = "Requisition Line"
    _order = 'id desc'

    def get_schedule_date(self):
        return self.env.context.get('s_date')

    def get_warehouse(self):
        return self.env.context.get('wh_id')

    def get_line_number(self):
        return self.env.context.get('l_no')

    sequence = fields.Integer('Sequence')
    name = fields.Char(string='Description')
    line_number = fields.Integer(string="#", compute='_get_line_number')
    schedule_date = fields.Date(string='Schedule Date', default=get_schedule_date)
    product_id = fields.Many2one('product.template', string="Product",
                                 domain=['|', ('purchase_ok', '=', True), ('sale_ok', '=', True)], required=True)
    # branch_id = fields.Many2one('res.branch', string="Branch", required=True, default=lambda self: self.env.branch)
    warehouse_id = fields.Many2one('stock.warehouse', string="Ship To", required=True)
    qty = fields.Float(string="Quantity", default=0.0)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string="UoM", store=True, readonly=False)
    requisition_id = fields.Many2one('material.purchase.requisition', string="Requisition Line", ondelete='cascade')
    vendor_id = fields.Many2one('res.partner', string="Vendors")
    category_id = fields.Many2one(related='product_id.categ_id', string="Category", store=True)
    price_unit = fields.Float('Unit Price', required=True, default=0.0)
    employee_id = fields.Many2one(related="requisition_id.employee_id")
    department_id = fields.Many2one(related="requisition_id.department_id")
    requisition_date = fields.Datetime(related="requisition_id.requisition_date")
    on_hand_quantity = fields.Float('On Hand Quantity')
    vendor_product_name = fields.Char(string="Vendor Product Name")
    note_to_buyer = fields.Char(string="Note To Buyer")
    note_to_receiver = fields.Char(string="Note To Receiver")
    urgent = fields.Boolean(string='Urgent')
    purchase_order_number = fields.Char(string="Purchase Order Number")
    purchase_order_qty = fields.Float(string="Purchase Order Quantity")
    received_qty = fields.Float(string="Received Quantity")
    purchase_order_balance_qty = fields.Float(string="Purchase Order balance Quantity", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('qo_created', 'QO Created'),
        ('po_created', 'PO Created'),
        ('cancel', 'Cancel'),
    ], string='Stage', readonly=True, default="draft")
    product_expense = fields.Boolean(compute='_compute_product_expense')
    line_no = fields.Integer()
    total_val = fields.Float('Total', compute='_compute_total_amount')
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False, help="Technical field for UX purpose.")
    qty_done = fields.Float('Done')
    remaining_quantity = fields.Float('Remaining', store=True)

    # Line status tracking fields
    rfq_date = fields.Date('RFQ Date')
    rfq_id = fields.Many2one('requisition.order', string='RFQ Number')
    qo_date = fields.Date('Quotation Date')
    quotation_id = fields.Many2one('quotation.order', string='Quotation Number')
    po_id = fields.Many2one('purchase.order', string="Po No")
    po_date = fields.Date('Po Date')
    po_quantity = fields.Float('Po Quantity')
    qty_received = fields.Float('Qty Received')

    @api.onchange('qty')
    def _compute_remaining_qty(self):
        if self.qty:
            self.remaining_quantity = self.qty

    @api.constrains('schedule_date')
    def _check_schedule_date_constraint(self):
        for line in self:
            if line.schedule_date and line.requisition_id.schedule_date:
                if line.schedule_date < line.requisition_id.schedule_date:
                    raise UserError(_("Line schedule date should not less than header schedule date!"))

    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return
        self._product_id_change()

    def _product_id_change(self):
        if not self.product_id:
            return
        product_lang = self.product_id.with_context(
            lang=get_lang(self.env, self.requisition_id.requisition_responsible_id.lang).code
        )
        self.name = self._get_product_purchase_description(product_lang)

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase
        return name

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, qty=0, uom_id=False)
        lines = super(RequisitionLine, self).create(vals_list)
        for line in lines:
            if line.requisition_id.state == 'draft':
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.requisition_id.message_post(body=msg)
        return lines

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))
        return super(RequisitionLine, self).write(values)

    def _get_line_number(self):
        for line in self:
            if line.id:
                line.line_number = len(
                    self.search([('requisition_id', '=', line.requisition_id.id), ('id', '<=', line.id)]))
            else:
                line.line_number = 0

    @api.onchange('schedule_date')
    def _check_schedule_date_onchange(self):
        date = self.env.context.get('s_date')
        if date and self.schedule_date:
            date = datetime.strptime(date, "%Y-%m-%d")
            if self.schedule_date < date.date():
                raise UserError(_('Line schedule date should not be less than schedule date'))

    @api.onchange('purchase_order_qty', 'received_qty')
    def purchase_order_balance_quantity(self):
        self.purchase_order_balance_qty = self.purchase_order_qty - self.received_qty

    @api.constrains('qty')
    def _check_number(self):
        for number in self:
            if len(str(number.qty)) > 20:
                raise UserError(_('Number of digits in quantity must not exceed 20'))

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, "%s" % (rec.requisition_id.sequence or "")))
        return res

    @api.depends('qty', 'price_unit')
    def _compute_total_amount(self):
        for record in self:
            record.total_val = record.qty * record.price_unit

    @api.depends('category_id')
    def _compute_product_expense(self):
        for record in self:
            record.product_expense = record.category_id.is_expense if record.category_id else False

    def action_convert_to_rfq(self):
        request_ids = self.env.context.get('active_ids')
        request_lines = self.env['requisition.line'].search([('id', 'in', request_ids)])
        if request_lines:
            for line in request_lines:
                if line.state == 'rfq_created':
                    raise UserError(_('%s is already in FRQs please unselect to create RFQ') % line.name)
                if line.state == 'qo_created':
                    raise UserError(_('%s is already in Quotations please unselect to create RFQ') % line.name)
        return {
            'name': _('RFQ'),
            'type': 'ir.actions.act_window',
            'res_model': 'requisition.order',
            'view_type': 'form',
            'view_mode': 'form',
            'context': {
                'request_line_ids': request_ids,
                'from_purchasing': True,
            }
        }

    def action_convert_to_po(self):
        requisition_obj = self.env['requisition.line']
        request_ids = self.env.context.get('active_ids')
        requesitions_lines = requisition_obj.browse(request_ids)
        if requesitions_lines:
            for line in requesitions_lines:
                if line.state == 'rfq_created':
                    raise UserError(_('%s is already in FRQs please unselect to create PO') % line.name)
                if line.state == 'qo_created':
                    raise UserError(_('%s is already in Quotations please unselect to create PO') % line.name)
        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_type': 'form',
            'view_mode': 'form',
            'context': {
                'request_line_ids': requesitions_lines.ids,
                'from_purchasing': True,
                'default_date_order': datetime.now(),
                'requisition_po_id': self.requisition_id.ids,
            }
        }

    @api.constrains('qty')
    def _check_qty(self):
        for rec in self:
            if rec.display_type not in ('line_section', 'line_note') and rec.qty <= 0:
                raise UserError(
                    _("Quantity of %s can't be negative or zero. It should be a positive integer") % rec.product_id.name)

    @api.constrains('price_unit')
    def _check_price_unit(self):
        for rec in self:
            if rec.display_type not in ('line_section', 'line_note') and rec.price_unit <= 0:
                raise UserError(
                    _("Unit Price of %s can't be negative or zero. It should be a positive integer") % rec.product_id.name)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    requisition_picking_id = fields.Many2one('material.purchase.requisition', string="Purchase Requisition")


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    destination_location_id = fields.Many2one('stock.location', string="Destination Location")
    requisition_order_id = fields.Many2one('requisition.order')
    committee_notes = fields.Text('Committee Notes')


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    destination_location_id = fields.Many2one('stock.location', string="Destination Location")


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_user_manager(self):
        users_search = self.env['res.users'].search([])
        users = [
            user.id for user in users_search
            if user.has_group('purchase_requisitions.group_requisition_department_manager')
        ]
        return [('id', 'in', users)]

    user_manager = fields.Many2one('res.users', string="User Manager", domain=_get_user_manager)