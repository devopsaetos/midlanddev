from odoo import models, fields, api, _


class UnitClass(models.Model):
    _name = 'unit.class'
    _description = 'Unit Class'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char()
    code = fields.Char()

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('code_uniq', 'unique(code)', 'Code must be unique'),
    # ]

