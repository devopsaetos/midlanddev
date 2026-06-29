# -- coding: utf-8 --
from odoo import models, fields, api, _
import base64


class File(models.Model):
    _inherit = 'file'

    allotment_id = fields.Many2one('allotment.batch', string="Allotment Batch", tracking=True)
    allotment_date = fields.Date('Allotment Date')
    allotment_by = fields.Many2one('res.users', 'Allotment By')

    printed_date = fields.Date('Printed Date')
    printed_by = fields.Many2one('res.users', 'Printed By')

    issued_date = fields.Date('Issued Date')
    issued_by = fields.Many2one('res.users', 'Issued By')

    collected_date = fields.Date('Collected Date')
    collected_by = fields.Many2one('res.users', 'Colllected By')

    allotment_detail_ids = fields.One2many('allotment.details', 'file_id')


class AllotmentDetails(models.Model):
    _name = 'allotment.details'
    _description = 'Allotment Details'

    date = fields.Date()
    transaction_type = fields.Selection([
        ('allotment', 'Allotment'),
        ('file', 'New File'),
        ('processing','Processing'),
        ('file_re_issue','File Re-Issue'),
        ('file_transfer','File Transfer'),
    ])
    print_date = fields.Date()
    issue_date = fields.Date('Issued Date')
    print_by = fields.Many2one('res.users', 'Printed By')
    issued_by = fields.Many2one('res.users', 'Issued By')
    allotment_batch_id = fields.Many2one('allotment.batch', string="Allotment #")

    file_id = fields.Many2one('file')



