def migrate(cr, version):
    # property_account_income_id is switching from a single shared integer column
    # to a company_dependent (jsonb) one. Postgres can't cast int -> jsonb, so
    # capture the old value, then drop the column outright — otherwise Odoo's
    # _auto_init() tries an in-place ::jsonb cast and the upgrade fails.
    cr.execute("""
        CREATE TABLE IF NOT EXISTS _upgrade_product_realestate_income_account AS
        SELECT id AS product_realestate_id, property_account_income_id AS old_account_id
        FROM product_realestate
        WHERE property_account_income_id IS NOT NULL
    """)
    cr.execute("""
        ALTER TABLE product_realestate DROP COLUMN IF EXISTS property_account_income_id
    """)
