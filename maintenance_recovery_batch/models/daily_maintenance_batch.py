from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class DailyMaintenanceBatch(models.Model):
    _name = 'daily.maintenance.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Daily Expense Batch'
    _order = 'date desc'

    name = fields.Char('Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'), tracking=True)
    date = fields.Date('Date', default=lambda self: fields.Date.today(), tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company",
                                 tracking=True)
    user_id = fields.Many2one("res.users", required=True, string="User",
                              domain="[('maintenance_recovery_agent', '=', True)]", tracking=True)
    # res.branch model does not exist anywhere in this project - commented out, not deleted,
    # matching the established pattern in real_estate/file_financials for the same field.
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch, string='Branch',
    #                             tracking=True)
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('submit', 'Submit'),
        ('approved', 'Approved'),
    ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')
    maintenance_line_ids = fields.One2many("daily.maintenance.line", "batch_maintenance_id", string='Maintenances',
                                           tracking=True)
    payment_created = fields.Boolean(string='Approved', default=False)
    journal_id = fields.Many2one('account.journal', string='Journal',
                                 domain=[('type', 'in', ('cash', 'bank')), ('show_in_maintenance', '=', True)])
    total_records = fields.Float(string='Daily Count', compute='_compute_total_records', store=True)
    account_payment_id = fields.Many2many('account.payment', string='Payment', tracking=True)
    payment_approved = fields.Boolean(string='Payment Approved', default=False)
    payment_submit = fields.Boolean(string='Payment Submit', default=False)

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            if self.env.user.maintenance_recovery_agent == True:
                rec.user_id = self.env.user.id

    def unlink(self):
        for rec in self:
            if rec.state == 'draft' and not self.env.user.has_group(
                    'base.group_erp_manager'):
                raise ValidationError(_('You are not allowed delete record!'))
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record that is not in draft state!'))

        return super(DailyMaintenanceBatch, self).unlink()

    @api.depends('maintenance_line_ids')
    def _compute_total_records(self):
        for record in self:
            record.total_records = len(record.maintenance_line_ids)

    def submit_to_manager(self):
        current_date = datetime.today()
        last_day_of_month = datetime(current_date.year, current_date.month, 1) + relativedelta(months=1, days=-1)
        for rec in self:
            account_payment_record = []
            for line in rec.maintenance_line_ids:
                if not line.paid_amount:
                    raise ValidationError("Line has no paid amount, so it cannot be submitted to manager.. ")
                payment_lines = []
                invoice_ids = []
                payment_vals_list = []
                file = self.env['file'].sudo().search(
                    [('inventory_id', '=', line.house_id.id)], limit=1)
                # fiscal_month_id field removed (fiscal.month model does not exist in this project)
                # if line.fiscal_month_id and line.paid_amount > line.due_amount:
                #     raise ValidationError("Cannot Pay Advance if Month is Selected.")
                move_records = self.env['account.move'].search([('id', 'in', line.invoice_ids.ids)],
                                                               order='invoice_date')
                balance = line.paid_amount
                if balance > 0:
                    total_paid_amount = balance
                    if move_records:
                        for invoice in move_records:
                            if balance < 1:
                                break
                            payment_amount = min(invoice.amount_residual, total_paid_amount)
                            total_paid_amount -= payment_amount
                            balance -= payment_amount
                            payment_vals_list.append((0, 0, {
                                'invoice_id': invoice.id,
                                'payment_id': False,
                                'payment_due': invoice.amount_residual,
                                'payment_amount': payment_amount,
                            }))
                            invoice_ids.append(invoice.id)
                            writeoff_account_id = (
                                    self.env.company.discount_allowed_account_id.id
                                    or False
                            )
                            payment_lines.append((0, 0, {
                                'invoice_id': invoice.id,
                                'payment_id': False,
                                'payment_due': invoice.amount_residual,
                                'payment_amount': payment_amount,
                                # 'writeoff_account_id': writeoff_account_id,
                            }))
                    # Create the payment
                    Payment = self.env['account.payment'].sudo()
                    total_payment_amount = line.paid_amount
                    payment = Payment.create({
                        'payment_date': line.payment_date,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'payment_category': 'multi_inv_payment',
                        'partner_id': line.partner_id.id,
                        'file_id': file.id,
                        'amount': total_payment_amount,
                        'journal_id': rec.journal_id.id,
                        'company_id': rec.env.company.id,
                        # 'branch_id': rec.env.branch.id,  # res.branch not available in this project
                        'currency_id': rec.env.company.currency_id.id,
                        'communication': 'Received Maintenance Charges For ' + file.name if file else 'Received Maintenance Charges For ' + line.house_id.name,
                        'multi_invoice_ids': payment_lines,
                    })
                    if payment:
                        line.payment_id = payment.id
                        account_payment_record.append(payment.id)
            rec.account_payment_id = [(6, 0, account_payment_record)]
            rec.state = 'submit'
            rec.payment_approved = True
            rec.payment_submit = True

    def set_to_draft(self):
        for rec in self:
            rec.state = 'draft'

    def approved(self):
        for rec in self:
            if rec.state == 'submit':
                for payment_id in rec.account_payment_id:
                    payment_id.post()
                rec.state = 'approved'
                rec.payment_created = True
            else:
                raise ValidationError('Submit Transaction First Before Approval!')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            prefix = 'MNT/REC/'
            if 'journal_id' in vals and vals['journal_id']:
                journal_code = self.env['account.journal'].sudo().browse(vals['journal_id']).code
                if journal_code == 'MC':
                    prefix = 'MNT/CSH/'
                elif journal_code == 'HBM-M':
                    prefix = 'MNT/HBM/'
            if 'date' in vals and vals['date']:
                date_obj = fields.Date.from_string(vals['date'])
                vals['name'] = prefix + date_obj.strftime('%d/%b/%Y').upper()
            else:
                raise ValidationError('Date must be provided for creating a record.')
        new_record = super(DailyMaintenanceBatch, self).create(vals)
        return new_record

    def account_payment_created(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment',
            'view_mode': 'list,form',
            'target': 'current',
            'res_model': 'account.payment',
            'domain': [('id', 'in', self.account_payment_id.ids)]
        }


