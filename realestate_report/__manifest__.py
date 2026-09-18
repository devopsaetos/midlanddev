# -*- coding: utf-8 -*-
{
    'name': "Real Estate Report",
    'summary': """
        Statement Of Account, Files Labels, Payment/Confirmation Customer Receipt
        and Duplicate Membership Form PDF reports for a real estate file.""",
    'description': """
        Statement Of Account, Files Labels, Payment/Confirmation Customer Receipt
        and Duplicate Membership Form PDF reports for a real estate file.
    """,
    'author': "Axiom World",
    'category': 'Real Estate',
    'version': '19.0.1.0.0',
    'license': 'OEEL-1',
    'depends': ['real_estate'],
    'data': [
        'report/statement_of_account_header.xml',
        'report/statement_of_account_report.xml',
        'report/files_label_report.xml',
        'report/file_receipt_report_templates.xml',
        'report/file_receipt_report.xml',
        'report/duplicate_membership_form.xml',
    ],
}
