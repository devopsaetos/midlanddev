

from odoo import fields, models


class FileInstallmentRemaining(models.Model):
    _name = 'installment.remaining'
    _description = 'Installment Remaining'

    file_id = fields.Many2one('file')
    remaining_installments = fields.Integer()

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('unique_file', 'UNIQUE(file_id)',
    #      'file can only one in these records')
    # ]
