# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree as ET


class PlotInventory(models.Model):
    _inherit = 'plot.inventory'
    _description = 'Plot Inventory'

    investor_file_id = fields.Many2one('investor.file', string='Investor File', tracking=True)
    file_id = fields.Many2one('file', string='File No.', tracking=True)
