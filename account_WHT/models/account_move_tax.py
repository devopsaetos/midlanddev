# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class AccountMoveTax(models.Model):
    _name = "account.move.tax"
    _description = "Invoice Tax"
    _order = 'sequence'

    @api.depends('move_id.invoice_line_ids')
    def _compute_base_amount(self):
        """
        Compute the base amount for each tax line using the invoice’s tax grouping logic.
        """
        tax_grouped = {}
        for invoice in self.mapped('move_id'):
            tax_grouped[invoice.id] = invoice.get_taxes_values()

        for tax in self:
            tax.base = 0.0
            if tax.tax_id:
                key = tax.tax_id.get_grouping_key({
                    'tax_id': tax.tax_id.id,
                    'account_id': tax.account_id.id,
                    'analytic_account_id': tax.analytic_account_id.id,
                })
                if tax.move_id and key in tax_grouped.get(tax.move_id.id, {}):
                    tax.base = tax_grouped[tax.move_id.id][key]['base']
                else:
                    _logger.warning(
                        'Tax Base Amount not computable, probably due to a change in an underlying tax (%s).',
                        tax.tax_id.name
                    )

    name = fields.Char(string='Tax Description', required=True, help="Name or label for the tax line.")
    tax_id = fields.Many2one('account.tax', string='Tax', ondelete='restrict', help="The tax rule applied to the invoice.")
    move_id = fields.Many2one('account.move', string='Invoice', ondelete='cascade', index=True, help="The invoice this tax line is linked to.")
    account_id = fields.Many2one('account.account', string='Tax Account', required=True, domain=[('active', '=', True)], help="Account where the tax amount is posted.")
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic account', help="Optional analytic account for the tax line.")
    amount = fields.Monetary(help="The tax amount.")
    amount_rounding = fields.Monetary(help="Rounding adjustment applied to this tax.")
    amount_total = fields.Monetary(string="Total Amount", compute='_compute_amount_total', help="Total tax amount including rounding.")
    manual = fields.Boolean(default=True, help="Whether this tax line was entered manually.")
    sequence = fields.Integer(help="Defines the order in which tax lines are displayed on the invoice.")
    company_id = fields.Many2one('res.company', string='Company', related='account_id.company_id', store=True, readonly=True, help="Company to which this tax line belongs.")
    currency_id = fields.Many2one('res.currency', related='move_id.currency_id', store=True, readonly=True, help="Currency used in the invoice.")
    base = fields.Monetary(string='Base', compute='_compute_base_amount', store=True, help="Base amount on which the tax is calculated.")

    @api.depends('amount', 'amount_rounding')
    def _compute_amount_total(self):
        """
        Compute the total amount = tax amount + rounding.
        """
        for tax_line in self:
            tax_line.amount_total = tax_line.amount + tax_line.amount_rounding
