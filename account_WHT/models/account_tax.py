# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    """Inherits account.tax to customize tax grouping behavior for invoice taxes."""
    _inherit = 'account.tax'

    def get_grouping_key(self, invoice_tax_val):
        """Return a unique grouping key for invoice tax lines.

        This key is used to group tax lines that share the same:
        - Tax ID
        - Account ID
        - Analytic Account ID

        :param invoice_tax_val: Dictionary containing tax line values with keys:
                                'tax_id', 'account_id', and 'analytic_account_id'
        :return: A string grouping key in the format: 'tax_id-account_id-analytic_account_id'
        """
        self.ensure_one()
        return str(invoice_tax_val['tax_id']) + '-' + str(invoice_tax_val['account_id']) + '-' + str(
            invoice_tax_val['analytic_account_id'])
