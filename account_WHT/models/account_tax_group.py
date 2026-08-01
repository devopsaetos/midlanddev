# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)


class AccountTaxGroup(models.Model):
    """Extension of Account Tax Group to mark tax groups as WHT (Withholding Tax)."""
    _inherit = 'account.tax.group'

    is_wht = fields.Boolean('WHT', help='Enable this option to mark this tax group as a Withholding Tax (WHT).')
