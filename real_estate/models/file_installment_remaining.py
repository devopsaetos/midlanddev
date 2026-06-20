

from odoo import fields, models


class FileInstallmentRemaining(models.Model):
    _name = 'installment.remaining'
    _description = 'Installment Remaining'

    file_id = fields.Many2one('file')
    remaining_installments = fields.Integer()

    _sql_constraints = [
        ('unique_file', 'UNIQUE(file_id)',
         'file can only one in these records')
    ]