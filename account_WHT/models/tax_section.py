from odoo import fields, models, api


class TaxSection(models.Model):
    _name = 'tax.section'
    _description = 'Tax Section'

    name = fields.Char(required=True)
    code = fields.Char(required=True)

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('code_uniq', 'unique (code)', 'Code must be unique.')
    # ]
    


