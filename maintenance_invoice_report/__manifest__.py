# -*- coding: utf-8 -*-
{
    'name': "Maintenance Invoice Report",

    'summary': """
        This module to print Maintenance Invoice Report""",

    'description': """
    """,

    'author': "Yasir Ali || Axiom Team",
    'website': "http://www.axm.app",
    'category': 'Real Estate',
    'version': '19.0.1.0.0',

    'depends': [
        'file_financials',
        # 'accounting_pdf_reports',  # not available in Odoo 19 project (only exists in old Odoo 13/17 source trees)
    ],
    'data': [
        'wizard/maintenance_charges_wizard.xml',
        'views/account_move_ext.xml',
        'report/maintenance_charges_report.xml',
        'report/maintenance_charges_invoice_report.xml',
    ],

}
