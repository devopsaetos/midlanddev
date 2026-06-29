import json
import base64
import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class InvestmentHistoryExt(models.Model):
    _inherit = 'investment.history'
    _description = 'Investment History'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
