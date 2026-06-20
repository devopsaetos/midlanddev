# -*- coding: utf-8 -*-


from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import float_compare
from odoo.tools.misc import formatLang, get_lang

class RequisitionOrder(models.Model):
    _name = "requisition.order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Requisition Order (RFQ)"
    _order = 'id desc'

    @api.model
    def default_get(self, fields):
        ctx = dict(self.env.context)
        res = super(RequisitionOrder, self.with_context(ctx)).default_get(fields)
        selected_products = self._context.get('request_line_ids')
        if selected_products:
            selected_line_ids = self.env['requisition.line'].browse(selected_products)
            values = []
            if selected_line_ids:
                for line in selected_line_ids:
                    result = {
                        'category_id': line.category_id.id or False,
                        'product_id': line.product_id and line.product_id.id or False,
                        'name': line.name or '',
                        'display_type': line.display_type or False,
                        'product_qty': line.qty or 0.0,
                        'product_uom': line.uom_id.id or False,
                        'requisition_line_id': line.id,
                        'schedule_date': line.schedule_date or False,
                        # 'branch_id': line.branch_id.id or False,
                        'warehouse_id': line.warehouse_id.id or False,
                    }
                    values.append((0, 0, result))
                res['order_line_ids'] = values
                res['company_id'] = selected_line_ids[0].requisition_id.company_id.id or False
        return res


    READONLY_STATES = {
        'requisition': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }


    name = fields.Char('Order Reference', index=True, default='New')
    sequence = fields.Integer(string='Sequence', default=10)
    origin = fields.Char('Source Document',
                         help="Reference of the document that generated this requisition order "
                              "request (e.g. a sales order)")
    partner_ref = fields.Char('Vendor Reference', copy=False, \
                              help="Reference of the sales order or bid sent by the vendor. "
                                   "It's used to do the matching when you receive the "
                                   "products as this reference is usually written on the "
                                   "delivery order sent by your vendor.")
    rfq_type = fields.Selection([('standard', 'Standard'), ('bid', 'Bid RFQ')], string='RFQ Type', default='bid')
    issue_date = fields.Datetime('Issue Date', default=fields.Datetime.now)
    creation_date = fields.Datetime('Creation Date', default=fields.Datetime.now)
    closure_date = fields.Datetime('RFQ Validity Date', states=READONLY_STATES, index=True, copy=False,
                                   help="Depicts the date where the Quotation should be validated and converted into a requisition order.")
    date_approve = fields.Date('Approval Date', readonly=1, index=True, copy=False)
    partner_id = fields.Many2many('res.partner', string='Vendor', required=True, states=READONLY_STATES,
                                  change_default=True, track_visibility='always')
    currency_id = fields.Many2one('res.currency', 'Currency', states=READONLY_STATES, \
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    # branch_id = fields.Many2one('res.branch', string="Central Branch")
    # operation_type = fields.Selection(related='company_id.operation_type', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requisition', 'Confirm'),
        ('approved', 'Approved'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    order_line_ids = fields.One2many('requisition.order.line', 'order_id', string='Order Lines')
    order_line = fields.One2many('requisition.order.line', 'order_id', string='Order Line', related='order_line_ids', readonly=False)

    notes = fields.Text('Terms and Conditions')
    date_submission = fields.Datetime(string='Date Response')

    product_id = fields.Many2one('product.product', string='Product')
    create_uid = fields.Many2one('res.users', 'Responsible')
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, readonly=True)

    requisition_responsible_id = fields.Many2one('res.users', string="Requester", readonly=True,
                                                 default=lambda self: self.env.user and self.env.user.id or False)
    quotation_order_count = fields.Integer('Quotation Order', compute='_get_rfq_order_count')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True,
                                     track_visibility='onchange')
    amount_tax = fields.Monetary(string='Tax', store=True, readonly=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True)
    payment_terms = fields.Many2one('account.payment.term', string='Payment Terms')
    notes = fields.Text('Terms and Conditions')
    member_committee_ids = fields.Many2many(comodel_name='hr.employee', string='Committee Member')
    employee_ids = fields.One2many(
        comodel_name='hr.employee',
        inverse_name='requisition_order_id',
        string='Member Committee',
        required=False)

    evaluation_criteria_ids = fields.One2many('evaluation.connector', 'requisition_order_id', ondelete="cascade")

    @api.onchange('creation_date')
    def default_date_validity(self):
        if self.creation_date:
            self.closure_date = self.creation_date

    @api.constrains('issue_date')
    def issue_date_validation(self):
        if self.issue_date:
            if self.issue_date.date() < fields.Datetime.now().date():
                raise UserError(_('Issue Date should not fall in past'))
            if self.issue_date > self.closure_date:
                raise UserError(_('Issue Date should not greater than RFQ Validity Date'))
            if self.issue_date.date() < self.creation_date.date():
                raise UserError(_('Issue Date should not less than creation date'))

    @api.constrains('creation_date')
    def creation_date_validation(self):
        if self.creation_date:
            if self.creation_date.date() < fields.Datetime.now().date():
                raise UserError(_('Creation Date should not fall in past'))


    # Method to validate closure date #
    @api.onchange('closure_date')
    def closure_date_validation(self):
        if self.closure_date:
            if self.closure_date.date() < self.issue_date.date() or self.closure_date.date() < self.creation_date.date():
                raise UserError(_('RFQ Validity Date should not less than issue date or creation Date'))

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('partner_ref', operator, name)]
        pos = self.search(domain + args, limit=limit)
        return pos.name_get()

    @api.depends('name', 'partner_ref')
    def name_get(self):
        result = []
        for po in self:
            name = po.name
            if po.partner_ref:
                name += ' (' + po.partner_ref + ')'
            if self.env.context.get('show_total_amount') and po.amount_total:
                name += ': ' + formatLang(self.env, po.amount_total, currency_obj=po.currency_id)
            result.append((po.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('requisition.order') or '/'
        res = super(RequisitionOrder, self).create(vals_list)
        for rec in res:
            requisition_line_ids = self.env['requisition.line'].search([('id', 'in', rec.order_line_ids.requisition_line_id.ids)])
            for line in requisition_line_ids:
                line.write({
                    'state': 'rfq_created',
                    'rfq_date': fields.Date.today(),
                    'rfq_id': rec.id or False,
                })
        return res

    def unlink(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(_('In order to delete a requisition order, you must cancel it first.'))
        return super(RequisitionOrder, self).unlink()

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.currency_id = False
        else:
            self.currency_id = self.env.user.company_id.currency_id.id

    def button_draft(self):
        self.write({'state': 'draft'})
        return {}

    def button_unlock(self):
        self.write({'state': 'approved'})

    def button_done(self):
        self.write({'state': 'done'})

    def button_cancel(self):
        self.write({'state': 'cancel'})

    def button_confirm(self):
        self.write({'state': 'requisition'})
        for order in self:
            if not order.partner_id:
                raise UserError(_('Please select at least one vendor to create RFQ'))

    def button_approve(self):
        # if self.env.company.operation_type == 'centralized' and self.env.branch.id != self.env.company.centralized_branch_id.id:
        #     raise UserError(
        #         'You are not Allowed to approve an rfq from this branch if system is in centralized state you have to log in through central branch to approve this rfq!')
        precision = self.env['decimal.precision'].precision_get('Quantity')
        for order in self:
            if order.state not in ['requisition']:
                continue
            quotation_order_obj = self.env['quotation.order']
            quotation_order_line_obj = self.env['quotation.order.line']
            evaluation_criteria_obj = self.env['evaluation.connector']
            if order.partner_id:
                for vendor in order.partner_id:
                    vals = {
                        'partner_id': vendor and vendor.id or False,
                        'date_order': datetime.now(),
                        'origin': order.name,
                        'state': 'draft',
                        'requisition_rfq_id': order.id,
                        'rfq_type': order.rfq_type,
                        'closure_date': order.closure_date,
                        'payment_term_id': order.payment_terms.id,
                        'requisition_responsible_id': order.requisition_responsible_id and order.requisition_responsible_id.id or False,
                        'company_id': order.company_id.id or False,
                        'currency_id': order.currency_id and order.currency_id.id or False
                    }
                    quotation_order = quotation_order_obj.create(vals)
                    # evaluation portion starting from here
                    for line in order.evaluation_criteria_ids:
                        evaluation_line_vals = {
                            'field_id': line.field_id.id or False,
                            'value': line.value or " ",
                            'quotation_order_id': quotation_order and quotation_order.id or False
                        }
                        evaluation_lines = evaluation_criteria_obj.create(evaluation_line_vals)
                    # evaluation portion ending here
                    for line in order.order_line_ids:
                        check_qty = False
                        qo_line_vals = {
                            'category_id': line.category_id and line.category_id.id or False,
                            'product_id': line.product_id and line.product_id.id or False,
                            'expected_price': line.price_unit,
                            'rfq_qty': line.product_qty or 0.0,
                            'requisition_line_id': line.requisition_line_id.id or False,
                            'product_qty': line.product_qty or 0.0,
                            'display_type': line.display_type or False,
                            'name': line.name or ' ',
                            # 'branch_id': line.branch_id.id or False,
                            'warehouse_id': line.warehouse_id.id or False,
                            'price_unit': line.price_unit,
                            'product_uom': line.product_uom and line.product_uom.id or False,
                            'order_id': quotation_order and quotation_order.id or False,
                            'state': 'draft',
                        }
                        quotation_order_line = quotation_order_line_obj.create(qo_line_vals)
                        order.write({'state': 'approved'})
                        if line.requisition_line_id.qty == line.product_qty or float_compare(line.product_qty,
                                                                                             line.requisition_line_id.qty,
                                                                                             precision_digits=precision) >= 0:
                            check_qty = True
                        else:
                            line.requisition_line_id.qty = line.requisition_line_id.qty - line.product_qty

                        if check_qty:
                            line.requisition_line_id.write({
                                'state': 'qo_created',
                                'qo_date': fields.Date.today(),
                                'quotation_id': quotation_order.id or False,
                            })

    def _get_rfq_order_count(self):
        for po in self:
            po_ids = self.env['quotation.order'].search([('requisition_rfq_id', '=', po.id)])
            po.quotation_order_count = len(po_ids)

    def purchase_order_button(self):
        self.ensure_one()
        return {
            'name': 'Quotation Order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'quotation.order',
            'domain': [('requisition_rfq_id', '=', self.id)],
        }

    # This method would use to validate that if you are not in central branch in case of centralize operation type you would be unable to create an RFQ!#
    # @api.onchange('company_id')
    # def centralization_validation(self):
    #     for rec in self:
    #         if rec.company_id:
    #             if rec.company_id.centralized_branch_id.id != self.env.branch.id:
    #                 raise UserError('You are not Allowed to created an rfq from this branch if system is in centralized state you have to log in through central branch to create rfq!')


class RequisitionOrderLine(models.Model):
    _name = 'requisition.order.line'
    _description = 'Requisition Order Line'
    _order = 'order_id, sequence, id'

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_qty=0, product_uom=False, schedule_date=False,
                              state=False, currency_id=False)
        lines = super(RequisitionOrderLine, self).create(vals_list)

        for line in lines:
            if line.order_id.state == 'draft' and line.product_id:
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
        return lines

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))
        result = super(RequisitionOrderLine, self).write(values)
        return result

    name = fields.Char(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    product_qty = fields.Float(string='Quantity', default=1)
    product_uom = fields.Many2one('uom.uom', related='product_id.uom_id', string='UoM')
    product_id = fields.Many2one('product.product', string='Product',
                                 domain=['|', ('purchase_ok', '=', True), ('sale_ok', '=', True)],
                                 change_default=True)
    schedule_date = fields.Date('Expected Receipt Date')
    category_id = fields.Many2one('product.category', related='product_id.categ_id', string="Product Category")

    price_unit = fields.Float(string='Expected Price', default=1)

    order_id = fields.Many2one('requisition.order', string='Order Reference', index=True, required=True,
                               ondelete='cascade')
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True,
                                 readonly=True)
    state = fields.Selection(related='order_id.state', store=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    # branch_id = fields.Many2one('res.branch', string='Branch')
    warehouse_id = fields.Many2one('stock.warehouse', string="Ship To")
    requisition_line_id = fields.Many2one('requisition.line', 'Requisition Line')
    product_expense = fields.Boolean(compute='_compute_product_expense')
    requisition_id = fields.Many2one('material.purchase.requisition')

    taxes_id = fields.Many2many('account.tax', string='Taxes')
    amount = fields.Float(string="Amount", compute='_compute_total_amount')
    note_to_vendor = fields.Char(string='Vendor Note')
    vendor_product_name = fields.Char('Vendor Product Name')
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False, help="Technical field for UX purpose.")

    ############ on change product id description #################
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

    ############ on change product id description #################

    # Method to validate that schedule date could not be in past
    @api.constrains('schedule_date')
    def _schedule_date_validation(self):
        if not self.display_type in ('line_section', 'line_note'):
            for line in self:
                if not line.schedule_date:
                    raise UserError(_('Expected receipt Date not selected please select a Date!'))
                if line.schedule_date:
                    if line.schedule_date < fields.Datetime.now().date():
                        raise UserError(_('Expected receipt Date should not in past it must be any future date!'))
                    if line.schedule_date < self.order_id.closure_date.date():
                        raise UserError(_('Closure date should not greater than expected receipt date!'))

    # Method to validate that maximum number of digits in quantity would be 20
    @api.constrains('product_qty')
    def _check_product_qty(self):
        if not self.display_type in ('line_section', 'line_note'):
            for number in self:
                if len(str(number.product_qty)) > 20:
                    raise ValidationError(_('Number of digits in quantity must not exceed 20'))

    # Method to validate that maximum number of digits in unit price would be 20
    @api.constrains('price_unit')
    def _check_price_unit_length(self):
        if not self.display_type in ('line_section', 'line_note'):
            for number in self:
                if len(str(number.price_unit)) > 20:
                    raise ValidationError(_('Number of digits in price must not exceed 20'))

    # This function is to validate that quantity should not less than 0
    @api.constrains('product_qty')
    def _check_qty(self):
        if not self.display_type in ('line_section', 'line_note'):
            for rec in self:
                if rec.product_qty <= 0:
                    raise UserError(
                        _("Quantity of %s can't be 0 or negative. It should be a positive integer") % rec.product_id.name)

    # This function is to validate that price should not less than 0
    @api.constrains('price_unit')
    def _check_price_unit(self):
        if not self.display_type in ('line_section', 'line_note'):
            for rec in self:
                if rec.price_unit <= 0:
                    raise UserError(
                        _("Expected Price of %s can't be negative or zero. It should be a positive integer") % rec.product_id.name)

    # This function is to to calculate the total amount of quantity for line level
    @api.depends('product_qty', 'price_unit')
    def _compute_total_amount(self):
        for record in self:
            record.amount = record.product_qty * record.price_unit

    @api.onchange('product_id')
    def _category_doamin(self):
        return {'domain': {
            'category_id': [('id', '=', self.product_id.categ_id.id)],
        }
        }

    @api.depends('category_id')
    def _compute_product_expense(self):
        for record in self:
            record.product_expense = record.category_id.is_expense

    def unlink(self):
        for line in self:
            if line.order_id.state in ['requisition', 'done']:
                raise UserError(_('Cannot delete a requisition order line which is in state \'%s\'.') % (line.state,))
        return super(RequisitionOrderLine, self).unlink()
