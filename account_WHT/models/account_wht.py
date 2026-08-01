# -*- coding: utf-8 -*-
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class AccountWHT(models.Model):
    _name = "account.wht"
    _description = "Account WHT"

    @api.model
    def _default_wht_tax_group(self):
        return self.env['account.tax.group'].search([('is_wht', '=', True)], limit=1)

    name = fields.Char(string='Name', required=True, copy=False, help="Name of the withholding tax.")
    tax_code = fields.Char(string='Tax Code', required=True, copy=False, help="Unique code identifying the tax.")
    type_tax_use = fields.Selection([
        ('tax', 'Withholding of Taxes'),
        ('sale', 'Sales'),
        ('purchase', 'Purchases')],
        string='Tax Scope', required=True, default="sale", help="Defines where this tax is applied: sales, purchases, or WHT.")

    tax_application = fields.Selection([
        ('payment', 'At Payment'),
        ('invoice', 'At Invoice')],
        string='Tax Application', default="payment", help="Choose when to apply the WHT: at invoice or at payment.")

    bill_to = fields.Many2one('res.partner', string='Bill To', domain=[('is_tax_collection_body', '=', True)])


    sale_tax_id = fields.Many2one('account.tax', string='Sales Tax', help="Used to define dependency between WHT and sales tax.")
    amount_type = fields.Selection([
        ('group', 'Group of Taxes'),
        ('fixed', 'Fixed'),
        ('percent', 'Percentage of Price'),
        ('division', 'Percentage of Price Tax Included')],
        default='percent', string="Tax Computation", required=True,
        help="Specifies how the tax amount is calculated.")

    active = fields.Boolean(default=True, help="Set to False to deactivate the WHT without deleting it.")
    amount = fields.Float(required=True, digits=(16, 4), help="Rate or fixed value of the WHT.")

    account_id = fields.Many2one(
        'account.account',
        domain=[('active', '=', True)],
        string='WHT Account',
        ondelete='restrict',
        help="The account where WHT entries are posted.")

    refund_account_id = fields.Many2one(
        'account.account',
        domain=[('active', '=', True)],
        string='WHT Account on Credit Notes',
        ondelete='restrict',
        help="Account used when WHT is applied on refund/credit notes.")

    description = fields.Text(help="Detailed explanation or notes for this WHT.")
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="Company to which this WHT belongs.")

    tax_group_id = fields.Many2one(
        'account.tax.group',
        string="Tax Group",
        domain=[('is_wht', '=', True)],
        default=_default_wht_tax_group,
        required=True,
        help="Group of related taxes for reporting purposes.")

    tax_section_id = fields.Many2one(
        comodel_name='tax.section',
        required=False,
        help="Optional section or category used to group this WHT.")

    @api.onchange('account_id')
    def onchange_account_id(self):
        """
        Automatically set the refund account to the same as the WHT account
        if not manually specified.
        """
        self.refund_account_id = self.account_id

    def copy(self, default=None):
        """
        Override the copy method to append ' (Copy)' to name and tax code.
        """
        default = dict(default or {})
        default.update({
            'name': self.name + ' (Copy)' if self.name else "New WHT",
            'tax_code': self.tax_code + ' (Copy)' if self.tax_code else "Code"
        })
        return super(AccountWHT, self).copy(default)
