# -*- coding: utf-8 -*-
{
    'name': "Real Estate Files Financials",

    'summary': """
        Real Estate Files Financials Management System.""",

    'description': """
        This module is developed to manage financials changes of Files.
    """,

    'author': "Siddiq Chauhdry",
    'website': "https://www.siddiqchauhdry.com",
    'category': 'Real Estate',
    'version': '19.0.1.0.3',

    'depends': [
        'crm',
        'allotment',
        'unit_booking',
        'default_payment',
        'land_development',
    ],

    'data': [
        'views/owner_mobile.xml',
        'views/res_company.xml',
        'views/res_config_setting.xml',
        'views/predefine_plan.xml',
        'views/account_move_ext.xml',
        'views/account_payment.xml',
        'views/investor_file.xml',
        'views/file.xml',
        'views/file_verification.xml',
        'views/payment_verification.xml',
        'views/dealer_rebate.xml',
        'views/investment.xml',
        'views/menuitems.xml',
        'views/investment_platter.xml',
        'views/investment_category.xml',
        'views/investment_lines.xml',
        'views/investment_plan.xml',
        'views/printing_queue.xml',
        'views/print_documents.xml',
        'views/unit_swapping_request.xml',
        'views/investment_rebate_request.xml',
        'views/sub_dealer_inventory_management.xml',
        'views/plot_merger_application_view.xml',
        'views/plot_merger_view.xml',
        'views/plot_inventory.xml',
        # Wizards
        'wizards/document_printing_wizard.xml',
        'wizards/investment_rebate_wizard.xml',
        'wizards/file_confirmation_adjustment_wizard.xml',
        'wizards/unit_swapping_wizard.xml',
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/ir_cron.xml',
        'data/ir_sequence_data.xml',
        'data/record_rules.xml',
        'data/mail_templates.xml',
        'data/product_data.xml',

    ],
}
