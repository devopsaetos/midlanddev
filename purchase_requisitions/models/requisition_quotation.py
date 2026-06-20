# -*- coding: utf-8 -*-


from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools.misc import formatLang, get_lang


class QuotationOrder(models.Model):
    _name = "quotation.order"
    _description = "Requisition Quotation Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.depends('order_line.price_total')
    def _amount_all(self):
        # self.ensure_one()
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    # @api.onchange('creation_date')
    # def default_date_validity(self):
    #     if self.creation_date:
    #         self.date_validity = self.creation_date

    name = fields.Char('Order Reference', index=True, default='New')
    origin = fields.Char(string="RFQ Number", copy=False, \
                         help="Reference of the document that generated this quotation order "
                              "request (e.g. a sales order)")
    partner_ref = fields.Char('Vendor Reference', copy=False, \
                              help="Reference of the sales order or bid sent by the vendor. "
                                   "It's used to do the matching when you receive the "
                                   "products as this reference is usually written on the "
                                   "delivery order sent by your vendor.")
    response_date = fields.Date('Response Date')
    date_order = fields.Datetime('Quotation Closure Date', states=READONLY_STATES, index=True, copy=False,
                                 default=fields.Datetime.now, \
                                 help="Depicts the date where the Quotation should be validated and converted into a quotation order.")
    date_approve = fields.Date('Approval Date', readonly=1, index=True, copy=False)

    creation_date = fields.Datetime('Creation Date', default=fields.Datetime.now)
    date_validity = fields.Date('Quotation Validity')
    partner_id = fields.Many2one('res.partner', string='Vendor', states=READONLY_STATES, change_default=True,
                                 track_visibility='always')
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, states=READONLY_STATES, \
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'RFQ Sent'),
        ('quotation', 'Quotation'),
        ('purchase', 'Purchase'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    order_line = fields.One2many('quotation.order.line', 'order_id', string='Order Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    order_line_details = fields.One2many('quotation.order.line', 'order_id', string='Order Lines', related='order_line',
                                         readonly=True)
    notes = fields.Text('Terms and Conditions')
    date_submission = fields.Datetime(string='Date Response')

    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all',
                                   track_visibility='always')

    product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')
    create_uid = fields.Many2one('res.users', 'Responsible')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES,
                                 default=lambda self: self.env.user.company_id.id)
    # branch_id = fields.Many2one('res.branch', string="Branch")
    # operation_type = fields.Selection(related='company_id.operation_type', store=True)
    rfq_type = fields.Selection([
        ('standard', 'Standard'),
        ('bid', 'Bid RFQ')
    ], string='Quotation Type')
    closure_date = fields.Datetime(string='RFQ Closure Date', copy=False,
                                   help="Closure date that is specified on RFQ form")
    requisition_responsible_id = fields.Many2one('res.users', string="Requester", readonly=True,
                                                 default=lambda self: self.env.user and self.env.user.id or False)
    purchase_order_count = fields.Integer('Purchase Order', compute='_get_rfq_order_count')
    requisition_rfq_id = fields.Many2one('requisition.order', 'Requisition Order')
    order_line_price = fields.Many2many('quotation.order.line', string="Product Price",
                                        compute="compute_product_prices_line")
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                     tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    evaluation_criteria_ids = fields.One2many('evaluation.connector', 'quotation_order_id', ondelete="cascade")

    @api.onchange('response_date')
    def response_date_validation(self):
        if self.response_date:
            if self.response_date < fields.Date().today():
                raise UserError(_("Please select a response date that doesn't fall in the past!"))
        if self.response_date and self.date_validity:
            if self.response_date > self.date_validity:
                raise UserError(_("Please select the response date that doesn't greater than validity date!"))

    @api.onchange('date_validity')
    def validity_date_validation(self):
        if self.date_validity:
            if self.date_validity < fields.Date().today():
                raise UserError(_("Please select a validity date than doesn't fall in the past!"))
        if self.response_date and self.date_validity:
            if self.date_validity < self.response_date:
                raise UserError(_('Please select the validity date greater than response date!'))

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('partner_ref', operator, name)]
        pos = self.search(domain + args, limit=limit)
        return pos.name_get()

    def compute_product_prices_line(self):
        for rec in self:
            if len(rec.order_line.ids) > 0:
                rec.order_line_price = [(6, 0, rec.order_line.ids)]

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
                vals['name'] = self.env['ir.sequence'].next_by_code('quotation.order') or '/'
        return super(QuotationOrder, self).create(vals_list)

    def unlink(self):
        for order in self:
            if not order.state == 'cancel':
                raise UserError(_('In order to delete a quotation order, you must cancel it first.'))
        return super(QuotationOrder, self).unlink()

    @api.constrains('response_date')
    def response_date_validation(self):
        for rec in self:
            if rec.response_date < fields.Date.today():
                raise UserError(_("Sorry, Response Date %s can't in the past") % str(rec.response_date))

    @api.onchange('partner_id', 'company_id')
    def onchange_partner_id(self):
        if not self.partner_id:
            self.currency_id = False
        else:
            self.currency_id = self.env.user.company_id.currency_id.id
        return {}



    def button_draft(self):
        self.write({'state': 'draft'})
        # return {}

    def button_unlock(self):
        self.write({'state': 'purchase'})

    def button_done(self):
        self.write({'state': 'done'})

    def button_cancel(self):
        self.write({'state': 'cancel'})

    def button_validate(self):
        self.write({'state': 'quotation'})

    # currently this method is doing nothing that's why we have commented it
    # def button_confirm(self):
    #     for order in self:
    #         if order.state not in ['quotation']:
    #             continue
    #         purchase_order_obj = self.env['purchase.order']
    #         purchase_order_line_obj = self.env['purchase.order.line']
    #         if order.partner_id:
    #             for vendor in order.partner_id:
    #                 vals = {
    #                     'partner_id': vendor and vendor.id or False,
    #                     'date_order': datetime.now(),
    #                     'origin': order.name,
    #                     'state': 'draft',
    #                     'payment_term_id': order.payment_terms.id,
    #                     'requisition_rfq_id': order.id,
    #                     'rfq_type': order.rfq_type or False,
    #                     'closure_date': order.closure_date or False,
    #                     'requisition_responsible_id': order.requisition_responsible_id and order.requisition_responsible_id.id or False,
    #                     'branch_id': order.branch_id and order.branch_id.id or False,
    #                 }
    #                 purchase_order = purchase_order_obj.create(vals)
    #                 purchase_order.write({'state': 'draft'})
    #
    #                 for line in order.order_line:
    #                     po_line_vals = {
    #                         'category_id': line.category_id and line.category_id.id or False,
    #                         'product_id': line.product_id and line.product_id.id or False,
    #                         'product_qty': line.product_qty or 0.0,
    #                         'name': line.product_id.description_purchase or 'cement',
    #                         'date_planned': datetime.now(),
    #                         'price_unit': line.price_unit,
    #                         'product_uom': line.product_uom and line.product_uom.id or 1,
    #                         'order_id': purchase_order and purchase_order.id or False,
    #                         'state': 'draft',
    #                     }
    #                     purchase_order_line = purchase_order_line_obj.create(po_line_vals)
    #                     line.requisition_line_id.write({'state': 'po_created'})
    #                     line.write({'po_created': True})
    #             self.write({'state': 'purchase', 'date_approve': fields.Date.context_today(self)})
    #             self.filtered(
    #                 lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
    #             all_quotation_ids = self.env['quotation.order'].search(
    #                 [('requisition_rfq_id', '=', self.requisition_rfq_id.id)])
    #             if len(all_quotation_ids) > 0:
    #                 for quotation in all_quotation_ids:
    #                     if quotation.id != self.id:
    #                         quotation.button_cancel()
    #         else:
    #             raise UserError(_('Please select at least one vendor to create Quotation'))
    #     return {}
    # currently this method is doing nothing that's why we have commented it
    def _get_rfq_order_count(self):
        for po in self:
            po_ids = self.env['purchase.order'].search([('requisition_rfq_id', '=', po.id)])
            po.purchase_order_count = len(po_ids)

    def purchase_order_button(self):
        self.ensure_one()
        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('requisition_rfq_id', '=', self.id)],
        }

    def action_rfq_send(self):
        '''
        This function opens a window to compose an email, with the edi purchase template message loaded by default
        '''
        self.ensure_one()
        try:
            template_id = self.env.ref('purchasing.email_template_edi_quotation').id
        except ValueError:
            template_id = False
        try:
            compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        except ValueError:
            compose_form_id = False
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_model': 'quotation.order',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "purchasing.mail_template_data_notification_email_quotation_order",
            'quotation_mark_rfq_sent': True,
            'force_email': True
        })
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def print_quotation(self):
        pass
        self.write({'state': "sent"})
        return self.env.ref('purchasing.report_quotation_order').report_action(self)


