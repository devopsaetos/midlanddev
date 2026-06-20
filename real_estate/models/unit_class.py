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

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique'),
    ]

