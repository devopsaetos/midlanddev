# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PlotMerger(models.TransientModel):
    _name = 'plot.merger'
    _description = "Plot Merger"

    membership_id = fields.Many2one('res.member', string='Member No')
    file_merger_line = fields.One2many('plot.merger.line', 'file_merger_id')

    file_id = fields.Many2one('file')
    visibility_check = fields.Boolean(default=False)

    file_payment_history_id = fields.One2many('file.payment.history', 'file_id',
                                              related='file_id.file_payment_history_id', readonly=True)
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids',
                                           readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    installment_created = fields.Boolean(related='file_id.installment_created', readonly=True)
    active = fields.Boolean(related='file_id.active', readonly=True)
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)

    def search_related_file(self):
        self.file_merger_line.unlink()
        for rec in self.membership_id.file_line_ids:
            self.file_merger_line.create({
                'file_id': rec.id,
                'file_merger_id': self.id
            })

        return {
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def initiate_merjer(self):
        if not self.membership_source_id and not self.cnic:
            raise ValidationError(_("Please select the member first"))

        merger_vals = {}
        print('HHHHHHHHHHHHHHHHHHHHHHH')
        if self.membership_source_id and not self.membership_target_id:
            merger_vals.update({
                'membership_id': self.membership_source_id.id,
                'merger_status': 'process'
            })

        elif self.membership_source_id and self.membership_target_id:
            merger_vals.update({
                'membership_id': self.membership_source_id.id,
                'membership_merge_to_id': self.membership_target_id.id,
                'merger_request': True
            })

        elif self.cnic and not self.tar_member_cnic:
            member_record = self.env['res.member'].search([('cnic', '=', self.cnic)], limit=1)
            merger_vals.update({
                'membership_id': member_record.id,
            })

        elif self.cnic and self.tar_member_cnic:
            member_record = self.env['res.member'].search([('cnic', '=', self.cnic)], limit=1)
            tar_member_record = self.env['res.member'].search([('cnic', '=', self.tar_member_cnic)], limit=1)
            merger_vals.update({
                'membership_id': member_record.id,
                'membership_merge_to_id': tar_member_record.id,
                'merger_request': True
            })

        if merger_vals:
            merger_request_vals = {
                'membership_id': self.membership_id,
                'file_id': self.file_id,
                'visibility_check': self.visibility_check,
                'file_payment_history_id': self.file_payment_history_id,
                'plan_description': self.plan_description,
                'payment_states': self.payment_states,
                'interval_id': self.interval_id,
                'total_installment': self.total_installment,
                'starting_date': self.starting_date,
                'sale_amount': self.sale_amount,
                'factor_amount': self.factor_amount,
                'ttl_sale_amount': self.ttl_sale_amount,
                'discount_type': self.discount_type,
                'discount_amount': self.discount_amount,
                'net_sale_amount': self.net_sale_amount,
                'installment_plan_ids': self.installment_plan_ids,
                'balance_amount': self.balance_amount,
                'installment_created': self.installment_created,
                'initial_payment': self.initial_payment,
                'file_merger_request_line': self.file_merger_line,
                'state': 'submitted'
            }
            merger_request = self.env['file.merger.request'].create(merger_request_vals)
            if merger_request:
                merger_vals.update({'file_merger_request_id': merger_request.id})
            merger_application = self.env['plot.merger.application'].with_context(active_id=False).create(merger_vals)

            # return {
            #     'name': 'Merger Request',
            #     'type': 'ir.actions.act_window',
            #     'view_mode': 'form',
            #     'view_type': 'form',
            #     'res_model': 'plot.merger.request',
            #     'target': 'current',
            #     'res_id': merger_request.id
            # }

    # def initiate_merjer(self):
    #     if not self.membership_id:
    #         raise ValidationError(
    #             _("Please select the member first"))
    #     return {
    #         'name': _('Merger'),
    #         'res_model': 'plot.merger.application',
    #         'type': 'ir.actions.act_window',
    #         'view_id': False,
    #         'view_mode': 'form',
    #         'view_type': 'form',
    #         'context': {'default_membership_id': self.membership_id.id, 'default_merger_status': 'process', 'current_view': 'realestate'}
    #     }


class PlotMergerLine(models.TransientModel):
    _name = 'plot.merger.line'
    _description = "Plot Merger Line"

    membership_id = fields.Many2one('res.member', string='Member No', related='file_id.membership_id', readonly=True)
    file_id = fields.Many2one('file', readonly=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close')
    ], default='open', readonly=True)
    file_merger_id = fields.Many2one('plot.merger', readonly=True)

    def open_payment_plan(self):
        self.file_merger_id.visibility_check = True
        for rec in self.search([('state', '=', 'close')]):
            rec.state = 'open'
        self.file_merger_id.file_id = self.file_id
        self.state = 'close'
        return {
            'type': 'ir.actions.do_nothing'
        }

    def close_payment_plan(self):
        self.file_merger_id.file_id = False
        self.file_merger_id.visibility_check = False
        self.state = 'open'
        return {
            'type': 'ir.actions.do_nothing'
        }


