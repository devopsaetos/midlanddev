# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class PlotCategory(models.Model):
    _name = 'plot.category'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Plot Category"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True)
    code = fields.Char(required=True)

    _sql_constraints = [
        ('code_uniq', 'unique (code)',
         'Code must be unique !')
    ]