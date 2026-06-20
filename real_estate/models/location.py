# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class Location(models.Model):
    _name = 'location'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Location"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True, string='Name')
    street = fields.Char(required=True, string='Street')
    zip = fields.Char(change_default=True, related='city_id.zip', readonly=True)
    city_id = fields.Many2one('city', change_default=True, required=True, string='City')
    state_id = fields.Many2one("res.country.state", string='Province',change_default=True, related='city_id.state_id', readonly=True)
    country_id = fields.Many2one('res.country', string='Country',change_default=True, related='state_id.country_id', readonly=True)


    @api.depends('name', 'street', 'city_id')
    def name_get(self):
        result = []
        for record in self:
            name = "%s, %s %s" %(record.name,record.street,record.city_id.name)
            result.append((record.id, name))
        return result