# -*- coding: utf-8 -*-
{
    'name': "Maintenance Recovery",
    'license': 'LGPL-3',
    'summary': """
        Generate Maintenance Recovery Report based on various filters.""",
    'description': """
       Generate Maintenance Recovery Report based on various filters""",

    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'website': "https://www.aetostechnology.com",
    'category': 'Account',
    'version': '19.0.1.0.0',
    'depends': ['file_financials'],
    'data': [
        # Odoo 19: TransientModel wizards require an explicit ir.model.access.csv row
        # (same fix applied to maintenance_collection_report in this migration batch) -
        # re-enabled below with a corrected row for the actual wizard model.
        'security/ir.model.access.csv',
        'report/report.xml',
        'report/maintenance_recovery_report.xml',
        'wizard/maintenance_recovery_report_wizard.xml',
    ]
}
