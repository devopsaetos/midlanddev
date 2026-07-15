# -*- coding: utf-8 -*-
{
    'name': "Maintenance Recovery Batch",

    'summary': """
    This module for to save daily record of maintenance invoice on daily basis
        """,

    'description': """
            This module for to save daily record of maintenance invoice on daily basis

    """,

    'author': "Yasir Ali",
    'website': "http://www.necityparadise.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['default_payment', 'maintenance_charges', 'maintenance_invoice_report'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/account_journal.xml',
        'views/daily_maintenance_batch.xml',
        'views/res_company.xml',
        'wizard/maintenance_electricity_invoices_wizard.xml',
        'wizard/select_daily_batch_invoices.xml',
        'report/maintenance_batch_report.xml',
        'demo/sequence.xml',
        'demo/demo.xml',
    ],
}
