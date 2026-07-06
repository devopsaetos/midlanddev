from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    cr.execute("SELECT to_regclass('_upgrade_product_realestate_income_account')")
    if not cr.fetchone()[0]:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT product_realestate_id, old_account_id FROM _upgrade_product_realestate_income_account")
    rows = cr.fetchall()

    companies = env['res.company'].search([])
    for product_realestate_id, old_account_id in rows:
        old_account = env['account.account'].browse(old_account_id)
        product = env['product.realestate'].browse(product_realestate_id)
        if not old_account.exists() or not product.exists():
            continue

        account_name = old_account.name
        for company in companies:
            # Same account name, but the copy that actually belongs to this company —
            # never blindly reuse old_account itself, that was the whole bug.
            match = env['account.account'].search([
                ('name', '=', account_name),
                ('company_ids', 'in', company.id),
            ], limit=1)
            if match:
                product.with_company(company).property_account_income_id = match.id

        product._sync_income_account_to_shadow()

    cr.execute("DROP TABLE _upgrade_product_realestate_income_account")
