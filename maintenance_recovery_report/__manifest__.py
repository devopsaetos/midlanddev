# -*- coding: utf-8 -*-
{
    'name': "Maintenance Recovery Report",
    'summary': """
        Generate Maintenance Recovery Report based on various filters.""",
    'description': """
       Generate Maintenance Recovery Report based on various filters""",

    'author': "Muhammad Hamza Faizan | Data Elite",
    'website': "dateelite.tech",
    'category': 'Account',
    'version': '19.0.1.0.0',
    'depends': [
        'base', 'account',
        # 'axiom_recovery_report',  # Odoo 19: not available anywhere in this project (only
        #                           exists in the old Odoo 13 source tree at
        #                           ~/programming/odoo/13/ncp_odoo/extra/axiom_recovery_report);
        #                           commented out, not deleted, per migration policy.
        # 'ks_custom_report',       # Odoo 19: Ksolves commercial module not part of this
        #                           project's addons path (exists only in unrelated other-client
        #                           projects); commented out, not deleted, per migration policy.
        # Odoo 19: this module's report.py/wizard use the `file` model plus `society`, `sector`,
        # `plot.category`, `unit.category.type` (all real_estate) and `file.maintenance_history_ids`
        # / `file.maintenance_recovery_agent_id` (added by maintenance_charges) - none of which
        # were declared here because axiom_recovery_report (itself depending on 'real_estate' in
        # its old v13 form) pulled them in transitively. With that dependency gone, depending on
        # maintenance_charges directly (which in turn depends on real_estate) is required for the
        # module to actually load - same fix pattern used in the sibling maintenance_collection_report/
        # maintenance_invoice_report/maintenance_recovery_batch modules converted in this batch.
        'maintenance_charges',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/report.xml',
        'report/maintenance_recovery_report.xml',
        'wizard/maintenance_recovery_report_wizard.xml',
    ]
}
