from odoo import fields, models, api, tools, _
from odoo.exceptions import ValidationError
from datetime import datetime


class MaintenanceChargesInvoiceReportModel(models.AbstractModel):
    _name = 'report.maintenance_invoice_report.maintenance_invoice_report'
    _description = 'Global Invoice Report'

    @api.model
    def _get_report_values(self, docids, data):
        records = self.env['account.move'].browse(docids)
        invoice_month = records.invoice_date.strftime('%B %Y') if records.invoice_date else ''
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if current_month_start.month == 12:
            current_month_end = current_month_start.replace(year=current_month_start.year + 1, month=1)
        else:
            current_month_end = current_month_start.replace(month=current_month_start.month + 1)

        # Calculate the start date for August 2023
        nov_2023_start = datetime(2023, 11, 1)

        # Filter account moves for the current month
        account_moves_current_month = self.env['account.move'].search(
            [('payment_state', '=', 'not_paid'),
             ('partner_id', '=', records.partner_id.id),
             ('file_ids', '=', records.file_ids.id),
             ('date', '>=', current_month_start.strftime('%Y-%m-%d %H:%M:%S')),
             ('date', '<', current_month_end.strftime('%Y-%m-%d %H:%M:%S')),
             ('invoice_line_ids.product_id.name', '=', 'Maintenance Charges')]
        )
        account_moves_previous_months = self.env['account.move'].search(
            [('payment_state', '=', 'not_paid'),
             ('partner_id', '=', records.partner_id.id),
             ('file_ids', '=', records.file_ids.id),
             ('property_invoice_type', '=', 'maintenance_charges'),
             ('date', '>=', nov_2023_start.strftime('%Y-%m-%d %H:%M:%S')),
             ('date', '<', max(record.invoice_date for record in records))])
        total_amount_residual_signed = sum(x.amount_residual_signed for x in account_moves_previous_months)
        return {
            'data': data,
            'docs': records,
            'total_amount_residual_signed': total_amount_residual_signed,
            'invoice_month': invoice_month,
        }

    # @api.model
    # def _get_report_values(self, docids, data):
    #     records = self.env['account.move'].browse(docids)
    #     invoice_month = records.invoice_date.strftime('%B %Y') if records.invoice_date else ''
    #     current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    #     current_month_end = current_month_start.replace(month=current_month_start.month + 1)
    #     account_moves_current_month = self.env['account.move'].search(
    #         [('invoice_payment_state', '=', 'not_paid'),
    #          ('partner_id', '=', records.partner_id.id),
    #          ('date', '>=', current_month_start.strftime('%Y-%m-%d %H:%M:%S')),
    #          ('date', '<', current_month_end.strftime('%Y-%m-%d %H:%M:%S')),
    #          ('invoice_line_ids.product_id.name', '=', 'Maintenance Charges')]
    #     )
    #     account_moves_previous_months = self.env['account.move'].search(
    #         [('invoice_payment_state', '=', 'not_paid'),
    #          ('partner_id', '=', records.partner_id.id),
    #          ('property_invoice_type', '=', 'maintenance_charges'),
    #          ('date', '<', current_month_start.strftime('%Y-%m-%d %H:%M:%S'))]
    #     )
    #     total_amount_residual_signed = sum(x.amount_residual_signed for x in account_moves_previous_months)
    #     return {
    #         'data': data,
    #         'docs': records,
    #         'total_amount_residual_signed': total_amount_residual_signed,
    #         'invoice_month': invoice_month,
    #     }
