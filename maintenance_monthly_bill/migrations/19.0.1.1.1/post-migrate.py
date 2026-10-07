# -*- coding: utf-8 -*-
"""The 19.0.1.1.0 split copied the electricity product of the old draft bills, which was the
Maintenance Charges product on the drafts generated on 2026-10-06. Point draft electricity
bills at the Electricity product.
Bills posted with nothing to invoice (no invoice, 0 due) go back to draft, so they can be filled
and posted again."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    electricity = env['product.product'].search([('name', '=', 'Electricity'), ('type', '=', 'service')], limit=1)
    if not electricity:
        return
    drafts = env['maintenance.bill'].search([('state', '=', 'draft'), ('bill_type', '=', 'electricity'),
                                             ('electricity_product_id', '!=', electricity.id)])
    drafts.with_context(tracking_disable=True).write({'electricity_product_id': electricity.id})
    _logger.info('maintenance.bill: electricity product fixed on %s draft bills', len(drafts))

    empty = env['maintenance.bill'].search([('state', '=', 'posted'), ('bill_type', 'in', ('utility', 'electricity')),
                                            ('invoice_id', '=', False), ('utility_invoice_id', '=', False),
                                            ('electricity_invoice_id', '=', False)])
    empty = empty.filtered(lambda b: not b.due_amount)
    empty.write({'state': 'draft'})
    _logger.info('maintenance.bill: %s empty posted bills set back to draft: %s', len(empty), empty.mapped('name'))
