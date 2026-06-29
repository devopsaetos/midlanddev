# -*- coding: utf-8 -*-
{
    'name': 'Midland Invoicing',
    'version': '19.0.1.0.0',
    'category': 'Real Estate',
    'author': 'Midland',
    'license': 'OEEL-1',
    'depends': ['file_financials', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'data/post_migration.xml',
        'views/res_config_settings_views.xml',
        'views/midland_invoice_views.xml',
        'views/midland_payment_views.xml',
        'views/file_ext_views.xml',
        'views/menuitems.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
