# -*- coding: utf-8 -*-
{
    'name': "Allotment",

    'summary': """
       This module make the allotment""",

    'description': """
        This module make the allotment request and further processing till the ending date
    """,

    'author': "Umer Farooq||By Axiom World Team",
    'website': "http://www.axiomworld.net",

    'category': 'real_estate',
    'version': '19.0.1.0.0',
    'depends': ['real_estate'],

    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/file.xml',
        'views/printing_queue.xml',
        'views/printing_history.xml',
        'views/allotment_batch.xml',
        'wizard/allotment.xml',
        'views/document_issuance.xml',
        'views/file_allotment_application.xml'
    ],
}
