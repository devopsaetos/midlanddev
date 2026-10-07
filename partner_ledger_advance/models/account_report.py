# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Domain

from .account_account import PAYABLE_TYPE, RECEIVABLE_TYPE

# account type read by a partner report -> the advance accounts read with it
ADVANCE_SIDE = {PAYABLE_TYPE: 'payable', RECEIVABLE_TYPE: 'receivable'}


class AccountReport(models.Model):
    _inherit = 'account.report'

    @api.model
    def _get_options_account_type_domain(self, options):
        """Partner Ledger account filter: Payable also reads supplier advance accounts,
        Receivable also reads customer advance accounts (trade side only)."""
        domain = super()._get_options_account_type_domain(options)
        account_types = options.get('account_type') or []
        if not account_types:
            return domain
        selected = {opt['id'] for opt in account_types if opt.get('selected')} or {opt['id'] for opt in account_types}
        sides = [side for opt_id, side in (('trade_payable', 'payable'), ('trade_receivable', 'receivable'))
                 if opt_id in selected]
        if not sides:
            return domain
        return Domain.OR([domain, Domain('account_id.partner_advance_type', 'in', sides)])

    def _get_report_query(self, options, date_scope, domain=None):
        """Aged Payable / Receivable read one account type (passed as the domain); read the
        matching advance accounts with it."""
        if self.env.context.get('partner_advance_accounts') and domain:
            conditions = list(domain) if isinstance(domain, (list, tuple)) else None
            if (conditions and len(conditions) == 1 and isinstance(conditions[0], (list, tuple))
                    and tuple(conditions[0][:2]) == ('account_id.account_type', '=')
                    and conditions[0][2] in ADVANCE_SIDE):
                domain = Domain.OR([Domain(conditions),
                                    Domain('account_id.partner_advance_type', '=', ADVANCE_SIDE[conditions[0][2]])])
        return super()._get_report_query(options, date_scope, domain=domain)


class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'

    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, next_groupby,
                                                  offset=0, limit=None):
        return super(AgedPartnerBalanceCustomHandler, self.with_context(partner_advance_accounts=True)) \
            ._aged_partner_report_custom_engine_common(options, internal_type, current_groupby, next_groupby,
                                                       offset=offset, limit=limit)
