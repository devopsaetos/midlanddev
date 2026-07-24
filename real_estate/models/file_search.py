# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FileSearch(models.TransientModel):
    _name = 'file.search'
    _description = "File Search"

    file_id = fields.Many2one('file', 'File Number', domain="[('state','in',['cancel', 'refund'])]")
    membership_id = fields.Many2one('res.member', string='Member No')
    tracking_id = fields.Char('Tracking ID')
    member_id = fields.Char('Member ID')
    cnic = fields.Char('CNIC')
    unit_number = fields.Char('Unit Number')

    return_line = fields.One2many('return.line', 'return_id', 'Initial Request')
    reason = fields.Char(string='Reason')

    def search_related_file(self):
        self.return_line.unlink()

        # Every filled field narrows the search together (AND) instead of only
        # the single highest-priority one being used and the rest silently
        # ignored - previously File Number and Member No couldn't be combined,
        # and membership_id was compared against its .ref string rather than
        # its id, so a Member No search rarely matched anything at all.
        domain = []
        if self.file_id:
            domain.append(('id', '=', self.file_id.id))
        if self.membership_id:
            domain.append(('membership_id', '=', self.membership_id.id))
        if self.tracking_id:
            domain.append(('tracking_id', '=', self.tracking_id.strip()))
        if self.cnic:
            domain.append(('membership_id.cnic', '=', self.cnic.strip()))
        if self.unit_number:
            domain.append(('unit_number', '=', self.unit_number.strip()))

        if not domain:
            raise ValidationError(_('Must populate one of the above field for search.'))

        record = self.env['file'].search(domain)

        if record:
            for rec in record:
                self.return_line = [(0, 0, {
                    'file_id': rec.id,
                    'return_id': self.id
                })]

        return {
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class ReturnLine(models.TransientModel):
    _name = 'return.line'
    _description = "Return Line"

    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Member Type', related='membership_id.company_type')
    cnic = fields.Char(related='file_id.membership_id.cnic')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id')
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id')
    street_id = fields.Many2one('street', related='file_id.street_id')
    inventory_id = fields.Many2one('plot.inventory', related='file_id.inventory_id')
    unit_number = fields.Char(related='inventory_id.name')
    size_id = fields.Many2one('unit.size', 'Unit Size', related='file_id.size_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='file_id.unit_category_type_id')
    unit_class_id = fields.Many2one('unit.class', related='file_id.unit_class_id')
    tracking_id = fields.Char(related='file_id.tracking_id')
    booking_date = fields.Date(related='file_id.booking_date')
    member_name = fields.Char(related='file_id.membership_id.name', readonly=True, string="Member Name")
    file_id = fields.Many2one('file', readonly=True)
    allow_request = fields.Boolean()
    reason = fields.Text()
    request_by = fields.Selection(
        string='Request By',
        selection=[('dealer', 'Dealer'),
                   ('customer', 'Customer'), ],
        required=False, default='customer')

    return_id = fields.Many2one('file.search')

    cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details', related='membership_id.cnic_line_ids', readonly=True)

    deduction_refund = fields.Float('Deduction(%)')

    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('cancelation', 'Cancellation'),
        ('refund', 'Refund'),
        ('registry', 'Registry'),
        ('next_of_kin', 'Next of kin'),
    ])
    appointment_date = fields.Datetime(string='Expected Delivery Date')

    transferee_existing_partner = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], 'Is Member ?', default='no')
    transfer_type = fields.Selection([
        ('sale', 'Sale'),
        ('gift', 'Gift'),
        ('inherit', 'Inherit'),
        ('open_file', 'Open File')
    ])
    transferee_partner_id = fields.Many2one('res.member', 'Name ', domain="[('id', '!=', membership_id)]")
    transferee_company_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'Joint Owners'),
    ], 'Transferee Type', related='transferee_partner_id.company_type', readonly=False)
    transferee_name = fields.Char('Transferee Name')
    transferee_cnic_number = fields.Char('CNIC Number')
    transferee_cnic_line_ids = fields.One2many('res.cnic', 'member_id', string='Details ', related='transferee_partner_id.cnic_line_ids', readonly=True)

    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')

    relation_name = fields.Char()
    transferee_relation_name = fields.Char()

    # Payment Plan
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    balloting_amount = fields.Float('Balloting Amount', related='file_id.balloting_amount')
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    # deal_price = fields.Float()
    total_installments_paid = fields.Float(compute='_compute_installment_amount')
    installments_paid = fields.Integer(compute='_compute_installment_amount')
    total_installments_due = fields.Float(compute='_compute_due_installment_amount')
    installments_due = fields.Integer(compute='_compute_due_installment_amount')
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids', readonly=True)
    file_payment_history_id = fields.One2many('file.payment.history', 'file_id', related='file_id.file_payment_history_id', readonly=True)

    # Kin Details
    return_kin_line_ids = fields.One2many('return.line.kin', 'return_line_id')

    traferer_setup_ids = fields.Many2many('requirements', 'requirements_return_rel', 'transfer_id', 'return_id')
    traferee_setup_ids = fields.Many2many('requirements')
    traferer_tax_setup_ids = fields.Many2many('tax.setup.lines', 'tax_requirements_return_rel', 'transfer_id', 'return_id')
    traferee_tax_setup_ids = fields.Many2many('tax.setup.lines')

    @api.depends('file_id.installment_plan_ids.invoice_created', 'file_id.installment_plan_ids.payment_status',
                 'file_id.installment_plan_ids.amount_paid')
    def _compute_installment_amount(self):
        for rec in self:
            # Every installment line counts here (Booking, Confirmation, Balloon,
            # the 36 regular ones, ...) - "Installments Paid"/"Total Installments
            # Paid" is meant to reflect everything actually paid on the file, not
            # just the regular numbered installments.
            lines = rec.file_id.installment_plan_ids.filtered(
                lambda s: s.invoice_created == True and s.payment_status == 'paid')
            rec.total_installments_paid = sum(lines.mapped('amount_paid'))
            rec.installments_paid = len(lines)

    @api.depends('file_id.installment_plan_ids.payment_status', 'file_id.installment_plan_ids.amount')
    def _compute_due_installment_amount(self):
        for rec in self:
            lines = rec.file_id.installment_plan_ids.filtered(
                lambda s: s.payment_status == 'not_paid' or s.payment_status == False)
            rec.total_installments_due = sum(lines.mapped('amount'))
            rec.installments_due = len(lines)

    @api.onchange('transaction_type')
    def transection_detail(self):

        if self.transaction_type:
            if self.transaction_type == 'transfer':
                record = self.env['setup'].search([('transaction_type', '=', 'transfer')])
                for rec in record:
                    if rec.setup_for == 'seller':
                        self.traferer_setup_ids = [[6, False, rec.requirements_ids.mapped('id')]]
                    elif rec.setup_for == 'buyer':
                        self.traferee_setup_ids = [[6, False, rec.requirements_ids.mapped('id')]]
                tax_setup = self.env['tax.setup'].search([('transaction_type', '=', 'transfer')])
                for tax in tax_setup:
                    if tax.setup_for == 'seller':
                        self.traferer_tax_setup_ids = [[6, False, tax.tax_setup_line_ids.mapped('id')]]
                    elif tax.setup_for == 'buyer':
                        self.traferee_tax_setup_ids = [[6, False, tax.tax_setup_line_ids.mapped('id')]]

    @api.onchange('transferee_partner_id')
    def onchange_transferee_partner_id(self):
        if self.transferee_partner_id:
            self.relation_id = self.transferee_partner_id.relation_id
            self.transferee_relation_name = self.transferee_partner_id.relation_name
            self.transferee_cnic_number = self.transferee_partner_id.cnic

    @api.onchange('transferee_existing_partner')
    def onchange_transferee_existing_partner(self):
        self.transferee_name = False
        self.transferee_partner_id = False
        self.transferee_relation_name = False
        self.transferee_cnic_number = False

    def add_intention(self):
        if self.file_id.file_status == 'merged_and_cancel' or self.file_id.state in ('merged', 'cancel'):
            raise ValidationError(_(
                "File %s is Merged And Cancel - it cannot be transferred, cancelled, refunded, "
                "registered or otherwise processed any further." % self.file_id.name))
        if self.transaction_type == 'transfer':
            plans_invoice_created = self.installment_plan_ids.search([('invoice_created', '=', True), ('file_id', '=', self.file_id.id)])
            # if True in self.installment_plan_ids.mapped('invoice_created'):
            if not self.allow_request and 'not_paid' in plans_invoice_created.mapped('payment_status') or 'in_payment' in plans_invoice_created.mapped(
                    'payment_status'):
                raise ValidationError(
                    _("Transfer could not process of this file while invoices are not fully paid."))
            record = self.env['file.transfer.request'].search([('file_id', '=', self.file_id.id)])
            if record and record.membership_id == self.membership_id:
                raise ValidationError(
                    _("Transfer Intention already generated for this file : %s" % (record.file_id.name)))
            else:
                record.create({
                    'file_id': self.file_id.id,
                    'transfer_type': self.transfer_type,
                    'membership_id': self.membership_id.id,
                    'transaction_type': self.transaction_type,
                    'transferee_existing_partner': self.transferee_existing_partner,
                    'appointment_date': self.appointment_date if self.appointment_date else fields.Date.today(),
                    'transferee_partner_id': self.transferee_partner_id.id,
                    'transferee_name': self.transferee_name,
                    'relation_id': self.relation_id,
                    'allow_request': self.allow_request,
                    'reason': self.reason,
                    'transferee_relation_name': self.transferee_relation_name,
                    'transferee_cnic_number': self.transferee_cnic_number,
                    'traferer_setup_ids': [[6, False, self.traferer_setup_ids.mapped('id')]],
                    'traferee_setup_ids': [[6, False, self.traferee_setup_ids.mapped('id')]],
                    'traferer_tax_setup_ids': [[6, False, self.traferer_tax_setup_ids.mapped('id')]],
                    'traferee_tax_setup_ids': [[6, False, self.traferee_tax_setup_ids.mapped('id')]]
                })
                self.file_id.state = 'inprocess'
                # return {
                #     'name': _('Transfer Request'),
                #     'view_type': 'form',
                #     'view_mode': 'form,tree',
                #     'res_model': 'file.transfer.request',
                #     'view_id': False,
                #     'type': 'ir.actions.act_window',
                #     'context': {
                #         'current_view': 'realestate'
                #     }
                # }
                return {
                    'effect': {
                        'fadeout': 'no',
                        'message': """Request Submitted Successfully""".replace('   ', ''),
                        'type': 'rainbow_man',
                    }
                }
                return {'type': 'ir.actions.act_window_close'}

        if self.transaction_type == 'cancelation':
            if self.payment_states == 'close':
                raise ValidationError(_('File which is already closed can not be Cancel.'))
            record = self.env['file.cancel.application'].search([('file_id', '=', self.file_id.id)])
            if record and record.membership_id == self.membership_id:
                raise ValidationError(
                    _("Transfer Intention already generated for this file : %s" % (record.file_id.name)))
            else:
                record.create({
                    'file_id': self.file_id.id,
                    'membership_id': self.membership_id.id,
                    'transaction_type': self.transaction_type,
                    'request_by': self.request_by,
                    'reason': self.reason,
                    'appointment_date': self.appointment_date,
                    'traferer_setup_ids': [[6, False, self.traferer_setup_ids.mapped('id')]],
                })
                self.file_id.state = 'inprocess'
                # return {
                #     'name': _('Cancellation Request'),
                #     'view_type': 'form',
                #     'view_mode': 'tree,form',
                #     'res_model': 'file.cancel.application',
                #     'view_id': False,
                #     'type': 'ir.actions.act_window',
                #     'context': {
                #         'current_view': 'realestate'
                #     }
                # }
                return {
                    'effect': {
                        'fadeout': 'no',
                        'message': """Request Submitted Successfully""".replace('   ', ''),
                        'type': 'rainbow_man',
                    }
                }
                return {'type': 'ir.actions.act_window_close'}
        if self.transaction_type == 'refund':
            if self.payment_states == 'close':
                raise ValidationError(_('File which is already closed can not be Refund.'))
            record = self.env['file.refund'].search([('file_id', '=', self.file_id.id)])
            if record and record.membership_id == self.membership_id:
                raise ValidationError(
                    _("Transfer Intention already generated of file : %s" % (record.file_id.name)))
            else:
                record.create({
                    'file_id': self.file_id.id,
                    'membership_id': self.membership_id.id,
                    'deduction_refund': self.deduction_refund,
                    # 'request_by': self.request_by,
                    # 'reason': self.reason,
                    # 'appointment_date': self.appointment_date,
                    'transaction_type': self.transaction_type,
                    'traferer_setup_ids': [[6, False, self.traferer_setup_ids.mapped('id')]],
                })

                self.file_id.state = 'inprocess'

                # return {
                #     'name': _('Refund Request'),
                #     'view_type': 'form',
                #     'view_mode': 'tree,form',
                #     'res_model': 'file.refund',
                #     'view_id': False,
                #     'type': 'ir.actions.act_window',
                #     'context': {
                #         'current_view': 'realestate'
                #     }
                # }
                return {
                    'effect': {
                        'fadeout': 'no',
                        'message': """Request Submitted Successfully""".replace('   ', ''),
                        'type': 'rainbow_man',
                    }
                }
                return {'type': 'ir.actions.act_window_close'}

        if self.transaction_type == 'registry':
            if 'not_paid' or 'in_payment' or False in self.installment_plan_ids.mapped('payment_status'):
                raise ValidationError(
                    _("Plot registry could not process of this file while invoices are not fully paid."))
            record = self.env['file.registry.request'].search([('file_id', '=', self.file_id.id)])
            if record and record.membership_id == self.membership_id:
                raise ValidationError(
                    _("Registration request already generated of file : %s" % (record.file_id.name)))
            else:
                record.create({
                    'file_id': self.file_id.id,
                    'membership_id': self.membership_id.id,
                    'transaction_type': self.transaction_type,
                    # 'request_by': self.request_by,
                    # 'reason': self.reason,
                    'appointment_date': self.appointment_date,
                })
                self.file_id.state = 'inprocess'
                # return {
                #     'name': _('Registry Request'),
                #     'view_type': 'form',
                #     'view_mode': 'tree,form',
                #     'res_model': 'file.registry.request',
                #     'view_id': False,
                #     'type': 'ir.actions.act_window',
                #     'context': {
                #         'current_view': 'realestate'
                #     }
                # }
                return {
                    'effect': {
                        'fadeout': 'no',
                        'message': """Transfer Request Submitted Successfully""".replace('   ', ''),
                        'type': 'rainbow_man',
                    }
                }
                return {'type': 'ir.actions.act_window_close'}
        if self.transaction_type == 'next_of_kin':
            record = self.env['res.kin.request'].search([('file_id', '=', self.file_id.id)])
            if record and record.membership_id == self.membership_id and record.state == 'draft':
                raise ValidationError(_("Kin request already generated of file : %s" % (record.file_id.name)))
            elif not self.return_kin_line_ids:
                raise ValidationError(_("Please add Kin details to proceed."))
            else:
                record.create({
                    'file_id': self.file_id.id,
                    'membership_id': self.membership_id.id,
                    'transaction_type': self.transaction_type,
                    'appointment_date': self.appointment_date,
                    # 'request_by': self.request_by,
                    # 'reason': self.reason,
                    'appointment_date': self.appointment_date,
                    'kin_request_line_ids': [(0, 0,
                                              {'name': kin.name,
                                               'relation_with_member': kin.relation_with_member,
                                               'relation_name': kin.relation_name,
                                               'cnic': kin.cnic,
                                               'mobile': kin.mobile,
                                               'start_date': fields.Date.today()
                                               }) for kin in self.return_kin_line_ids]
                })

                self.file_id.state = 'inprocess'

                # return {
                #     'name': _('Kin Request'),
                #     'view_type': 'form',
                #     'view_mode': 'tree,form',
                #     'res_model': 'res.kin.request',
                #     'view_id': False,
                #     'type': 'ir.actions.act_window',
                #     'context': {
                #         'current_view': 'realestate'
                #     }
                # }
                return {
                    'effect': {
                        'fadeout': 'no',
                        'message': """Transfer Request Submitted Successfully""".replace('   ', ''),
                        'type': 'rainbow_man',
                    }
                }
                return {'type': 'ir.actions.act_window_close'}


class ReturnLinekin(models.TransientModel):
    _name = 'return.line.kin'
    _description = "Return Line Kin"

    name = fields.Char('Name', required=True)
    member_name = fields.Char()
    cnic = fields.Char('CNIC')
    mobile = fields.Char('Mobile')
    relation_with_member = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('wife', 'Wife'),
        ('husband', 'Husband'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('other', 'Other'),
    ], required=True)
    relation_name = fields.Char()

    start_date = fields.Date()
    end_date = fields.Date()
    return_line_id = fields.Many2one('return.line')
