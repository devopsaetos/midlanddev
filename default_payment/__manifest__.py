# -*- coding: utf-8 -*-
{
    'name': "Default Payment",

    'summary': """
        Change the default view of Invoice and Vendor payments to Payments form """,

    'description': """
        Change the default view of Invoice and Vendor payments to Payments form """,

    'author': "Wahab Ali Malik || Axiom Team",
    'website': "https://www.axiomworld.net",
    'category': 'Invoicing',
    'version': '1.2',
    'depends': ['account'],
    'data': [
        'security/multi_invoice_logs_security.xml',
        'security/ir.model.access.csv',
        'wizard/apply_advance_payment.xml',
        'views/account_payment.xml',
        'views/multi_invoice_payment.xml',
        'views/account_move.xml',
        # 'views/report_invoice.xml',    # kept commented until report is verified
        # 'views/res_config_setting.xml', # kept commented until config is verified
    ],
    'auto_install': True
}
