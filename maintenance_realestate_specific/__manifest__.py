# -*- coding: utf-8 -*-
{
    'name': "maintenance_realestate_specific",

    'summary': """
        Maintenance For Real Estate""",

    'description': """
        This module is build to deal with the maintenance issue is related to Real Estate
    """,

    'author': "Mudassar Ali Syed|| Axiom Team",
    'website': "https://www.axm.app",
    'category': 'Help Desk',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    # Odoo 19 migration note: 'website_axis_helpdesk' (an old Odoo 13/17 third-party
    # module) does not exist anywhere in this project's addons path, so it cannot be
    # depended on. This module has been rewired to depend on and extend Odoo 19
    # Enterprise's own core 'helpdesk' app instead (module 'helpdesk', which defines
    # 'helpdesk.ticket'/'helpdesk.team'/'helpdesk.stage'). Views/fields that relied on
    # concepts unique to website_axis_helpdesk (e.g. 'helpdesk.ticket.type', the
    # self-assign button/flag, the project 'create_task' bridge) have no equivalent in
    # core helpdesk and are commented out in place with notes rather than deleted.
    # 'maintenance' was added explicitly because this module inherits 'maintenance.request'
    # and now also 'maintenance.team' directly - previously this dependency was only
    # satisfied implicitly via website_axis_helpdesk's own manifest.
    'depends': [
        # 'website_axis_helpdesk',  # not available in this Odoo 19 project - replaced by core 'helpdesk' below
        'helpdesk',
        'maintenance',
        'maintenance_recovery_batch',
    ],

    # always loaded
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'security/maintenance_security.xml',
        'views/helpdesk_ticket.xml',
        'views/maintenance_request.xml',
        'views/maintenance_exemption.xml',
        'views/maintenance_exemption_withdrawal.xml',
        'views/file_ext.xml',
        'wizard/search_record.xml'
    ],
}
