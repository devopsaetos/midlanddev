
from odoo import models, fields, api

class FileAttachment(models.Model):
    _name = 'file.attachment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "File Attachment"

    name = fields.Char(string='Document Type', required=True, copy=False)
    transfer_id = fields.Many2one('transfer.application')
    attachment = fields.Binary('Attachment')
    transfer_type = fields.Selection([
        ('transferer', 'Transferer'),
        ('transfree', 'Transfree')
        ],default='transfer',string='Type')

    doc_attachment_ids = fields.Many2many(
        'ir.attachment', 
        'file_attach_rel', 
        'file_id', 'attach_id', 
        string="Attachment ",
        help='You can attach the copy of your document', 
        copy=False)

class IrAttachmentExt(models.Model):
    _inherit = 'ir.attachment'
    _description = "Ir Attachment Ext"

    file_attach_rel = fields.Many2many(
        'file.attachment', 
        'doc_attachment_ids', 
        'attachment_id', 
        'file_attachment_id',
        string="Attachment ",
        invisible=1)