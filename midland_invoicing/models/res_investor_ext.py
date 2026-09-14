# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResInvestorDealerAdvance(models.Model):
    """A dealer's Midland Payment can be confirmed for more than what's owed
    on the invoice(s) it's paying (see MidlandPayment._confirm_no_entry) -
    the excess is booked to the paying company's "Advance from Dealer"
    liability account instead of Revenue. This surfaces that running
    balance on the dealer's own record and lets it be applied to a future
    payment.

    That account is configured per-company (Settings -> Invoicing ->
    Midland Invoicing), and this business invoices/pays the same dealer
    across many group companies - so a dealer's advance is really a
    separate balance per company's own account, not one pool. The stat
    button below sums across every company purely for visibility; applying
    an advance to a new payment (see MidlandPayment.dealer_advance_available)
    is deliberately kept scoped to that payment's own company, since a
    journal entry can't debit one company's account to offset another's."""
    _inherit = 'res.investor'

    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id',
    )
    dealer_advance_balance = fields.Monetary(
        string='Advance Balance (All Companies)', compute='_compute_dealer_advance_balance',
        currency_field='currency_id',
        help='Cash this dealer has paid in that is not yet applied against '
             'any invoice, summed across every company\'s "Advance from '
             'Dealer" account. A new payment can only draw on the balance '
             'held in that payment\'s own company - see its Dealer Advance '
             'Available field.',
    )

    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id or self.env.company.currency_id

    def _dealer_advance_balance_for_company(self, company):
        """Advance balance for this dealer under one specific company's own
        "Advance from Dealer" account - what a new payment in that company
        may actually draw on."""
        self.ensure_one()
        account = company.advance_from_dealer_account_id
        if not account or not self.partner_id:
            return 0.0
        # sudo(): this is a read-only informational balance, not a bypass of
        # any write access - and it must reflect the true balance in that
        # company's own account regardless of which companies happen to be
        # toggled on in the current user's company switcher, or the figure
        # would silently read as 0/incomplete depending on an unrelated UI
        # setting (multi-company "allowed_company_ids" record rules on
        # account.move.line, not this dealer's own access).
        result = self.env['account.move.line'].sudo()._read_group(
            domain=[
                ('account_id', '=', account.id),
                ('partner_id', '=', self.partner_id.id),
                ('parent_state', '=', 'posted'),
            ],
            aggregates=['credit:sum', 'debit:sum'],
        )
        credit_sum, debit_sum = result[0] if result else (0.0, 0.0)
        return (credit_sum or 0.0) - (debit_sum or 0.0)

    # Reads live off account.move.line, which @api.depends can't express -
    # non-stored, so it's recomputed fresh whenever the field is accessed
    # (e.g. every time the dealer form is opened).
    @api.depends('partner_id')
    def _compute_dealer_advance_balance(self):
        companies = self.env['res.company'].sudo().search([
            ('advance_from_dealer_account_id', '!=', False),
        ])
        for rec in self:
            rec.dealer_advance_balance = sum(
                rec._dealer_advance_balance_for_company(company) for company in companies
            )

    def action_view_dealer_advance_ledger(self):
        self.ensure_one()
        accounts = self.env['res.company'].sudo().search([
            ('advance_from_dealer_account_id', '!=', False),
        ]).mapped('advance_from_dealer_account_id')
        return {
            'name': _('Dealer Advance Ledger'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('account_id', 'in', accounts.ids),
                ('partner_id', '=', self.partner_id.id),
                ('parent_state', '=', 'posted'),
            ],
            'context': {'search_default_group_by_move': 1},
        }
