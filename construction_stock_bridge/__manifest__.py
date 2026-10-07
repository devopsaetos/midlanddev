{
    'name': 'Construction Stock Bridge',
    'website': "https://www.aetostechnology.com",
    'version': '19.0.1.0.1',
    'category': 'Construction',
    'summary': 'Links Issue Requisitions and Stock Transactions to construction projects, tasks, and cost sheets',
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'license': 'LGPL-3',
    'depends': [
        'supply_chain_customizations',
        'construction_costing',
    ],
    'data': [
        'views/project_task.xml',
        'views/issue_requisition.xml',
        'views/stock_transaction.xml',
    ],
    'installable': True,
    'application': False,
}