class DailyMaintenanceLines(models.Model):
    _name = 'daily.maintenance.line'
    _description = 'Daily Maintenance Lines'

    unit_class_id = fields.Many2one('unit.class', default=lambda self: self._default_unit_class())
    house_id = fields.Many2one('plot.inventory', string='House')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    sector_id = fields.Many2one('sector', string='Sector', related='house_id.sector_id')
    street_id = fields.Many2one('street', string='Street', related='house_id.street_id')
    category_id = fields.Many2one('plot.category', string='Category', related='house_id.category_id')
    batch_maintenance_id = fields.Many2one('daily.maintenance.batch', string="Batch")
    due_amount = fields.Float(string='Due Amount', compute='_compute_amounts', store=True)
    paid_amount = fields.Float(string='Paid Amount')
    balance = fields.Float(string='Balance', compute='_compute_balance', store=True)
    journal_id = fields.Many2one('account.journal', string='Journal')
    sequence = fields.Integer(string="Sr.No",
                              default=lambda self: self.env['ir.sequence'].next_by_code('daily.maintenance.line'))
    discount = fields.Float(string='Discount %')
    payment_id = fields.Many2one('account.payment', string='Payment', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Member', compute='_compute_partner')
    invoice_ids = fields.Many2many('account.move', string='Invoice')
    is_inv_select = fields.Boolean(compute='_compute_inv_select')
    product_id = fields.Many2one('product.product', string='Charge Type')
    # fiscal.month / fiscal.year do not exist anywhere in this project - commented out, not deleted.
    # fiscal_month_id = fields.Many2one(
    #     'fiscal.month',
    #     string="Fiscal Month",
    #     readonly=False,
    # )
    # fiscal_year_id = fields.Many2one(
    #     'fiscal.year',
    #     string="Fiscal Year",
    #     related="fiscal_month_id.fiscal_year_id"
    # )
    payment_date = fields.Date()

    @api.depends('invoice_ids')
    def _compute_inv_select(self):
        for rec in self:
            if rec.invoice_ids:
                rec.is_inv_select = True
            else:
                rec.is_inv_select = False

    @api.constrains('paid_amount', 'due_amount')
    def _constrains_paid_amount(self):
        for rec in self:
            if rec.paid_amount <= 0.0:
                raise ValidationError(_('Please enter Paid Amount as it cannot be 0.0'))
            if rec.due_amount and rec.paid_amount:
                if rec.due_amount < rec.paid_amount:
                    raise ValidationError(_('Paid Amount cannot be greater than total amount due of invoices'))

    def _default_unit_class(self):
        house = self.env['unit.class'].search([('name', '=', 'House')], limit=1)
        return house.id if house else False

    @api.onchange('unit_class_id')
    def _domain_house(self):
        for rec in self:
            if rec.unit_class_id:
                return {
                    'domain': {
                        'house_id': [('unit_class_id', '=', rec.unit_class_id.id)]
                    }
                }

    def unlink(self):
        for rec in self:
            if rec.batch_maintenance_id.state == 'draft' and not self.env.user.has_group(
                    'base.group_erp_manager'):
                raise ValidationError(_('You are not allowed delete record!'))
            if rec.batch_maintenance_id.state != 'draft' and self.env.user.has_group(
                    'base.group_erp_manager'):
                raise ValidationError(_('You cannot delete record that is not in draft state!'))

        return super(DailyMaintenanceLines, self).unlink()

    @api.onchange('house_id', 'product_id', 'partner_id')
    def _invoices_domain(self):
        for rec in self:
            file = self.env['file']
            if rec.house_id:
                file = file.search([('inventory_id', '=', rec.house_id.id)], limit=1)
            set_date = '2023-11-01'
            # This branch (gated on rec.fiscal_month_id) is disabled: fiscal_month_id was removed
            # because its comodel 'fiscal.month' does not exist anywhere in this project. The
            # remaining elif branch below (identical logic minus the fiscal-month filter) now
            # covers this case, matching the original fallback behaviour when no fiscal month
            # was selected.
            # if rec.partner_id and rec.house_id and rec.product_id and rec.fiscal_month_id:
            #     if rec.product_id.name == 'Maintenance Charges':
            #         return {
            #             'domain': {
            #                 'invoice_ids': [('partner_id', '=', rec.partner_id.id),
            #                                 ('property_invoice_type', '=', 'maintenance_charges'),
            #                                 ('date', '>=', set_date),
            #                                 ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
            #                                 ('amount_residual_signed', '>', 0.0),
            #                                 ('fiscal_month_id', '=', rec.fiscal_month_id.id),
            #                                 ('is_maintenance_batch', '=', False)],
            #             }
            #         }
            #     elif rec.partner_id and rec.product_id.name == 'Service Charges':
            #         return {
            #             'domain': {
            #                 'invoice_ids': [('partner_id', '=', rec.partner_id.id),
            #                                 ('property_invoice_type', '=', 'society_charges'), ('date', '>=', set_date),
            #                                 ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
            #                                 ('amount_residual_signed', '>', 0.0),
            #                                 ('fiscal_month_id', '=', rec.fiscal_month_id.id),
            #                                 ('is_maintenance_batch', '=', False)],
            #             }
            #         }
            if rec.partner_id and rec.house_id and rec.product_id:
                if rec.product_id.name == 'Maintenance Charges':
                    return {
                        'domain': {
                            'invoice_ids': [('partner_id', '=', rec.partner_id.id),
                                            ('property_invoice_type', '=', 'maintenance_charges'),
                                            ('date', '>=', set_date),
                                            ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                            ('amount_residual_signed', '>', 0.0), ('is_maintenance_batch', '=', False)],
                        }
                    }
                elif rec.partner_id and rec.product_id.name == 'Service Charges':
                    return {
                        'domain': {
                            'invoice_ids': [('partner_id', '=', rec.partner_id.id),
                                            ('property_invoice_type', '=', 'society_charges'), ('date', '>=', set_date),
                                            ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                            ('amount_residual_signed', '>', 0.0), ('is_maintenance_batch', '=', False)],
                        }
                    }

            elif rec.partner_id and rec.house_id:
                return {
                    'domain': {
                        'invoice_ids': [('partner_id', '=', rec.partner_id.id), ('date', '>=', set_date),
                                        ('file_ids', '=', file.id), ('payment_state', '=', 'not_paid'),
                                        ('amount_residual_signed', '>', 0.0), ('is_maintenance_batch', '=', False)],
                    }
                }

    @api.onchange('sector_id')
    def _product_domain(self):
        return {
            'domain': {
                'product_id': [
                    ('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))],
            }
        }

    @api.onchange('invoice_ids', 'paid_amount', 'due_amount')
    def _validation_invoices(self):
        for rec in self:
            if rec.invoice_ids:
                move_records = self.env['account.move'].search([('id', 'in', rec.invoice_ids.ids)],
                                                               order='invoice_date')
                for move in move_records:
                    move.write({'is_maintenance_batch': True})
                if rec.paid_amount:
                    if rec.due_amount < rec.paid_amount:
                        raise ValidationError(_('Paid Amount cannot be greater than total amount due of invoices'))
                        rec.paid_amount = 0.0
                    remaining_amount = rec.paid_amount
                    move_records = self.env['account.move'].search([('id', 'in', rec.invoice_ids.ids)],
                                                                   order='invoice_date')
                    for move in move_records:
                        if move.amount_residual_signed <= remaining_amount:
                            move.write({'is_maintenance_batch': True})
                            remaining_amount = remaining_amount - move.amount_residual_signed
                        else:
                            move.write({'is_maintenance_batch': False})

    # fiscal.month model does not exist anywhere in this project - whole method disabled, not deleted.
    # @api.onchange('company_id')
    # def _compute_fiscal_data(self):
    #     for rec in self:
    #         current_year = datetime.utcnow().year
    #         previous_year = current_year - 1
    #         # Get the start and end dates of the current year
    #         start_of_year = datetime(previous_year, 1, 1)
    #         end_of_year = datetime(current_year, 12, 31)
    #         fiscal_month = rec.env['fiscal.month'].search([
    #             ('open_close', '=', False),
    #             ('start_date', '>=', start_of_year),
    #             ('end_date', '<=', end_of_year),
    #             ('fiscal_year_id.company_id.id', '=', self.env.company.id)
    #         ])
    #         # fiscal_month.filtered(lambda c: c.fiscal_year_id.company_id == self.env.company)
    #         return {'domain': {'fiscal_month_id': [('id', 'in', fiscal_month.ids)]}}

    @api.depends('invoice_ids', 'paid_amount')
    def _compute_amounts(self):
        for record in self:
            if record.invoice_ids:
                move_records = self.env['account.move'].search([('id', 'in', record.invoice_ids.ids)])
                record.due_amount = sum(move_records.mapped('amount_residual_signed')) if move_records else 0.0
                record.balance = record.due_amount - record.paid_amount

    def print_receipt(self):
        # Original implementation printed the payment receipt via a report action defined in
        # 'axiom_payment_report', which is not available in this addons tree (dependency
        # commented out in maintenance_charges/__manifest__.py during its own Odoo 19
        # conversion). Preserved below so it can be restored if that module is ever added
        # back to this project. Mirrors the fix already applied in
        # maintenance_charges/models/maintenance_charges_payment.py::print_receipt.
        # for rec in self:
        #     print(f"Payment ID: {rec.payment_id}")
        #     # rec.payment_id.sudo().print_payment_receipt_office()
        #     payment = self.env['account.payment'].search([('id', '=', rec.payment_id.id)])
        #     report = self.env.ref('axiom_payment_report.action_payment_receipt_report_customer').report_action(payment)
        #     return report
        raise ValidationError(_(
            "Printing the payment receipt is not available: the 'axiom_payment_report' "
            "module that provides this report is not installed in this project."))

    @api.depends('house_id')
    def _compute_partner(self):
        for rec in self:
            file = self.env['file'].sudo().search([('inventory_id', '=', rec.house_id.id)], limit=1)
            if file:
                rec.partner_id = file.membership_id.id
