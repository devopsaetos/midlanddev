# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
from dateutil.relativedelta import relativedelta


class MaintenanceChargesPayment(models.Model):
    _name = 'maintenance.charges.payment'
    # 'tools.mixin' removed - it was provided by 'axiom_payment_report', which is
    # not available in this addons tree (dependency commented out in __manifest__.py).
    # 'mail.thread'/'mail.activity.mixin' added explicitly (matching the convention used
    # everywhere else in this project, e.g. change_unit_type.py) so tracking=True fields
    # and the <chatter/> widget in the form view keep working.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Maintenance Charges Payment'

    name = fields.Char(required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'), tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')
    ], default="draft", tracking=True)
    file_id = fields.Many2one('file')
    unit_class_id = fields.Many2one('unit.class', default=lambda self: self._default_unit_class())
    inventory_id = fields.Many2one('plot.inventory')
    sector_id = fields.Many2one('sector', related='inventory_id.sector_id', store=True)
    membership_id = fields.Many2one('res.partner', related='file_id.membership_id')  # domain=[('is_member','=',True)] removed: is_member is not a field on res.partner anywhere in this project
    category_id = fields.Many2one('plot.category', string='Category', related='inventory_id.category_id')
    size_id = fields.Many2one('unit.size', 'Size', related='inventory_id.size_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='inventory_id.unit_category_type_id')
    date = fields.Date(tracking=True, default=fields.Date.today())
    product_id = fields.Many2one('product.product', string='Charge Type')

    # Hard coded cash journal for society charges
    journal_id = fields.Many2one('account.journal', 'Payment Journal', default=6,
                                 domain=[('type', 'in', ('cash', 'bank')), ('show_in_maintenance', '=', True)],
                                 tracking=True)
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default="cash", tracking=True)
    remarks = fields.Char()
    payment_ref = fields.Char()
    from_app = fields.Boolean()
    maintenance_recovery_agent_id = fields.Many2one('res.users', domain="[('maintenance_recovery_agent', '=', True)]")

    invoice_ids = fields.Many2many('account.move')
    is_advance_payment = fields.Boolean(default=False)
    payment_id = fields.Many2one('account.payment')
    maintenance_advance_payment_ids = fields.One2many('maintenance.advance.payment.lines',
                                                      'maintenance_charges_payment_id')

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            if self.env.user.maintenance_recovery_agent == True:
                rec.maintenance_recovery_agent_id = self.env.user.id

    def _default_unit_class(self):
        house = self.env['unit.class'].search([('name', '=', 'House')], limit=1)
        return house.id if house else False

    @api.onchange('sector_id')
    def _product_domain(self):
        return {
            'domain': {
                'product_id': [
                    ('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))],
            }
        }

    @api.onchange('unit_class_id')
    def _domain_inventory(self):
        for rec in self:
            if rec.unit_class_id:
                return {
                    'domain': {
                        'inventory_id': [('unit_class_id', '=', rec.unit_class_id.id)]
                    }
                }

    @api.onchange('inventory_id', 'product_id', 'membership_id')
    def _invoices_domain(self):
        for rec in self:
            if rec.inventory_id:
                file = self.env['file'].search([('inventory_id', '=', rec.inventory_id.id)], limit=1)
                rec.file_id = file.id
            set_date = '2023-11-01'
            if rec.membership_id and rec.inventory_id and rec.product_id:
                if rec.product_id.name == 'Maintenance Charges':
                    return {
                        'domain': {
                            'invoice_ids': [('partner_id', '=', rec.membership_id.id),
                                            ('property_invoice_type', '=', 'maintenance_charges'),
                                            ('date', '>=', set_date),
                                            ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                            ('amount_residual_signed', '>', 0.0), ('is_maintenance_batch', '=', False)],
                        }
                    }
                elif rec.membership_id and rec.product_id.name == 'Service Charges':
                    return {
                        'domain': {
                            'invoice_ids': [('partner_id', '=', rec.membership_id.id),
                                            ('property_invoice_type', '=', 'society_charges'), ('date', '>=', set_date),
                                            ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                            ('amount_residual_signed', '>', 0.0), ('is_maintenance_batch', '=', False)],
                        }
                    }

            elif rec.membership_id and rec.inventory_id:
                return {
                    'domain': {
                        'invoice_ids': [('partner_id', '=', rec.membership_id.id), ('date', '>=', set_date),
                                        ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                        ('amount_residual', '>', 0.0)],
                    }
                }

    @api.onchange('invoice_ids')
    def _validation_invoices(self):
        for rec in self:
            if rec.invoice_ids:
                for inv in rec.invoice_ids:
                    inv.write({'is_maintenance_batch': True})

    def receive_payment(self):
        for rec in self:
            if not rec.is_advance_payment:
                if not rec.invoice_ids:
                    raise ValidationError(_('Please select invoices.'))

                invoices = []
                total_amount = 0
                for invoice in rec.invoice_ids:
                    total_amount = total_amount + invoice.amount_residual
                    invoices.append((0, 0, {'invoice_id': invoice.id,
                                            'payment_id': False,
                                            'payment_due': invoice.amount_residual,
                                            'payment_amount': invoice.amount_residual
                                            }))

                payment = self.env['account.payment'].create({
                    'payment_date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'payment_category': 'multi_inv_payment',
                    'partner_id': rec.membership_id.id,
                    'file_id': rec.file_id.id,
                    'amount': total_amount,
                    'journal_id': rec.journal_id.id,
                    'company_id': rec.env.company.id,
                    # 'branch_id': rec.env.branch.id,  # res.branch not available in this project
                    'currency_id': rec.env.company.currency_id.id,
                    'payment_difference_handling': 'reconcile',
                    'communication': rec.remarks,
                    'multi_invoice_ids': invoices,
                })
                payment.post()
                rec.payment_ref = payment.name
                rec.payment_id = payment.id
                rec.state = 'paid'

            if rec.is_advance_payment and rec.product_id.name in ('Maintenance Charges', 'Service Charges'):
                multi_invoices = []
                invoices_list = []
                monthly_invoice_created = False
                for line in rec.maintenance_advance_payment_ids:
                    total_invoices = ((
                                              line.to_date.year - line.from_date.year) * 12 + line.to_date.month - line.from_date.month) + 1
                    start_date = line.from_date

                    for inv in range(total_invoices):
                        if rec.file_id.maintenance_history_ids:
                            installment_number = rec.file_id.maintenance_history_ids[-1].installment_number + 1

                            file_maintenance_line = rec.file_id.maintenance_history_ids.filtered(
                                lambda l: l.date.month == start_date.month and l.date.year == start_date.year)

                            if file_maintenance_line.payment_status != 'paid' and file_maintenance_line.residual > 0.0:
                                monthly_invoice_created = True
                                if monthly_invoice_created:
                                    invoices_list.append((0, 0, {
                                        'id': file_maintenance_line.invoice_id.id,
                                    }))
                                    multi_invoices.append((0, 0, {
                                        'invoice_id': file_maintenance_line.invoice_id.id,
                                        'payment_id': False,
                                        'payment_due': file_maintenance_line.invoice_id.amount_residual,
                                        'discount_amount': line.discount_amount / total_invoices if line.discount_amount and line.discount_type == 'fixed_amount' else (
                                            file_maintenance_line.residual / 100 * line.discount_amount if line.discount_amount and line.discount_type == 'percentage' else 0.0),
                                        'writeoff_account_id': self.env.company.discount_allowed_account_id.id if line.discount_amount else False,
                                    }))
                                    start_date = start_date + relativedelta(months=1)

                            else:
                                monthly_invoice_created = False
                        else:
                            installment_number = 1

                        if not monthly_invoice_created:
                            invoice_line = [(0, 0, {
                                'product_id': rec.product_id.id,
                                'name': rec.product_id.name,
                                'account_id': rec.product_id.property_account_income_id.id,
                                'price_unit': line.amount / total_invoices
                            })]
                            invoice = self.env['account.move'].create({
                                'partner_id': rec.membership_id.id,
                                # 'branch_id': rec.env.branch.id,  # res.branch not available in this project
                                'move_type': 'out_invoice',
                                'invoice_date': start_date,
                                'journal_id': rec.env.company.account_journal_id.id,
                                'invoice_line_ids': invoice_line,
                                'property_invoice_type': 'maintenance_charges' if rec.product_id.name == 'Maintenance Charges' else 'society_charges',
                            })
                            invoices_list.append((0, 0, {
                                'id': invoice.id,
                            }))
                            invoice.file_ids = rec.file_id.id
                            invoice.action_post()
                            multi_invoices.append((0, 0, {
                                'invoice_id': invoice.id,
                                'payment_id': False,
                                'payment_due': invoice.amount_residual,
                                'discount_amount': line.discount_amount / total_invoices if line.discount_amount and line.discount_type == 'fixed_amount' else (
                                    invoice.amount_residual / 100 * line.discount_amount if line.discount_amount and line.discount_type == 'percentage' else 0.0),
                                'writeoff_account_id': self.env.company.discount_allowed_account_id.id if line.discount_amount else False,
                            }))

                            rec.file_id.maintenance_history_ids.create({
                                'date': start_date,
                                'installment_number': installment_number,
                                'amount': invoice.amount_total,
                                'invoice_created': True,
                                'invoice_id': invoice.id,
                                'amount_paid': invoice.amount_total - invoice.amount_residual,
                                'residual': invoice.amount_residual,
                                'payment_status': invoice.payment_state,
                                'file_id': rec.file_id.id
                            })
                            start_date = start_date + relativedelta(months=1)

                payment = self.env['account.payment'].create({
                    'payment_date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'payment_category': 'multi_inv_payment',
                    'partner_id': rec.membership_id.id,
                    'file_id': rec.file_id.id,
                    'amount': line.net_amount,
                    'journal_id': rec.journal_id.id,
                    'company_id': rec.env.company.id,
                    # 'branch_id': rec.env.branch.id,  # res.branch not available in this project
                    'currency_id': rec.env.company.currency_id.id,
                    'payment_difference_handling': 'reconcile',
                    'communication': rec.remarks,
                    'multi_invoice_ids': multi_invoices,
                })
                payment.post()
                rec.write({'payment_ref': payment.name,
                           'payment_id': payment.id,
                           'state': 'paid',
                           'invoice_ids': invoices_list})

    @api.model
    def receive_payment_from_app(self, **kwargs):
        invoices = []
        app_invoices = []
        file_ids = []
        for rec in kwargs['invoice_ids']:
            app_invoices.append(rec['invoice_id'])
            file_ids.append(rec['file_id'])
        maintenance_invoices = self.env['account.move'].sudo().browse(app_invoices)
        files = self.env['file'].sudo().browse(file_ids)
        if not maintenance_invoices:
            raise ValidationError(_('No Invoices found against this plot/file.'))

        # file = self.env['file'].browse(kwargs['file_id'])
        total_amount = 0
        amount_residual = -1
        for rec in kwargs['invoice_ids']:
            inv = self.env['account.move'].sudo().browse(rec['invoice_id'])
            file = self.env['file'].sudo().browse(rec['file_id'])
            if inv.file_ids == file:
                maintenance_payment = self.create({
                    'from_app': True,
                    'file_id': file.id,
                    'inventory_id': file.inventory_id.id,
                    'membership_id': file.membership_id.id,
                    'category_id': file.category_id.id,
                    'unit_category_type_id': file.unit_category_type_id.id,
                    'unit_class_id': file.unit_class_id.id,
                    'size_id': file.size_id.id,
                    'date': fields.Date.today(),
                    'journal_id': 6,
                    'mode_of_payments': 'cash',
                    'remarks': "Payment Created From Maintenance App",
                    'maintenance_recovery_agent_id': rec.get("uid", False),
                    'invoice_ids': inv.ids
                })
                # for invoice in maintenance_payment.invoice_ids:
                #     for rec in kwargs['invoice_ids']:
                #         if invoice.id == rec['invoice_id']:
                #             amount = rec['payment_amount']
                #             invoices.append((0, 0, {'invoice_id': invoice.id,
                #                                      'payment_id': False,
                #                                      'payment_due': invoice.amount_residual,
                #                                      'payment_amount': amount
                #                                 }))

                payment = self.env['account.payment'].sudo().create({
                    'payment_date': fields.Date.today(),
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'payment_category': 'multi_inv_payment',
                    'partner_id': maintenance_payment.membership_id.id,
                    'file_id': file.id,
                    'amount': rec['payment_amount'],
                    'journal_id': maintenance_payment.journal_id.id,
                    'company_id': self.env.company.id,
                    # 'branch_id': self.env.branch.id,  # res.branch not available in this project
                    'currency_id': self.env.company.currency_id.id,
                    'payment_difference_handling': 'reconcile',
                    'communication': maintenance_payment.remarks,
                    'multi_invoice_ids': [(0, 0, {'invoice_id': inv.id,
                                                  'payment_id': False,
                                                  'payment_due': inv.amount_residual,
                                                  'payment_amount': rec['payment_amount']
                                                  })],
                })
                payment.post()
                maintenance_payment.payment_ref = payment.name
                amount_residual = sum(maintenance_payment.invoice_ids.mapped('amount_residual_signed'))
                if amount_residual == 0:
                    maintenance_payment.state = 'paid'
                elif amount_residual > 0:
                    maintenance_payment.state = 'in_payment'

        if amount_residual < 0:
            return json.dumps({'error': "Amount Not Paid", 'status': 400})
        else:
            return json.dumps({'Success': "Amount Successfully Paid", 'status': 200})

    # This returns four most recents maintenance payments
    @api.model
    def get_recent_records(self, **kwargs):
        recent_payments = self.env['maintenance.charges.payment'].search([('state', '!=', 'draft')], limit=4,
                                                                         order="create_date desc")
        data = []
        for rec in recent_payments:
            payment = self.env['account.payment'].search([('name', '=', rec.payment_ref)], limit=1)
            maintenance_payment = {
                'name': rec.name,
                'date': str(payment.payment_date),
                'amount': payment.amount,
                'payment_ref': payment.name
            }
            data.append(maintenance_payment)

        if data:
            return json.dumps(data)
        else:
            return json.dumps({'error': "No record found", 'status': 400})

    @api.model
    def get_today_maintenance_payments(self, **kwargs):
        user = kwargs["uid"]
        payment_received_today = self.env['maintenance.charges.payment'].search([('state', '!=', 'draft'),
                                                                                 ('date', '=', fields.Date.today()),
                                                                                 ('maintenance_recovery_agent_id', '=',
                                                                                  user)])
        amount = 0
        for rec in payment_received_today:
            payment = self.env['account.payment'].search(
                [('name', '=', rec.payment_ref), ('payment_date', '=', fields.Date.today())], limit=1)
            amount = amount + payment.amount

        return json.dumps(amount)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code("maintenance.charges.payment") or _('New')

        record = super(MaintenanceChargesPayment, self).create(vals)

        return record

    def unlink(self):
        for rec in self:
            if rec.state == 'draft' and not self.env.user.has_group(
                    'base.group_erp_manager'):
                raise ValidationError(_('You are not allowed delete record!'))
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record when payment is received!'))

        return super(MaintenanceChargesPayment, self).unlink()

    def print_receipt(self):
        # Original implementation printed the payment receipt via a report action defined in
        # 'axiom_payment_report', which is not available in this addons tree (dependency
        # commented out in __manifest__.py). Preserved below so it can be restored if that
        # module is ever added back to this project.
        # for rec in self:
        #     print(f"Payment ID: {rec.payment_id}")
        #     payment = self.env['account.payment'].search([('id', '=', rec.payment_id.id)])
        #     report = self.env.ref('axiom_payment_report.action_payment_receipt_report_customer').report_action(payment)
        #     return report
        raise ValidationError(_(
            "Printing the payment receipt is not available: the 'axiom_payment_report' "
            "module that provides this report is not installed in this project."))

    def payment_receipt(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment',
            'view_mode': 'list,form',
            'target': 'current',
            'res_model': 'account.payment',
            'domain': [('id', 'in', self.payment_id.ids)]
        }


class MaintenanceAdvancePaymentLines(models.Model):
    _name = 'maintenance.advance.payment.lines'
    _description = 'Maintenance Advance Payment Lines'

    maintenance_charges_payment_id = fields.Many2one('maintenance.charges.payment')
    from_date = fields.Date()
    to_date = fields.Date()
    amount = fields.Float()
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount')])
    discount_amount = fields.Float()
    net_amount = fields.Float(compute='_compute_net_amount')

    @api.depends('discount_type', 'discount_amount', 'amount')
    def _compute_net_amount(self):
        for rec in self:
            if rec.amount and rec.discount_type == 'percentage' and rec.discount_amount:
                rec.net_amount = rec.amount / 100 * (100 - rec.discount_amount)
            elif rec.amount and rec.discount_type == 'fixed_amount' and rec.discount_amount:
                rec.net_amount = rec.amount - rec.discount_amount
            else:
                rec.net_amount = rec.amount

    def unlink(self):
        for rec in self:
            if rec.maintenance_charges_payment_id.state == 'draft' and not self.env.user.has_group(
                    'base.group_erp_manager'):
                raise ValidationError(_('You are not allowed delete record!'))
            if rec.maintenance_charges_payment_id.state != 'draft':
                raise ValidationError(_('You cannot delete record when payment is received!'))

        return super(MaintenanceAdvancePaymentLines, self).unlink()
