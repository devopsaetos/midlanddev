# -*- coding: utf-8 -*-
{
    'name': "maintenance_ext",

    'summary': """
        Maintenance Extension""",

    'description': """
        This module is build to deal with the maintenance issue
    """,

    'author': "Hassan Raza|| Axiom Team",
    'website': "https://www.axm.app",
    'category': 'Help Desk',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    # Odoo 19 migration note: 'website_axis_helpdesk' (an old Odoo 13/17 third-party
    # module) does not exist anywhere in this project's addons path, so it cannot be
    # depended on. This module has been rewired to depend on and extend Odoo 19
    # Enterprise's own core 'helpdesk' app instead (module 'helpdesk', which defines
    # 'helpdesk.ticket'/'helpdesk.team'/'helpdesk.stage'). Views/fields that relied on
    # concepts unique to website_axis_helpdesk (e.g. the 'create_task'/project bridge
    # button, the old group/field layout) have no equivalent in core helpdesk and are
    # commented out in place with notes rather than deleted. See
    # maintenance_realestate_specific (converted earlier in this same migration batch)
    # for the precedent this follows.
    # 'maintenance' was added explicitly because this module inherits 'maintenance.request'
    # and references 'maintenance.stage_1/3/4' directly - previously this dependency was
    # only satisfied implicitly via website_axis_helpdesk's own manifest.
    #
    # 'issue_requistion' (a purchase-requisition/issue-tracking bridge module) does NOT
    # exist anywhere in this Odoo 19 project either - it only exists in an old Odoo 13
    # source tree. It is commented out below; every field/method in this module that
    # depended on its 'issue.requistion' model has been commented out in place too (see
    # models/issue_requistion.py, models/maintenance_request.py, views/issue_requistion.xml).
    # NOTE FOR PROJECT OWNER: a sibling module 'supply_chain_customizations' (already
    # present in this project, version 19.0.0.0.1) independently defines its own native
    # 'issue.requistion'/'issue.requistion.line' models (models/issue_requisition.py) and
    # its own 'maintenance.request.line' + material_requisition/on_issue_requisition bridge
    # on maintenance.request (models/maintenance_request_ext.py) - i.e. it appears to be a
    # from-scratch Odoo 19 reimplementation of what 'issue_requistion' used to provide, and
    # already depends on 'maintenance'. This module's commented-out issue-requisition
    # integration could potentially be restored against that model instead of core
    # 'issue_requistion' if desired, but re-pointing this module at it (and de-duplicating
    # the two now-independent 'maintenance.request.line' model definitions) was judged out
    # of scope for a like-for-like version migration and left for the project owner to
    # decide - see this module's final migration report.
    'depends': [
        # 'website_axis_helpdesk',  # not available in this Odoo 19 project - replaced by core 'helpdesk' below
        'helpdesk',
        'maintenance',
        # 'issue_requistion',  # not available in this Odoo 19 project - see note above; dependent code commented out in place
        'purchase_requisitions',
        # 'account_asset' added because models/tool_allocation.py's 'asset_id' field points
        # at 'account.asset' (renamed from the old 'account.asset.asset' - fixed during this
        # migration), which is only guaranteed registered if this module depends on it
        # directly (same pattern as sibling module 'unit_booking').
        'account_asset',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/tools_allocation.xml',
        # 'views/issue_requistion.xml',  # entirely dependent on the unavailable 'issue_requistion' module (inherits its 'issue.requistion' view) - content left in place/documented, just not loaded
        'views/maintenance_request.xml',
        'views/helpdesk_ticket.xml',
        'views/purchase_requisition.xml',
        'data/heldesk_data.xml'
    ],
}
