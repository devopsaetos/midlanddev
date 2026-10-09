{
    'name': "Maintenance Inquiry",
    'license': 'LGPL-3',

    'summary': 'Maintenance Inquiry ',

    'description': """
        This module would be used to generate the Maintenance Inquiry
    """,

    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'website': "https://www.aetostechnology.com",

    'category': 'Real Estate',
    'version': '19.0.1.0.10',

    # any module necessary for this one to work correctly
    'depends': ['file_financials', 'maintenance_charges', 'maintenance_monthly_bill'],

    # always loaded
    'data': [
             'security/ir.model.access.csv',
             'wizard/maintenance_statement_inquiry_wizard.xml',
             'reports/report.xml',
             ],
}
