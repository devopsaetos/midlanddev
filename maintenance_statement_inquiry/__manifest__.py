{
    'name': "Maintenance Inquiry",

    'summary': 'Maintenance Inquiry ',

    'description': """
        This module would be used to generate the Maintenance Inquiry
    """,

    'author': "Siddiq Chauhdry",
    'website': 'https://siddiqchauhdry.com',

    'category': 'Real Estate',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['file_financials', 'maintenance_charges'],

    # always loaded
    'data': [
             'security/ir.model.access.csv',
             'wizard/maintenance_statement_inquiry_wizard.xml',
             'reports/report.xml',
             ],
}
