from datetime import datetime, timedelta
from odoo.exceptions import UserError
from odoo import models, api, _


class MaintenanceCollectionReport(models.AbstractModel):
    _name = 'report.maintenance_collection_report.maintenance_report_custom'
    _description = 'Maintenance Collection Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))

        domain = [
            ('state', '=', 'posted'),
        ]
        if docs.sector_id:
            domain.append(('file_id.sector_id', 'in', docs.sector_id.ids))

        if docs.category_ids:
            domain.append(('file_id.category_id', 'in', docs.category_ids.ids))

        if docs.unit_category_type_ids:
            domain.append(('file_id.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))

        if docs.date_from:
            from_date = docs.date_from
            domain.append(('payment_date', '>=', from_date))

        if docs.date_to:
            to_date = docs.date_to
            domain.append(('payment_date', '<=', to_date))

        invoice_types = docs.invoice_type

        account_payments = self.env['account.payment'].search(domain)
        # account_payments = account_payments.filtered(
        #     lambda payment: any(
        #         invoice.invoice_id.property_invoice_type in ['maintenance_charges', 'society_charges']
        #         for invoice in payment.multi_invoice_ids
        #     )
        # )
        if invoice_types == 'maintenance_charges':
            print('Maintenance charges')
            account_payments = account_payments.filtered(
                lambda payment: any(
                    invoice.invoice_id.property_invoice_type == 'maintenance_charges'
                    and any(line.product_id.id == 103 for line in invoice.invoice_id.invoice_line_ids)
                    for invoice in payment.multi_invoice_ids
                )
            )
        if invoice_types == 'society_charges':
            print('Society Charges')
            account_payments = account_payments.filtered(
                lambda payment: any(
                    invoice.invoice_id.property_invoice_type == 'society_charges'
                    and any(line.product_id.id == 103 for line in invoice.invoice_id.invoice_line_ids)
                    for invoice in payment.multi_invoice_ids
                )
            )
        if invoice_types != 'maintenance_charges' and invoice_types != 'society_charges':
            print('both')
            account_payments = account_payments.filtered(
                lambda payment: any(
                    invoice.invoice_id.property_invoice_type in ['maintenance_charges', 'society_charges']
                    and any(line.product_id.id == 103 for line in invoice.invoice_id.invoice_line_ids)
                    for invoice in payment.multi_invoice_ids
                )
            )

        print(len(account_payments))
        unique_sectors = None
        unique_product = None
        unit_category_product = None
        sector_from_wizard = None
        if not docs.sector_id:
            unique_sectors = list(set(payment.file_id.sector_id for payment in account_payments if payment.file_id.sector_id))
            unique_product = sorted(unique_sectors, key=lambda x: x['name'])
        if not docs.unit_category_type_ids:
            unique_product = list(
                set(payment.file_id.unit_category_type_id for payment in account_payments if
                    payment.file_id.unit_category_type_id))
            unique_product = sorted(unique_product, key=lambda x: x['name'])
        else:
            unit_category_product = sorted(docs.unit_category_type_ids, key=lambda x: x.name)

        months_list = []
        current_date = docs.date_from
        while current_date <= docs.date_to:
            months_list.append(current_date.strftime('%b %Y'))
            next_month = current_date.replace(day=1) + timedelta(days=32)
            current_date = next_month.replace(day=1)
        report_data = {
            'account_payment': account_payments,
            'docs': docs,
            'category_ids': docs.category_ids,
            'sectors_from_payments': unique_sectors,
            'unit_category_type_ids': docs.unit_category_type_ids,
            'sector_id': docs.sector_id,
            'date_from': docs.date_from,
            'date_to': docs.date_to,
            'months_list': months_list,
            'unique_product': unique_product,
            'unit_category_product': unit_category_product,
        }
        return report_data

# OLD CODE
#     @api.model
#     def _get_report_values(self, docids, data=None):
#         model = self.env.context.get('active_model')
#         docs = self.env[model].browse(self.env.context.get('active_id'))
#
#         domain = [
#             ('state', '=', 'posted'),
#         ]
#         if docs.sector_id:
#             domain.append(('file_id.sector_id', 'in', docs.sector_id.ids))
#
#         if docs.category_ids:
#             domain.append(('file_id.category_id', 'in', docs.category_ids.ids))
#
#         if docs.unit_category_type_ids:
#             domain.append(('file_id.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
#
#         if docs.date_from:
#             from_date = docs.date_from
#             domain.append(('payment_date', '>=', from_date))
#
#         if docs.date_to:
#             to_date = docs.date_to
#             domain.append(('payment_date', '<=', to_date))
#
#         account_payments = self.env['account.payment'].search(domain)
#         account_payments = account_payments.filtered(
#             lambda payment: any(
#                 invoice.invoice_id.property_invoice_type in ['maintenance_charges', 'society_charges']
#                 for invoice in payment.multi_invoice_ids
#             )
#         )
#         print(len(account_payments))
#         unique_sectors = None
#         if not docs.sector_id:
#             unique_sectors = list(set(payment.file_id.sector_id for payment in account_payments if payment.file_id.sector_id))
#         months_list = []
#         current_date = docs.date_from
#         while current_date <= docs.date_to:
#             months_list.append(current_date.strftime('%b %Y'))
#             next_month = current_date.replace(day=1) + timedelta(days=32)
#             current_date = next_month.replace(day=1)
#         print(docs.sector_id)
#         report_data = {
#             'account_payment': account_payments,
#             'docs': docs,
#             'category_ids': docs.category_ids,
#             'sectors_from_payments': unique_sectors,
#             'unit_category_type_ids': docs.unit_category_type_ids,
#             'sector_id': docs.sector_id,
#             'date_from': docs.date_from,
#             'date_to': docs.date_to,
#             'months_list': months_list,
#         }
#         return report_data


# New Changes Code

# @api.model
# def _get_report_values(self, docids, data=None):
#     model = self.env.context.get('active_model')
#     docs = self.env[model].browse(self.env.context.get('active_id'))
#
#     domain = [
#         ('state', '=', 'posted'),
#     ]
#     if docs.sector_id:
#         domain.append(('file_id.sector_id', 'in', docs.sector_id.ids))
#
#     if docs.category_ids:
#         domain.append(('file_id.category_id', 'in', docs.category_ids.ids))
#
#     if docs.unit_category_type_ids:
#         domain.append(('file_id.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
#
#     if docs.date_from:
#         from_date = docs.date_from
#         domain.append(('payment_date', '>=', from_date))
#
#     if docs.date_to:
#         to_date = docs.date_to
#         domain.append(('payment_date', '<=', to_date))
#
#     account_payments = self.env['account.payment'].search(domain)
#     account_payments = account_payments.filtered(
#         lambda payment: any(
#             invoice.invoice_id.property_invoice_type in ['maintenance_charges', 'society_charges']
#             for invoice in payment.multi_invoice_ids
#         )
#     )
#
#     # Calculate sum of total amounts for each sector and month
#     sector_month_totals = {}
#     for payment in account_payments:
#         sector_name = payment.file_id.sector_id.name
#         month_key = payment.payment_date.strftime('%b %Y')
#         sector_month_totals.setdefault(sector_name, {}).setdefault(month_key, 0.0)
#         sector_month_totals[sector_name][month_key] += payment.amount
#
#     unique_sectors = list(sector_month_totals.keys())
#     months_list = list(set(payment.payment_date.strftime('%b %Y') for payment in account_payments))
#     months_list.sort()
#
#     report_data = {
#         'account_payment': account_payments,
#         'docs': docs,
#         'category_ids': docs.category_ids,
#         'sectors_from_payments': unique_sectors,
#         'unit_category_type_ids': docs.unit_category_type_ids,
#         'sector_id': docs.sector_id,
#         'date_from': docs.date_from,
#         'date_to': docs.date_to,
#         'months_list': months_list,
#         'sector_month_totals': sector_month_totals,
#     }
#     return report_data
