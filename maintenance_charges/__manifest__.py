# -*- coding: utf-8 -*-
{
    'name': "Maintenance Charges",

    'summary': """
        This module manages the maintenance charges of society.""",


    'author': "Syed Hamza || Axiom World",
    'website': "http://www.axiomworld.net",

    'category': 'Real Estate',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': [
        'real_estate',
        # 'axiom_payment_report',  # not available in Odoo 19 project (only exists in the old Odoo 13 source tree)
    ],

    # always loaded
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'security/multi_company_rules.xml',
        'data/ir_cron.xml',
        'data/ir_sequence.xml',
        'views/maintenance_charges.xml',
        'views/maintenance_charges_type.xml',
        'views/file_ext.xml',
        'views/maintenance_charges_payment.xml',
        'views/change_unit_type.xml',
        'views/res_users.xml',
        'views/account_move_ext.xml',
        'wizard/assign_agent.xml',
    ],

    # 'test': ['static/html/index.html'],
    # commented out: static/html/index.html does not exist anywhere in this module
    # (it was never present in this addons tree), so referencing it here is dead weight.
}
