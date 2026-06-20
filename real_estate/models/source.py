# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Source(models.Model):
    _name = 'source'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Source"

    name = fields.Char()
