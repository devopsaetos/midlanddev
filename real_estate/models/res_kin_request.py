# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ResKinRequest(models.Model):
    _name = 'res.kin.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Kin Request"

    name = fields.Char('Sequence No', required=True, copy=False, index=True, readonly=True,
                       default=lambda self: _('New'))
    state = fields.Selection([
        ('draft','Draft'),
        ('approve','Approve'),
        ('cancel','Cancel'),
    ], default='draft', tracking=True)
    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('cancellation', 'Cancellation'),
        ('refund', 'Refund'),
        ('registry', 'Registry'),
        ('next_of_kin', 'Next of kin'),
    ])
    appointment_date = fields.Datetime()
    # File details
    file_id = fields.Many2one('file', readonly=True)
    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    member_name = fields.Char(related='file_id.membership_id.name', readonly=True, string="Member Name")
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
    tracking_id = fields.Char(related='file_id.tracking_id', tracking=True)

    # Kin Details
    kin_request_line_ids = fields.One2many('res.kin.request.lines', 'kin_request_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("res.kin.request") or _('New')

        return super(ResKinRequest, self).create(vals_list)

    def request_approve(self):
        for rec in self:
            if rec.file_id.kin_line_ids:
                for line in rec.file_id.kin_line_ids:
                    line.end_date = fields.Date.today()
            rec.file_id.kin_line_ids = [(0,0,
                                         {  'name': kin.name,
                                            'relation_with_member': kin.relation_with_member,
                                            'relation_name': kin.relation_name,
                                            'cnic': kin.cnic,
                                            'mobile': kin.mobile,
                                            'start_date': fields.Date.today()
                                        }) for kin in self.kin_request_line_ids]
            if rec.file_id.membership_id.kin_line_ids:
                for line in rec.file_id.membership_id.kin_line_ids:
                    line.end_date = fields.Date.today()
            rec.file_id.membership_id.kin_line_ids = [(0,0,
                                         {  'name': kin.name,
                                            'relation_with_member': kin.relation_with_member,
                                            'relation_name': kin.relation_name,
                                            'cnic': kin.cnic,
                                            'mobile': kin.mobile,
                                            'start_date': fields.Date.today()
                                        }) for kin in self.kin_request_line_ids]
            self.file_id.state = 'available'
            rec.state = 'approve'

    def request_cancel(self):
        for rec in self:
            rec.state = 'cancel'


class ResKinRequestLines(models.Model):
    _name = 'res.kin.request.lines'
    _description = "Kin Request Lines"

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
    kin_request_id = fields.Many2one('res.kin.request')