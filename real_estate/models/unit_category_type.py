from odoo import models, fields, api


class UnitCategoryType(models.Model):
    _name = 'unit.category.type'
    _description = 'Unit Category Type'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    area_marla = fields.Float()
    area_sq_feet = fields.Float()
    plot_category_id = fields.Many2one('plot.category')

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('code_uniq', 'unique(code)', 'Code must be unique!'),
    # ]
