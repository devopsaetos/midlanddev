from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError

class PrintingHistory(models.Model):
    _name = 'printing.history'
    _description = 'Printing History'

    document_type = fields.Char()
    file_id = fields.Many2one('file')
    print_date = fields.Date(string='Print Date')
    print_by = fields.Many2one('res.users')
