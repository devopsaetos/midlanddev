# -*- coding: utf-8 -*-

{
    'name': 'Petty Cash Management | Petty Cash Request | Petty Cash Expense',
    'version': '19.0.1.6',
    'author': 'DevIntelle Consulting Service Pvt.Ltd, Ateeb Shahid Baig',
    'sequence': 1,
    'category': 'Accouting',
    'description':
        """

Petty cash management odoo app designed to simplify the management of petty cash transactions.
It allows users to create and handle petty cash requests, record expenses, and manage the
approval workflow. The module includes a dashboard for an overview of all petty cash activities,
enabling users to track and monitor transactions effectively. Additionally, it provides
reporting capabilities, allowing users to print petty cash requests and expenses as PDF reports.
The module integrates with Odoo's Employees, Invoicing, and Discuss modules, ensuring a cohesive
and efficient management process. Payments can be registered and reconciled within the module,
providing a complete solution for managing petty cash in an organization.

Overall, this app ensures efficient petty cash management, improved authorization workflows,
and enhanced integration with your existing Odoo modules, streamlining financial operations and
reducing manual errors.

Odoo Petty Cash Management
Efficient Petty Cash System
Petty Cash Handling in Odoo
Odoo Petty Cash Module
Streamlined Petty Cash Management
Petty Cash Workflow in Odoo
Odoo Petty Cash Control
Petty Cash Tracking and Reporting
Odoo Petty Cash Expenses
Petty Cash Reconciliation in Odoo
Odoo Petty Cash Fund Management
Petty Cash Handling Procedures
Odoo Petty Cash Register
Petty Cash Accountability in Odoo
Odoo Petty Cash Expense Management


odoo app allow Petty Cash Management, Petty Cash Request, Petty cash expense, Petty Cash Workflow approval process, Petty Cash Request balance, Petty Cash Expense Remaing Balance, Petty Cash due balance, Petty Cash user wise allocation, Cash flow Petty Cash management in odoo

    """,
    'summary': 'petty cash management petty cash request petty cash approval workflow petty cash expense manage petty cash expenses petty cash accounting petty cash finance petty cash request petty cash fund management day to day cash operation management auto petty cash funding auto petty cash fund management odoo petty cash operational expense management',
    'depends': ['account', 'hr'],
    'data': ['security/security.xml',
             'security/ir.model.access.csv',
             'views/petty_cash_request_views.xml',
             'data/ez_sequence.xml',
             'report/print_pettycash_template.xml',
             'report/print_pettycash_menu.xml',
             'report/print_pettycash_exp_template.xml',
             'views/petty_cash_kanban_views.xml',
             'views/petty_cash_expense_views.xml',
             'report/petty_cash_report_templates.xml',
             'wizard/petty_cash_report_views.xml'],
    'demo': [],
    'test': [],
    'assets': {
        'web.assets_backend': [
            'dev_petty_cash/static/src/dashboard/petty_cash_dashboard.js',
            'dev_petty_cash/static/src/dashboard/petty_cash_dashboard.xml',
            'dev_petty_cash/static/src/dashboard/petty_cash_dashboard.scss',
        ],
    },
    'images': ['images/main_screenshot.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',

}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
