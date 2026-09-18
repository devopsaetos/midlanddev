# -*- coding: utf-8 -*-
{
    'name': "Dealers Statement Report",
    'summary': """
        Generate Dealer Statement Report based on various filters.""",
    'description': """
       Generate Dealer Statement Report based on various filters""",

    'author': "Muhammad Hamza Faizan | Data Elites",
    'website': "linkedin.com/in/muhammad-hamza-faizan/",
    'category': 'Sales/Real Estate',
    'version': '19.0.1.0.0',
    'depends': ['real_estate', 'file_financials', 'default_payment'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dealers_statement_report_wizard.xml',
        'report/report.xml',
        'report/dealers_statement_report_template.xml',
    ],
}