class QuotationOrderLine(models.Model):
    _name = 'quotation.order.line'
    _description = 'Requisition Order Line'
    _order = 'order_id, sequence, id'

    def name_get(self):
        if not self._context.get('show_line_price', True):  # TDE FIXME: not used
            return super(QuotationOrderLine, self).name_get()
        return [(value.id, "%s: %s" % (value.product_id.name, value.price_unit)) for value in self]

    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)],
                                 change_default=True)
    name = fields.Char(string='Description')
    sequence = fields.Integer(string='Sequence', default=1)

    product_qty = fields.Float(string='Quantity')
    rfq_qty = fields.Float(string='RFQ Qty')
    product_uom = fields.Many2one(related='product_id.uom_id', string='UoM')
    category_id = fields.Many2one('product.category', string="Item Category")
    price_unit = fields.Float(string='Unit Price')
    expected_price = fields.Float(string='Expected Price')
    order_id = fields.Many2one('quotation.order', string='Order Reference', index=True, required=True,
                               ondelete='cascade')
    requisition_rfq_id = fields.Many2one('requisition.order', related='order_id.requisition_rfq_id', store=True)
    origin = fields.Char(related="order_id.origin", store=True, string="RFQ Number")
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='Company', store=True,
                                 readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'RFQ Sent'),
        ('quotation', 'Quotation'),
        ('purchase', 'Purchase'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], related='order_id.state', readonly=True, copy=False, store=True, default='draft')
    po_created = fields.Boolean(default=False)

    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    date_order = fields.Datetime(related='order_id.date_order', string='Order Date', readonly=True)
    # branch_id = fields.Many2one('res.branch', string='Branch')
    warehouse_id = fields.Many2one('stock.warehouse', string='Ship To')
    requisition_line_id = fields.Many2one('requisition.line', 'Requisition Line')
    price_after_discount = fields.Monetary(string='Price After Discount', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', related="order_id.partner_id", store=True)
    rfq_type = fields.Selection([
        ('standard', 'Standard'),
        ('bid', 'Bid RFQ')
    ], related="order_id.rfq_type", store=True)
    closure_date = fields.Datetime(related='order_id.closure_date', store=True, string="RFQ Closure Date")

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    product_expense = fields.Boolean(compute='_compute_product_expense')
    schedule_date = fields.Date('Schedule Date')
    taxes_id = fields.Many2many('account.tax', string='Taxes',
                                domain=['|', ('active', '=', False), ('active', '=', True)])
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False, help="Technical field for UX purpose.")

    # @api.depends('requisition_rfq_id')
    # def _compute_expected_price(self):
    #     if self.requisition_rfq_id:
    #         for line in self.requisition_rfq_id.order_line_ids:
    #             if line.product_id == self.product_id:
    #                 self.expected_price = line.price_unit

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_qty=0, product_uom=False)
        lines = super(QuotationOrderLine, self).create(vals_list)
        for line in lines:
            if line.order_id.state == 'draft' and line.product_id:
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
        return lines

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                _("You cannot change the type of a purchase order line. Instead you should delete the current line and create a new line of the proper type."))
        result = super(QuotationOrderLine, self).write(values)
        return result

    @api.onchange('schedule_date')
    def onchange_schedule_date(self):
        for line in self:
            if line.schedule_date:
                if line.schedule_date < fields.Date().today():
                    raise UserError(
                        _("Promised Date (%s) can't be in past it must be future date!") % line.schedule_date)
            if line.schedule_date and self.order_id.response_date:
                if line.schedule_date < self.order_id.response_date:
                    raise UserError(_("Promised Date(%s) can't be less than Response Date") % line.schedule_date)
            if line.schedule_date and self.order_id.date_validity:
                if line.schedule_date < self.order_id.date_validity:
                    raise UserError(
                        _("Promised Date(%s) can't be less than Quotation Validity Date") % line.schedule_date)

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
            lang=get_lang(self.env, self.requisition_line_id.requisition_id.requisition_responsible_id.lang).code
        )
        self.name = self._get_product_purchase_description(product_lang)

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name

    ############ on change product id description #################

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.taxes_id.compute_all(
                vals['price_unit'],
                vals['currency_id'],
                vals['product_qty'],
                vals['product'],
                vals['partner'])
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.onchange('product_id')
    def _category_doamin(self):
        return {'domain': {
            'category_id': [('id', '=', self.product_id.categ_id.id)],
        }
        }

    def _prepare_compute_all_values(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        return {
            'price_unit': self.price_unit,
            'currency_id': self.currency_id,
            'product_qty': self.product_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }

    @api.depends('category_id')
    def _compute_product_expense(self):
        for record in self:
            record.product_expense = record.category_id.is_expense

    def unlink(self):
        for line in self:
            if line.order_id.state in ['purchase', 'done']:
                raise UserError(_('Cannot delete a purchase order line which is in state \'%s\'.') % (line.state,))
        return super(QuotationOrderLine, self).unlink()

    def action_create_po_vendor_wise(self):
        '''Create PO from Quotations'''
        # if self.env.company.operation_type == 'centralized' and self.env.branch.id != self.env.company.centralized_branch_id.id:
        #     raise UserError(
        #         'You are not Allowed to create po from this branch if system is in centralized state you have to log in through central branch to create PO!')

        purchase_order_obj = self.env['purchase.order']
        purchase_order_line_obj = self.env['purchase.order.line']
        quotation_line_ids = self.env.context.get('active_ids')
        quotation_lines = self.env['quotation.order.line'].browse(quotation_line_ids)
        vendors = quotation_lines.mapped('partner_id')
        purchase_order_ids = []
        for vendor_id in vendors:
            lines = quotation_lines.filtered(lambda line: line.partner_id.id == vendor_id.id)
            check_lines = lines.filtered(lambda line: line.po_created == True).mapped('product_id.name')
            products = ','.join(check_lines)
            if check_lines:
                raise UserError(
                    _("The Product/s %s is/are already selected for Purchase Order, Please remove it..!") % (products,))
            line_order_names = lines.mapped('order_id.name')
            # origin_line_name = '/'.join(line_order_names)
            order_line = []
            for line in lines:
                order_line.append((0, 0,
                                   {
                                       'category_id': line.category_id and line.category_id.id or False,
                                       'product_id': line.product_id and line.product_id.id or False,
                                       'branch_id': line.branch_id.id or False,
                                       'warehouse_id': line.warehouse_id.id or False,
                                       'product_qty': line.product_qty or 0.0,
                                       'name': line.name or False,
                                       'date_planned': datetime.now() or False,
                                       'price_unit': line.price_unit or False,
                                       'product_uom': line.product_uom.id or False,
                                       # 'order_id': purchase_order.id or False,
                                       'price_subtotal': line.price_subtotal or 0.0,
                                       'price_total': line.price_total or 0.0,
                                       'price_tax': line.price_tax or False,
                                       'taxes_id': [(6, 0, line.taxes_id.ids)] or False,
                                       'state': 'draft',
                                       'picking_type_id': line.warehouse_id.in_type_id.id,
                                   }))
            vals = {
                'partner_id': vendor_id and vendor_id.id or False,
                'date_order': datetime.now(),
                'origin': lines.mapped('order_id.name'),
                'state': 'draft',
                'payment_term_id': lines.order_id.payment_term_id.id,
                'requisition_rfq_id': lines[0].order_id.id,
                'rfq_type': lines[0].order_id.rfq_type or False,
                'requisition_responsible_id': lines[0].order_id.requisition_responsible_id and lines[
                    0].order_id.requisition_responsible_id.id or False,
                'branch_id': lines[0].order_id.branch_id and lines[0].order_id.branch_id.id or False,
                'company_id': lines[0].order_id.company_id and lines[0].order_id.company_id.id or False,
                'notes': lines[0].order_id.notes or False,
                'order_line': order_line,
            }
            purchase_order = purchase_order_obj.create(vals)
            for line in lines:
                if not line.po_created:
                    purchase_order_line_obj.write(order_line)
                    purchase_order_line_obj.write({
                        'order_id': purchase_order.id or False,
                    })
                    line.requisition_line_id.write({
                        'state': 'po_created',
                        'po_date': fields.Date.today(),
                        'po_quantity': line.product_qty or 0.0,
                        'po_id': purchase_order.id or False,
                    })
                    line.write({'po_created': True})
                    other_quotation_lines = self.env['quotation.order.line'].search([
                        ('product_id', '=', line.product_id.id), ('origin', '=', line.origin)])

                    if other_quotation_lines:
                        for line in other_quotation_lines:
                            line.write({'po_created': True})
                            line.order_id.write({'state': 'purchase'})
                else:
                    raise UserError(_('Purchase order is already create for the product %s') % (line.product_id.name,))
            purchase_order_ids.append(purchase_order.id)
        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('id', 'in', purchase_order_ids)],
        }

    @api.constrains('price_unit', 'product_qty')
    def _check_qty_price_unit(self):
        for rec in self:
            if rec.price_unit < 0 or rec.product_qty < 0:
                raise UserError(_("Product quantity and unit price can't be in negative"))


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def mail_quotation_order_on_send(self):
        if self._context.get('quotation_mark_rfq_sent'):
            order = self.env['quotation.order'].browse(self._context['default_res_id'])
            if order.state == 'draft':
                order.state = 'sent'

    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'quotation.order' and self._context.get('default_res_id'):
            order = self.env['quotation.order'].browse(self._context['default_res_id'])
            self = self.with_context(mail_post_autofollow=True, lang=order.partner_id.lang)
            self.mail_quotation_order_on_send()
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)
