# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResAuthority(models.Model):
    _name = 'res.authority'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Authority"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required = True)
    code = fields.Char(required = True)
    location_id = fields.Many2one('location')