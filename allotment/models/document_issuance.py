from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError


class DocumentIssance(models.Model):
    _name = 'document.issuance'
    _description = 'Document Issuance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    document_type = fields.Selection([('allotment', 'Allotment'),
                                      ('file', 'File'),
                                      ('processing_letter', 'Processing Letter')])
    member_id = fields.Many2one('res.member', string='Member No', tracking=True)
    files_id = fields.Many2one('file', string='File', domain=[('printed_date', '!=', False)], tracking=True)

    received_date = fields.Date('Received Date')
    received_by = fields.Many2one('res.member', string='Received By', required=True)
    receiver_cnic = fields.Char('CNIC', copy=False)
    file_ids = fields.Many2many('file', string="Files")
    state = fields.Selection([('draft', 'Draft'), ('issue', 'Issued')], string='Status', default='draft')

    def action_issuance(self):
        if self.user_has_groups('allotment.group_allotment_issue'):
            for file in self.file_ids:
                allotment = file.allotment_detail_ids.search([('transaction_type','=', self.document_type)], limit=1)
                if not allotment:
                    raise ValidationError('This file has not been allotted any unit.')
                else:
                    allotment.write({'issue_date': self.received_date, 'issued_by': self.env.user.id})
            self.write({'state': 'issue'})
        else:
            raise UserError(_('User has no access'))
