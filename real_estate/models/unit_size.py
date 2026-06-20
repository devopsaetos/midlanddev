# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class UnitSize(models.Model):
    _name = 'unit.size'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Unit Size"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char()
    from_area = fields.Integer('Area From(sft)')
    to_area = fields.Integer('Area To(sft)')
    code = fields.Char()
    standard_area = fields.Float('Standard Area (sft)')