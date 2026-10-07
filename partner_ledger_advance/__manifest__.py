# -*- coding: utf-8 -*-
{
    'name': 'Advance Payments in Partner Reports',
    'website': "https://www.aetostechnology.com",
    'summary': 'Partner Ledger and Aged Receivable/Payable include advance payments booked on '
               'advance accounts (e.g. Advance to Suppliers), in the opening balance and the lines.',
    'description': """
Advance payments (default_payment) are posted on a separate advance account, which is not a
receivable/payable account, so the partner reports never saw them. Accounts flagged as
supplier / customer advance accounts are now read together with the payable / receivable
accounts by the Partner Ledger (opening balance, lines, closing balance) and the Aged
Payable / Aged Receivable reports.

The Partner Ledger also shows an Opening Balance column and a Closing Balance column per
partner, and frames each unfolded partner with Opening Balance and Closing Balance lines.
""",
    'author': "Hassan Raza, Mubeen Amanat, Ateeb Shahid Baig",
    'category': 'Accounting/Accounting',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'depends': ['default_payment', 'account_reports'],
    'data': [
        'views/account_account_views.xml',
    ],
    'post_init_hook': '_flag_existing_advance_accounts',
    'auto_install': True,
}
