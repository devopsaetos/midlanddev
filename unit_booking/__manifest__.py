# -*- coding: utf-8 -*-
{
    'name': "Unit Booking",

    'summary': """
        This module generate bookings for plots/units.""",

    'author': "Syed Hamza ||Mudassir Ali Zaidi|| Axiom World",
    'website': "http://www.axiomworld.net",
    'category': 'Real Estate',
    'version': '19.0.1.0.1',

    # any module necessary for this one to work correctly
    'depends': ['real_estate', 'account_asset'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/groups.xml',
        'security/multi_company_rules.xml',
        'data/ir_sequence_data.xml',
        'data/product_data.xml',
        'data/ir_cron.xml',
        # -----------------
        # Views
        # -----------------
        'views/menuitems.xml',
        'views/unit_booking_allotment.xml',
        'views/units_booking.xml',
        'views/unit_batch.xml',
        'views/agent.xml',
        'views/deal_pack.xml',
        'views/open_file_assignment.xml',
        'views/unit_booking_issuance.xml',
        'views/unit_view.xml',
        'views/account_invoice_ext.xml',
        'views/file_ext.xml',
        'views/unit_swap_request.xml',
        'views/dealer_category.xml',
        'views/unit_booking_cancellation.xml',
        'views/open_file_issuance_request.xml',
        'views/res_config_setting.xml',
        'views/dealer_rebate.xml',
        'views/asset_allocation.xml',
        'views/account_asset_asset_ext.xml',
        'views/dealer_renewal_req.xml',
        'views/buy_back_open_file.xml',
        'views/dealer_cancellation_req.xml',
        'views/open_file_installment_plan.xml',
        'views/open_file_duplicate.xml',
        'views/file_transfer_application_ext.xml',
        'views/booking_verification.xml',
        'views/issuance_request_verification.xml',
        'views/units_platter.xml',
        # --------------------
        # Wizards
        # --------------------
        'wizard/open_file_qr_reading.xml',
        'wizard/unit_booking_search.xml',
        'wizard/file_assignment_undo.xml',
        'wizard/reset_installment_plan.xml',
        'wizard/search_dealer.xml',
        'wizard/buy_back_file_qr_scanning.xml',
        'wizard/dealer_rebate_search.xml',
        'wizard/unit_booking_reset_print_state.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'unit_booking/static/src/js/qr_code_reader.js',
        ],
    },
}
