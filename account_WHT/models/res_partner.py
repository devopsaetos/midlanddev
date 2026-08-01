# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_tax_collection_body = fields.Boolean(
        string='Is Tax Collection Body',
        help="Check this if the partner represents a tax collection body/authority."
    )
