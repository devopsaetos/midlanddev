# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProductTemplateExt(models.Model):

    _inherit = 'product.template'

    _description = "Product Ext"

    is_include_net_amount = fields.Boolean()
    is_include_property_system = fields.Boolean()
