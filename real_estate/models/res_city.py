# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResCity(models.Model):
    _name = 'city'
    _description = "City"

    name = fields.Char('City Name', required=True)
    zip = fields.Char('ZIP', required=True)
    zipcode = fields.Char(related='zip', string='ZIP Code', store=False)
    state_id = fields.Many2one('res.country.state', string='Province', required=True)
    country_id = fields.Many2one(related='state_id.country_id', string='Country', store=False)