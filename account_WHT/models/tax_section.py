from odoo import fields, models, api


class TaxSection(models.Model):
    _name = 'tax.section'
    _description = 'Tax Section'

    name = fields.Char(required=True)
    code = fields.Char(required=True)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Code must be unique.')
    ]
    


