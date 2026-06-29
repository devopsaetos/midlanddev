# -*- coding: utf-8 -*-

import qrcode
import base64
from io import BytesIO
from werkzeug import url_encode
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import dateutil.parser
from lxml import etree as ET
import random
import string


class ResBranchExtension(models.Model):
    _inherit = 'res.branch'

    # Currency
    currency_id = fields.Many2one('res.currency', tracking=True, required=True,
                                  string='Currency',
                                  default=lambda self: self.env.company.currency_id.id)
    foreign_currency = fields.Boolean()
    rate_type = fields.Selection([
        ('user', 'User'),
        ('corporate', 'Corporate'),
        ('spot', 'Spot'),
    ])

    @api.onchange('currency_id')
    def onchange_currency_id(self):
        for rec in self:
            if rec.currency_id != rec.env.company.currency_id:
                rec.foreign_currency = True
            else:
                rec.foreign_currency = False