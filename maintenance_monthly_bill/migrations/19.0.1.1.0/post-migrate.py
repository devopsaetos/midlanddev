# -*- coding: utf-8 -*-
"""Utility and electricity are billed separately from 19.0.1.1.0 (one bill, one invoice and
one PDF per charge).

- Posted / cancelled bills keep both charges on one bill: they become 'combined' (their
  invoices are already posted).
- Draft bills are split: the draft keeps the utility charge (bill_type 'utility') and a new
  draft electricity bill takes the meter readings and the electricity arrears.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE maintenance_bill SET bill_type = 'combined' WHERE state != 'draft'")
    cr.execute("UPDATE maintenance_bill SET bill_type = 'utility' WHERE state = 'draft'")
    env = api.Environment(cr, SUPERUSER_ID, {})
    Bill = env['maintenance.bill'].with_context(tracking_disable=True, mail_create_nolog=True)
    drafts = Bill.search([('state', '=', 'draft'), ('bill_type', '=', 'utility')])
    already = Bill.search([('state', '=', 'draft'), ('bill_type', '=', 'electricity')])
    have_electricity = {(b.file_id.id, b.bill_month) for b in already}
    vals_list = []
    for bill in drafts:
        if (bill.file_id.id, bill.bill_month) in have_electricity:
            continue
        vals_list.append({
            'bill_type': 'electricity',
            'file_id': bill.file_id.id,
            'journal_id': bill.journal_id.id,
            'bill_month': bill.bill_month,
            'issue_date': bill.issue_date,
            'due_date': bill.due_date,
            'electricity_product_id': bill.electricity_product_id.id,
            'meter_no': bill.meter_no,
            'previous_reading': bill.previous_reading,
            'current_reading': bill.current_reading,
            'unit_rate': bill.unit_rate,
            'arrears_electricity': bill.arrears_electricity,
            'surcharge_percent': bill.surcharge_percent,
            'bank_note': bill.bank_note,
            'payment_note': bill.payment_note,
        })
    created = Bill.create(vals_list)
    drafts.write({'meter_no': False, 'previous_reading': 0.0, 'current_reading': 0.0,
                  'unit_rate': 0.0, 'arrears_electricity': 0.0})
    _logger.info('maintenance.bill: %s draft bills split into utility + %s electricity drafts',
                 len(drafts), len(created))
