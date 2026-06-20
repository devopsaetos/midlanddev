# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FileRegistryRequest(models.Model):
    _name = 'file.registry.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "File Registry Request"

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))

    membership_id = fields.Many2one('res.member', string='Member No')
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
    member_name = fields.Char(related='file_id.membership_id.name')
    file_id = fields.Many2one('file')
    tracking_id = fields.Char(related='file_id.tracking_id')
    booking_date = fields.Date(related='file_id.booking_date')

    transfer_type = fields.Selection([
        ('sale', 'Sale'),
        ('gift', 'Gift'),
        ('inherit', 'Inherit')
    ])

    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('cancelation', 'Cancellation'),
        ('merge', 'Merge'),
        ('refund', 'Refund'),
        ('registry', 'Registry'),
    ], readonly=True)

    is_transferee_partner = fields.Boolean('Is Member ?', readonly=True)
    transferee_partner_id = fields.Many2one('res.member', 'Name ', readonly=True)
    transferee_name = fields.Char('Transferee Name', readonly=True)
    relation_id = fields.Selection([
        ('S/O', 'S/O'),
        ('D/O', 'D/O'),
        ('BR/O', 'BR/O'),
        ('WD/O', 'WD/O'),
        ('WF/O', 'WF/O')
    ], default='S/O')

    relation_name = fields.Char(related='membership_id.relation_name')
    transferee_relation_name = fields.Char()
    transferee_cnic_number = fields.Char('CNIC Number', readonly=True)

    file_payment_history_id = fields.One2many('file.payment.history', 'file_id',
                                              related='file_id.file_payment_history_id')
    plan_description = fields.Char('Plan Description', related='file_id.plan_description')
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states')
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id')
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment')
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date')
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount')
    factor_amount = fields.Float(related='file_id.factor_amount')
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount')
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type')
    discount_amount = fields.Float(related='file_id.discount_amount')
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount')
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids')
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount')
    total_installments_paid = fields.Float(compute='_compute_installment_amount')
    installments_paid = fields.Integer(compute='_compute_installment_amount')
    total_installments_due = fields.Float(compute='_compute_due_installment_amount')
    installments_due = fields.Integer(compute='_compute_due_installment_amount')
    installment_created = fields.Boolean(related='file_id.installment_created')
    active = fields.Boolean(related='file_id.active')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancel', 'Cancel')
    ], default='draft')
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment')

    # traferer_setup_ids = fields.Many2many('requirements', 'requirements_transfer_request_rel', 'transfer_request_id',
    #                                       'requirement_id', readonly=True)
    # traferee_setup_ids = fields.Many2many('requirements', readonly=True)

    def _compute_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(
            lambda s: s.installment_type != 'down' and s.invoice_created == True and s.payment_status == 'paid')
        self.total_installments_paid = 0
        self.installments_paid = 0
        if rec:
            self.total_installments_paid = sum(rec.mapped('amount_paid'))
            self.installments_paid = len(rec)

    def _compute_due_installment_amount(self):
        rec = self.file_id.installment_plan_ids.filtered(
            lambda s: s.installment_type != 'down' and s.payment_status == 'not_paid' or s.payment_status == False)
        self.total_installments_due = 0
        self.installments_due = 0
        if rec:
            self.total_installments_due = sum(rec.mapped('amount'))
            self.installments_due = len(rec)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("file.registry.request") or _('New')

        rec = super(FileRegistryRequest, self).create(vals_list)

        return rec

    def request_cancel(self):
        self.unlink()
        self.state = 'cancel'

    def request_generate(self):
        rec = self.env['transfer.application']
        if not rec.search([('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]):
            self.file_id.state = 'inprocess'

            rec.create({
                'file_id': self.file_id.id,
                'membership_id': self.membership_id.id,
                't_request_id': self.id,
                'is_transferee_partner': self.is_transferee_partner,
                'transferee_partner_id': self.transferee_partner_id.id,
                'transferee_name': self.transferee_name,
                'transferee_cnic_number': self.transferee_cnic_number,
            })

            # attachment = self.env['file.attachment']
            #
            # for recs in self.traferer_setup_ids:
            #     attachment.create({
            #         'name': recs.name,
            #         'transfer_type': 'transferer',
            #         'transfer_id': rec.search(
            #             [('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]).id
            #     })
            #
            # for recs in self.traferee_setup_ids:
            #     attachment.create({
            #         'name': recs.name,
            #         'transfer_type': 'transfree',
            #         'transfer_id': rec.search(
            #             [('file_id', '=', self.file_id.id), ('membership_id', '=', self.membership_id.id)]).id
            #     })
            self.state = 'approved'
        else:
            raise ValidationError(_("Registry form already generated of file : %s" % (self.file_id.name)))
