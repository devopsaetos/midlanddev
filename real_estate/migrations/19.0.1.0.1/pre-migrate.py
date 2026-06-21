_PRODUCT_NAMES = [
    'installment_product', 'rebate_product', 'refund_product',
    'preferences_product', 'possession_amount_product',
    'confirmation_amount_product', 'downpayment_product',
    'balloting_product', 'final_product', 'additional_balloon',
    'lump_sum_product', 'token_money', 'token_refund',
    'token_adjustment', 'token_cancel', 'balloon_payment',
    'investment', 'investment_installment', 'investment_adjustment',
    'file_transfer', 'deductions', 'unit_swapping_charges',
]


def migrate(cr, version):
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'real_estate'
          AND model  = 'product.product'
          AND name   = ANY(%s)
    """, [_PRODUCT_NAMES])
