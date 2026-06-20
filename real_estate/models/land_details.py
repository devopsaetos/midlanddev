from odoo import fields, models, api


class LandDetails(models.Model):
    _name = 'land.details'
    _description = 'Land Details'

    khasra = fields.Char()
    khatuni = fields.Char()
    city_id = fields.Many2one('city')
    mauza = fields.Char()

    # Ex Owner Details
    name = fields.Char()
    cnic = fields.Char()

    inventory_id = fields.Many2one('plot.inventory')