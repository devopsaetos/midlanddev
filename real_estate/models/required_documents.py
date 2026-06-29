# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class Setup(models.Model):
    _name = 'setup'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Setup"

    name = fields.Char(required=True)
    
    transaction_type = fields.Selection([
        ('transfer','Transfer'),
        ('cancelation','Cancelation'),
        ('merge','Merge'),
        ('refund','Refund'),
        ])
    setup_for = fields.Selection([
        ('buyer','Buyer'),
        ('seller','Seller'),
        ])

    requirements_ids = fields.Many2many('requirements','setup_id')

class Requirements(models.Model):
    _name = 'requirements'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Requirements"

    name = fields.Char(required=True)
    description = fields.Text()
    setup_id = fields.Many2one('setup')
    # transfer_id = fields.Many2one('file.transfer')

class RequiredDocuments(models.Model):
    _name = 'required.documents'
    _description = "Required Documents"

    name = fields.Char(required=True)
    transfer_req_id = fields.Many2one('file.transfer.request')
    transfer_app_id = fields.Many2one('transfer.application')

    required_documents_line_ids = fields.One2many('required.documents.line', 'required_documents_id')

    # @api.model
    # def create(self, vals):
    #     res = super().create(vals_list)
        # for record in res.required_documents_line_ids:
        # if not all(res.required_documents_line_ids.mapped('attachment')):
        #     raise ValidationError('Please attach all the required documents.')


class RequiredDocumentsLine(models.Model):
    _name = 'required.documents.line'
    _description = "Required Documents Lines"

    name = fields.Char()
    attachment = fields.Binary(attachment=True, required=True)
    rule = fields.Many2one('setup')
    party = fields.Selection([
        ('buyer','Buyer'),
        ('seller','Seller'),
        ])

    required_documents_id = fields.Many2one('required.documents')