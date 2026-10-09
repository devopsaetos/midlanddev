# -*- coding: utf-8 -*-
{
    'name': "Maintenance Collection Report",
    'license': 'LGPL-3',
    'summary': """
        Generate Maintenance Collection Report based on various filters.""",
    'description': """
       Generate Maintenance Collection Report based on various filters""",

    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'website': "https://www.aetostechnology.com",
    'category': 'Account',
    'version': '19.0.1.0.4',
    'depends': ['maintenance_charges'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_inherit.xml',

        'report/report.xml',
        'report/maintenance_collection_report.xml',
        'wizard/maintenance_collection_report_wizard.xml',
    ]
}
