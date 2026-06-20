# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResCountryCode(models.Model):
    _name = 'res.country.code'
    _description = "Res Country Code"

    name = fields.Char('Country Code', required = True)
    country_id = fields.Many2one('res.country', required = True)