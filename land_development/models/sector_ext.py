from odoo import fields, models, api


class SectorEXT(models.Model):
    _inherit = 'sector'

    floor_type = fields.Selection([
        ('residential', 'Residential'),
        ('parking', 'Parking'),
        ('commercial', 'Commercial'),
    ])
