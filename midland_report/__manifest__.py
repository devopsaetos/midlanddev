{
    'name': 'Midland Membership Form Report',
    'version': '19.0.1.0.0',
    'summary': 'Membership Form & Installment Plan PDF report for Real Estate Files',
    'description': """
Adds a "Print Report" button on the File form (Real Estate) which generates
a combined PDF report containing:
    1. Membership Form  - Owner Details, Next of Kin, Unit Details, Contract Detail
    2. Installment Plan - Full payment schedule table
""",
    'category': 'Real Estate',
    'author': 'Midland Dev',
    'depends': ['real_estate', 'midland_invoicing'],
    'data': [
        'security/ir.model.access.csv',
        'report/midland_membership_report_actions.xml',
        'report/midland_membership_report_template.xml',
        'views/file_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'midland_report/static/src/js/file_print_button.js',
            'midland_report/static/src/xml/file_print_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
