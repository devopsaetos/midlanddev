# -*- coding: utf-8 -*-
{
    'name': "Withholding Tax - WHT",
    'version': '19.0.1.0.0',
    'summary': "Deduct Withholding Tax (WHT) at the time of Payment or Invoice/Bill.",
    'description': """
This module provides functionality for the configuration, calculation, and deduction of Withholding Tax (WHT).
It enables businesses to apply WHT based on regional tax regulations during vendor/customer invoice or payment validation.

Key Features:
- Define and configure WHT rules per region.
- Auto-deduct WHT at invoice posting or payment.
- Dedicated reports and tracking for WHT deductions.
- Supports both customer and vendor bills.
""",
    'author': 'Syed Hamza',
    'maintainer': 'Aetos Technology',
    'website': 'https://www.aetostechnology.com',
    'category': 'Accounting',
    'license': 'OPL-1',
    'depends': ['account', 'account_batch_payment'],
    'data': [
        'data/wht_data.xml',
        'security/account_wht_security.xml',
        'security/ir.model.access.csv',
        'views/account_wht.xml',
        'views/res_partner_views.xml',

        'views/account_move.xml',
        'views/account_payment.xml',
        'views/account_payment_register.xml',
        'views/account_tax.xml',
        'views/tax_section.xml',
        'wizard/wht_bill_wizard.xml',
    ],
    'images': [
        'static/description/banner.gif',
        'static/description/icon.png',
    ],
    'price': 190,
    'currency': 'USD',
    'installable': True,
    'application': True,
    'auto_install': False,
    'demo': [
        # 'demo/wht_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Include custom frontend assets if needed, e.g.:
            # 'your_module/static/src/js/wht.js',
            # 'your_module/static/src/css/wht.css',
        ],
    },
}
