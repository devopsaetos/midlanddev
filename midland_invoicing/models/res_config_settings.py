# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    midland_create_invoice_entry = fields.Boolean(
        string='Create Entry for Invoices',
        help=(
            "If enabled: posting a Midland Invoice creates Dr Receivable / Cr Revenue JV. "
            "Payment creates Dr Bank / Cr Receivable and reconciles.\n\n"
            "If disabled: no JV at invoice time. Single Dr Bank / Cr Revenue entry at payment only."
        ),
    )
    rebate_expense_account_id = fields.Many2one(
        'account.account', string='Rebate Expense Account',
        related='company_id.rebate_expense_account_id', readonly=False,
    )
    advance_from_dealer_account_id = fields.Many2one(
        'account.account', string='Advance from Dealer Account',
        related='company_id.advance_from_dealer_account_id', readonly=False,
    )
    dealer_clearance_advance_account_id = fields.Many2one(
        'account.account', string='Dealer Clearance Advance Account',
        related='company_id.dealer_clearance_advance_account_id', readonly=False,
    )

    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'midland.create_invoice_entry', default='False'
        )
        res['midland_create_invoice_entry'] = param in ('True', '1', 'true')
        return res

    def set_values(self):
        super().set_values()
        # Store as explicit string so param is never deleted (avoids False→default→True bug)
        self.env['ir.config_parameter'].sudo().set_param(
            'midland.create_invoice_entry',
            'True' if self.midland_create_invoice_entry else 'False',
        )
