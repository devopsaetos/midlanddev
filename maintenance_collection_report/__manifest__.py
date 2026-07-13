# -*- coding: utf-8 -*-
{
    'name': "Maintenance Collection Report",
    'summary': """
        Generate Maintenance Collection Report based on various filters.""",
    'description': """
       Generate Maintenance Collection Report based on various filters""",

    'author': "Yasir Ali| Data Elite",
    'website': "dateelite.tech",
    'category': 'Account',
    'version': '19.0.1.0.0',
    'depends': ['maintenance_charges'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_inherit.xml',

        'report/report.xml',
        'report/maintenance_collection_report.xml',
        'wizard/maintenance_collection_report_wizard.xml',
    ]
}