class FileMergerRequest(models.Model):
    _name = 'file.merger.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "File Merger Request"

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    membership_id = fields.Many2one('res.member', string='Member No')
    file_merger_request_line = fields.One2many('file.merger.request.line', 'file_merger_request_id')

    file_id = fields.Many2one('file')
    visibility_check = fields.Boolean(default=False)

    file_payment_history_id = fields.One2many('file.payment.history', 'file_id',
                                              related='file_id.file_payment_history_id', readonly=True)
    plan_description = fields.Char('Plan Description', related='file_id.plan_description', readonly=True)
    payment_states = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
    ], default='draft', related='file_id.payment_states', readonly=True)
    interval_id = fields.Many2one('payment.interval', 'Payment Interval', related='file_id.interval_id', readonly=True)
    total_installment = fields.Integer('No of Installment', related='file_id.total_installment', readonly=True)
    starting_date = fields.Date('Installment Starting Date', related='file_id.starting_date', readonly=True)
    sale_amount = fields.Float('Sale Amount', related='file_id.sale_amount', readonly=True)
    factor_amount = fields.Float(related='file_id.factor_amount', readonly=True)
    ttl_sale_amount = fields.Float('Total Sale Amount', related='file_id.ttl_sale_amount', readonly=True)
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ], default='percentage', related='file_id.discount_type', readonly=True)
    discount_amount = fields.Float(related='file_id.discount_amount', readonly=True)
    net_sale_amount = fields.Float('Net Sale Amount', related='file_id.net_sale_amount', readonly=True)
    installment_plan_ids = fields.One2many('installment.plan', 'file_id', related='file_id.installment_plan_ids',
                                           readonly=True)
    balance_amount = fields.Float('Balance Amount', related='file_id.balance_amount', readonly=True)
    installment_created = fields.Boolean(related='file_id.installment_created', readonly=True)
    active = fields.Boolean(default=True)
    initial_payment = fields.Float('Initial Payment', related='file_id.initial_payment', readonly=True)
    membership_source_id = fields.Many2one('res.member', string='Member From')
    membership_target_id = fields.Many2one('res.member', string='Member To')
    cnic = fields.Char()
    tar_member_cnic = fields.Char()
    merger_type = fields.Selection(
        string='Merger Type',
        selection=[('same_member', 'Same Member'),
                   ('member_to_member', 'Member To Member')],
        required=False, default='same_member')
    waive_merger_application = fields.Selection(
        string='Waive Fee ?',
        selection=[('yes', 'Yes'),
                   ('no', 'No')],
        default="no", required=False, tracking=True)
    appointment_date = fields.Date(string='Application Date')
    notes = fields.Text(string='Remarks')
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted')], string="Status", readonly=True,
                             tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("file.merger.request") or _('New')

        return super(FileMergerRequest, self).create(vals_list)


class FileMergerRequestLine(models.Model):
    _name = 'file.merger.request.line'
    _description = "File Merger Request Line"

    file_id = fields.Many2one('file')
    membership_id = fields.Many2one('res.member', string='Member No')
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close')
    ], default='open', readonly=True)
    file_merger_request_id = fields.Many2one('file.merger.request')
    source = fields.Boolean(string='Source')
    target = fields.Boolean(string='Target')
    total_sale_amount = fields.Float(string='Sale Amount')
    ttl_invoiced_amount = fields.Float(string='Invoiced Amount')
    amount_received = fields.Float('Received')
    amount_remaining = fields.Float('Remaining')
