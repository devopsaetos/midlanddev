# -*- coding: utf-8 -*-
{
    'name': "Supply Chain Customizations",
    'summary': """To customize supply chain""",
    'description': """To customize supply chain""",
    'author': "Hassan Raza",
    'version': '19.0.0.0.2',
    'depends': ['purchase', 'maintenance'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/account_cost_center.xml',
        'views/stock_move_ext.xml',
        'views/stock_transaction.xml',
        'views/charge_type.xml',
        'views/price_list_history.xml',
        'views/issue_requisition.xml',
        'views/maintenance_request_ext.xml',
        'wizards/stock_warn_insufficient_qty_views.xml',
    ],
    'license': 'LGPL-3',
}
