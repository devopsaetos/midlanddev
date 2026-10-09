# -*- coding: utf-8 -*-
{
    'name': "Maintenance Monthly Bill",
    'website': "https://www.aetostechnology.com",
    'summary': """
        Monthly utility + electricity (meter reading) bills per file, posted as invoices
        and printed as a 3-copy bill (Customer / Society Office / Bank).""",
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'category': 'Real Estate',
    'version': '19.0.1.1.5',
    'license': 'LGPL-3',
    'depends': ['maintenance_charges', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'report/maintenance_bill_report.xml',
        'views/maintenance_bill.xml',
        'views/file.xml',
        'wizard/generate_bills.xml',
    ],
}
