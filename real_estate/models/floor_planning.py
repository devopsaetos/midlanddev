# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FloorPlanning(models.Model):
    _name = 'floor.planning'
    _description = 'Floor Planning'

    rent_area = fields.Float()
    common_area = fields.Float()

    sector_id = fields.Many2one('sector')
