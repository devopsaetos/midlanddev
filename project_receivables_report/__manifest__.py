# -*- coding: utf-8 -*-
{
    'name': "Project Receivables Report",
    'summary': "Month-wise member receivables report (Excel / PDF), one menu, project picked in the wizard.",
    'description': """
        Real Estate > Reports > Member (Receivables): the user picks the project
        and the "Till Month"; the report lists every member file of that project
        with its total, paid and due amounts, the selected month's installment,
        and the overdue amount from earlier months.
    """,
    'category': 'Sales/Real Estate',
    'version': '19.0.1.0.0',
    'depends': ['real_estate'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/project_receivables_wizard.xml',
        'report/project_receivables_report.xml',
        'data/receivables_menus.xml',
    ],
    'license': 'LGPL-3',
}
