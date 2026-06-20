from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class AllotmentLine(models.Model):
    _name = 'allotment.line'
    _description = 'Allotment Line'

    name = fields.Char(string='Name')

class AllotmentRequest(models.Model):
    _name = 'allotment.request'
    _description = 'Allotment Line'

    name = fields.Char(string='Name')