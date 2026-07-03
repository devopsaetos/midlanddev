# -*- coding: utf-8 -*-
"""
res.investor.name was renamed to res.investor.investor_id and made required.
Existing rows created before the rename have investor_id = NULL, which blocks
Odoo from adding the NOT NULL constraint on upgrade. Backfill those rows here
so the schema migration in _auto_init can proceed.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE res_investor
        SET investor_id = COALESCE(
            NULLIF(investor_id, ''),
            NULLIF(owner_name, ''),
            'Investor ' || id
        )
        WHERE investor_id IS NULL OR investor_id = ''
    """)
