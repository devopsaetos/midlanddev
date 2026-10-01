# -*- coding: utf-8 -*-
{
    'name': "Account Multi Payments",
    'version': '19.0.1.0.0',
    'summary': "Allows processing and managing multiple payments against customer/vendor invoices.",
    'description': """
This module enables users to process multiple invoice payments in one action.

Key Features:
- Pay multiple invoices from a single form.
- Handles partial and full payments.
- Automatically tracks payment differences.
- Supports customer and vendor bills.
""",
    'author': 'Aetos Technology',
    'maintainer': 'Aetos Technology',
    'website': 'https://www.aetostechnology.com',
    'category': 'Accounting',
    'license': 'OPL-1',
    # default_payment: it already defines the multi.invoice.payment model that this module
    # extends (and account.payment's multi_invoice_ids field on the same model) - without this
    # dependency, module load order between the two is undefined and the merged model's fields
    # (state, active, ...) aren't reliably set up yet when this module's views get validated.
    'depends': ['account', 'account_batch_payment', 'default_payment'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/account_payment.xml',
        'views/multi_invoice_payment.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
