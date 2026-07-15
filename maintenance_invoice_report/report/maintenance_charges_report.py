from odoo import fields, models, api, tools, _
from odoo.exceptions import ValidationError
from datetime import datetime


# class MaintenanceChargesReportModel(models.AbstractModel):
#     _name = 'report.maintenance_invoice_report.maintenance_charges_report'
#     _description = 'Maintenance Charges Invoice Report'
#
#     @api.model
#     def _get_report_values(self, docids, data=None):
#         model = self.env.context.get('active_model')
#         docs = self.env[model].browse(self.env.context.get('active_id'))
#
#         domain = [
#             ('state', '=', 'posted'),
#             ('property_invoice_type', '=', 'maintenance_charges'),
#             ('invoice_line_ids.product_id.id', '=', 103)
#         ]
#
#         society_domain = [
#             ('state', '=', 'posted'),
#             ('property_invoice_type', '=', 'society_charges'),
#             ('invoice_line_ids.product_id.name', '=', 'Service Charges'),
#             ('file_ids.service_charge', '=', True)
#         ]
#
#         if docs.society_id:
#             domain.append(('file_ids.society_id', '=', docs.society_id.id))
#             society_domain.append(('file_ids.society_id', '=', docs.society_id.id))
#
#         if docs.phase_id:
#             domain.append(('file_ids.phase_id', '=', docs.phase_id.id))
#             society_domain.append(('file_ids.phase_id', '=', docs.phase_id.id))
#
#         if docs.sector_id:
#             domain.append(('file_ids.sector_id', '=', docs.sector_id.id))
#             society_domain.append(('file_ids.sector_id', '=', docs.sector_id.id))
#
#         if docs.street_id:
#             domain.append(('file_ids.street_id', 'in', docs.street_id.ids))
#             society_domain.append(('file_ids.street_id', 'in', docs.street_id.ids))
#
#         if docs.category_ids:
#             domain.append(('file_ids.category_id', 'in', docs.category_ids.ids))
#             society_domain.append(('file_ids.category_id', 'in', docs.category_ids.ids))
#
#         if docs.unit_category_type_ids:
#             domain.append(('file_ids.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
#             society_domain.append(('file_ids.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
#
#         if docs.from_date:
#             domain.append(('invoice_date', '>=', docs.from_date))
#             society_domain.append(('invoice_date', '>=', docs.from_date))
#
#         if docs.to_date:
#             domain.append(('invoice_date', '<=', docs.to_date))
#             society_domain.append(('invoice_date', '<=', docs.to_date))
#
#         set_date = '2023-11-01'
#         records = self.env['account.move'].search(domain)
#         society_invoice = self.env['account.move'].search(society_domain)
#         invoice_month_dict = {record.id: record.invoice_date.strftime('%B %Y') for record in records}
#         society_invoice_month_dict = {record.id: record.invoice_date.strftime('%B %Y') for record in society_invoice}
#         total_arrears_maintenance = {}
#         for member in records.mapped('partner_id'):
#             total_arrears_maintenance[member.id] = {}
#             for file_id in records.filtered(lambda r: r.partner_id == member).mapped('file_ids'):
#                 account_moves_previous = self.env['account.move'].search([
#                     ('invoice_payment_state', '=', 'not_paid'),
#                     ('state', '=', 'posted'),
#                     ('property_invoice_type', '=', 'maintenance_charges'),
#                     ('partner_id', '=', member.id),
#                     ('file_ids', '=', file_id.id),
#                     ('invoice_date', '>=', set_date),
#                     ('invoice_date', '<', max(record.invoice_date for record in records)),
#                 ])
#                 total_arrears_maintenance[member.id][file_id.id] = sum(
#                     x.amount_residual_signed for x in account_moves_previous)
#
#         # Calculate total arrears for society charges
#         total_arrears_society = {}
#         for member in society_invoice.mapped('partner_id'):
#             total_arrears_society[member.id] = {}
#             for file_id in society_invoice.filtered(lambda r: r.partner_id == member).mapped('file_ids'):
#                 account_moves_previous = self.env['account.move'].search([
#                     ('invoice_payment_state', '=', 'not_paid'),
#                     ('property_invoice_type', '=', 'society_charges'),
#                     ('state', '=', 'posted'),
#                     ('partner_id', '=', member.id),
#                     ('file_ids', '=', file_id.id),
#                     ('invoice_date', '>=', '2024-03-01'),
#                     ('invoice_date', '<', max(record.invoice_date for record in society_invoice)),
#                 ])
#                 total_arrears_society[member.id][file_id.id] = sum(
#                     x.amount_residual_signed for x in account_moves_previous)
#
#         return {
#             'data': records,
#             'society_invoice': society_invoice,
#             'society_invoice_month_dict': society_invoice_month_dict,
#             'invoice_month_dict': invoice_month_dict,
#             'docs': docs,
#             'total_arrears_maintenance': total_arrears_maintenance,
#             'total_arrears_society': total_arrears_society,
#         }


