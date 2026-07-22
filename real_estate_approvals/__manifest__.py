{
    'name': 'Real Estate — Approvals Bridge',
    'version': '19.0.1.0.0',
    'summary': 'Route res.investor state transitions through the Enterprise Approvals app',
    'description': """
Real Estate Approvals Bridge
============================
Connects the custom res.investor workflow with the Odoo Enterprise Approvals app.

* Adds a seeded 'Investor Registration' approval category.
* Rewires the 'In Process' button on the investor form to raise an approval request
  instead of directly moving the state forward.
* The 'Approve' button is guarded and becomes actionable only after the related
  approval request has been approved by the configured approvers.
* Adds an 'Approvals' tab on the investor form showing linked approval requests
  with their current status.
""",
    'author': 'DevFusion',
    'website': 'https://devfusion.tech',
    'category': 'Real Estate',
    'depends': [
        'real_estate',
        'approvals',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/approval_category_data.xml',
        'views/res_investor_view.xml',
        'views/menu.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
