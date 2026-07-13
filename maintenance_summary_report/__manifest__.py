{
    'name': "Maintenance Summary Report",

    'summary': 'Maintenance Summary Report ',

    'description': """
        This module would be used to generate the Maintenance Summary Report in Excel
    """,

    'author': "Siddiq Chauhdry",
    'website': 'https://siddiqchauhdry.com',

    'category': 'Real Estate',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['file_financials', 'maintenance_collection_report'],

    # always loaded
    'data': [
             'security/ir.model.access.csv',
             'wizard/maintenance_summary_report_wizard.xml',
             'wizard/month_wise_report_wizard.xml',
             'wizard/maintenance_payment_summary_wizard.xml',
             # 'reports/report.xml' is kept disabled: it only contains a commented-out
             # legacy qweb-xlsx <report> shortcut tag (no longer valid Odoo 19 syntax, and
             # it never had a companion AbstractModel report class with generate_xlsx_report
             # needed to actually render qweb-xlsx reports). The excel output it was meant
             # to produce is already fully implemented by the wizards themselves
             # (generate_report / generate_xlsx_report methods build the .xlsx directly via
             # pandas/xlsxwriter and return an ir.actions.act_url download), so this file is
             # dead/superseded code kept only for reference. See reports/report.xml.
             # 'reports/report.xml',
             ],
}
