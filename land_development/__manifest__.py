# -*- coding: utf-8 -*-
{
    'name': "Land Development",

    'summary': """
        This module is for Building and Real-Estate Management System""",

    'description': """
        A rapper on Real Estate for adding Building with Real-Estate Management
    """,

    'author': "Wahab Ali Malik || Syed Hamza || Axiom Team",
    'website': "http://www.axm.app",
    'category': 'Real Estate',
    'version': '19.0.1.0.0',
    'license': 'OEEL-1',

    'depends': ['real_estate'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/actions.xml',
        'views/menuitems.xml',
        'views/members.xml',
        'views/building.xml',
        'views/demarcated_area.xml',
        'views/unit_inventory.xml',
        'views/change_installment_plan.xml',
        'views/file_search.xml',
        'views/predefine_plan.xml',
        'views/payment_interval.xml',
        'views/create_inventory.xml',
        'views/file_cancellation_application.xml',
        'views/file_merger_application.xml',
        'views/file_refund.xml',
        'views/file_transfer_request.xml',
        'views/file_transfer_application.xml',
        'views/floor.xml',
        'views/file.xml',
        'views/price_list.xml',
        'views/unit_category.xml',
        'views/unit_size.xml',
        'views/unit_category_type.xml',
        'views/unit_class.xml',
        'views/location.xml',
        'views/res_authority.xml',
        'views/create_invoice_file.xml',
        'views/advance_payments_file.xml',
        'views/investment.xml',
        'views/investors.xml',
        'views/investor_file.xml',
        # 'views/token_money.xml',
        'views/legal_dispute.xml',
        'views/investor_payment.xml',
        'views/unit_swapping.xml',
        'views/unit_swapping_request.xml',
        'views/file_charges_schedule.xml',
        'views/installment_invoice_wizard.xml',
        'wizard/unit_import_wizard.xml',
        # 'views/templates.xml',
        # 'views/crm_lead_ext.xml'
    ],

    'assets': {
        'web.assets_backend': [
            'land_development/static/src/css/payment_coloumn.scss',
        ],
    },

}