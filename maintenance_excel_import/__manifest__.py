# -*- coding: utf-8 -*-
{
    'name': "Maintenance Excel Import",
    'website': "https://www.aetostechnology.com",
    'summary': """
        Company-wise Excel template + import for Maintenance: houses (file, member, nominee,
        plot, meter) and their utility / electricity bill history.""",
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'category': 'Real Estate',
    'version': '19.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['maintenance_monthly_bill'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/ir.model.access.csv',
        'wizard/maintenance_excel_import.xml',
    ],
}