class MaintenanceChargesReportModel(models.AbstractModel):
    _name = 'report.maintenance_invoice_report.maintenance_charges_report'
    _description = 'Maintenance Charges Invoice Report'

    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))

        domain = [
            ('state', '=', 'posted'),
            ('property_invoice_type', '=', 'maintenance_charges'),
            ('invoice_line_ids.product_id.id', '=', 103),
            ('payment_state', '!=', 'paid')  # Exclude paid invoices
        ]

        # society_domain = [
        #     ('state', '=', 'posted'),
        #     ('property_invoice_type', '=', 'society_charges'),
        #     ('invoice_line_ids.product_id.name', '=', 'Service Charges'),
        #     ('file_ids.service_charge', '=', True),
        #     ('invoice_payment_state', '!=', 'paid')  # Exclude paid invoices
        # ]

        if docs.society_id:
            domain.append(('file_ids.society_id', '=', docs.society_id.id))
            # society_domain.append(('file_ids.society_id', '=', docs.society_id.id))

        if docs.phase_id:
            domain.append(('file_ids.phase_id', '=', docs.phase_id.id))
            # society_domain.append(('file_ids.phase_id', '=', docs.phase_id.id))

        if docs.sector_id:
            domain.append(('file_ids.sector_id', '=', docs.sector_id.id))
            # society_domain.append(('file_ids.sector_id', '=', docs.sector_id.id))

        if docs.street_id:
            domain.append(('file_ids.street_id', 'in', docs.street_id.ids))
            # society_domain.append(('file_ids.street_id', 'in', docs.street_id.ids))

        if docs.category_ids:
            domain.append(('file_ids.category_id', 'in', docs.category_ids.ids))
            # society_domain.append(('file_ids.category_id', 'in', docs.category_ids.ids))

        if docs.unit_category_type_ids:
            domain.append(('file_ids.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))
            # society_domain.append(('file_ids.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))

        if docs.inventory_ids:
            domain.append(('file_ids.inventory_id', 'in', docs.inventory_ids.ids))
            # society_domain.append(('file_ids.unit_category_type_id', 'in', docs.unit_category_type_ids.ids))

        if docs.from_date:
            domain.append(('invoice_date', '>=', docs.from_date))
            # society_domain.append(('invoice_date', '>=', docs.from_date))

        if docs.to_date:
            domain.append(('invoice_date', '<=', docs.to_date))
            # society_domain.append(('invoice_date', '<=', docs.to_date))

        set_date = '2023-11-01'
        records = self.env['account.move'].search(domain)
        # society_invoice = self.env['account.move'].search(society_domain)
        invoice_month_dict = {record.id: record.invoice_date.strftime('%B %Y') for record in records}
        # society_invoice_month_dict = {record.id: record.invoice_date.strftime('%B %Y') for record in society_invoice}
        total_arrears_maintenance = {}
        for member in records.mapped('partner_id'):
            total_arrears_maintenance[member.id] = {}
            for file_id in records.filtered(lambda r: r.partner_id == member).mapped('file_ids'):
                account_moves_previous = self.env['account.move'].search([
                    ('payment_state', '=', 'not_paid'),
                    ('state', '=', 'posted'),
                    ('property_invoice_type', '=', 'maintenance_charges'),
                    ('partner_id', '=', member.id),
                    ('file_ids', '=', file_id.id),
                    ('invoice_date', '>=', set_date),
                    ('invoice_date', '<', max(record.invoice_date for record in records)),
                    ('payment_state', '!=', 'paid')  # Exclude paid invoices
                ])
                total_arrears_maintenance[member.id][file_id.id] = sum(
                    x.amount_residual_signed for x in account_moves_previous)

        # Calculate total arrears for society charges
        # total_arrears_society = {}
        # for member in society_invoice.mapped('partner_id'):
        #     total_arrears_society[member.id] = {}
        #     for file_id in society_invoice.filtered(lambda r: r.partner_id == member).mapped('file_ids'):
        #         account_moves_previous = self.env['account.move'].search([
        #             ('invoice_payment_state', '=', 'not_paid'),
        #             ('property_invoice_type', '=', 'society_charges'),
        #             ('state', '=', 'posted'),
        #             ('partner_id', '=', member.id),
        #             ('file_ids', '=', file_id.id),
        #             ('invoice_date', '>=', '2024-03-01'),
        #             ('invoice_date', '<', max(record.invoice_date for record in society_invoice)),
        #             ('invoice_payment_state', '!=', 'paid')  # Exclude paid invoices
        #         ])
        #         total_arrears_society[member.id][file_id.id] = sum(
        #             x.amount_residual_signed for x in account_moves_previous)

        return {
            'data': records,
            # 'society_invoice': society_invoice,
            # 'society_invoice_month_dict': society_invoice_month_dict,
            'invoice_month_dict': invoice_month_dict,
            'docs': docs,
            'total_arrears_maintenance': total_arrears_maintenance,
            # 'total_arrears_society': total_arrears_society,
        }
