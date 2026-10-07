{
    'name': 'Construction Requisition Bridge',
    'website': "https://www.aetostechnology.com",
    'version': '19.0.1.0.1',
    'category': 'Construction',
    'summary': 'Links Purchase Requisitions to construction projects, tasks, and cost sheets',
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'license': 'LGPL-3',
    'depends': [
        'purchase_requisitions',
        'construction_po_bridge',
    ],
    'data': [
        'views/project_task.xml',
        'views/material_purchase_requisitions.xml',
        'views/requisition_order.xml',
        'views/requisition_quotation.xml',
    ],
    'installable': True,
    'application': False,
}
