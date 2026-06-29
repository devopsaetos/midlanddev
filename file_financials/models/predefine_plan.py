from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PredefinePlanExt(models.Model):
    _inherit = 'predefine.plan'

    confirmation_amount_period = fields.Integer()
    confirmation_period_type = fields.Selection([
        ('days', 'Day(s)'),
        ('months', 'Month(s)'),
        ('years', 'Year(s)'),
    ], default='days', tracking=True, required=True)
