{
    'name': 'Construction PO Bridge',
    'website': "https://www.aetostechnology.com",
    'version': '19.0.1.0.1',
    'category': 'Construction',
    'summary': 'Links Purchase Orders and Vendor Bills to construction tasks and cost sheets',
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'license': 'LGPL-3',
    'depends': [
        'construction_subcontracting',
        'purchase',
        'account',
    ],
    'data': [
        'views/purchase.xml',
        'views/account_move.xml',
        'views/project_task.xml',
    ],
    'installable': True,
    'application': False,
}
