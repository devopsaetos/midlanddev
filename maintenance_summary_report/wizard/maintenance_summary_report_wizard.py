# -*- coding: utf-8 -*-
import base64
import datetime
from datetime import timedelta, datetime
from io import BytesIO
import pandas as pd
from odoo import models, fields, api, _


class MaintenanceSummaryReportWizard(models.TransientModel):
    _name = 'maintenance.summary.report.wizard'
    _description = 'Maintenance Summary Report Wizard'

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date")
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    unit_class_id = fields.Many2one('unit.class', string="Type")
    maintenance_summary_xl_report = fields.Binary('Maintenance Summary Report Excel File')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def generate_report(self):
        # Odoo 19: account_move.type was renamed to move_type (fixed below, 2 occurrences).
        sql_query = f"""
            WITH previous_arrears AS (
                SELECT 
                    am.partner_id AS customer_id,
                    SUM(CASE 
                            WHEN am.date < '{str(self.start_date)}' AND am.date >= '2023-11-01' THEN am.amount_residual_signed
                            ELSE 0
                        END) AS arrears
                FROM 
                    account_move am
                JOIN 
                    account_move_line aml ON am.id = aml.move_id
                WHERE
                    am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.date >= '2023-11-01'
                    AND am.date < '{str(self.start_date)}'
                    AND aml.product_id = {str(self.product_id.id)}
                    AND am.property_invoice_type IN ('maintenance_charges', 'society_charges')
                    AND am.company_id = {self.env.company.id}
                GROUP BY 
                    am.partner_id
            )
            SELECT 
                INITCAP(customer.name) AS Customer,
                INITCAP(sector.name) AS Sector,
                INITCAP(street.name) AS StreetNo,
                INITCAP(inventory.name) AS HouseNo,
                INITCAP(category.name) AS Category,
                INITCAP(product.name) AS Product,
                INITCAP(size.name) AS Size,
                INITCAP(class.name) AS Type,
                CASE 
                    WHEN am.property_invoice_type = 'maintenance_charges' THEN 'Maintenance'
                    WHEN am.property_invoice_type = 'society_charges' THEN 'Electricity'
                    ELSE INITCAP(am.property_invoice_type)
                END AS InvoiceType,
                TO_CHAR(SUM(am.amount_total)::numeric, '999,999,999') AS TotalAmount,
                TO_CHAR(SUM(am.amount_total - am.amount_residual_signed)::numeric, '999,999,999') AS PaidAmount,
                TO_CHAR(SUM(am.amount_residual_signed)::numeric, '999,999,999') AS DueAmount,
                TO_CHAR(pa.arrears, '999,999,999') AS Arrears
            FROM 
                account_move am
            JOIN 
                account_move_line aml ON am.id = aml.move_id
            LEFT JOIN 
                file f ON f.id = am.file_ids
            LEFT JOIN 
                plot_inventory inventory ON inventory.id = f.inventory_id
            LEFT JOIN 
                sector sector ON sector.id = inventory.sector_id
            LEFT JOIN 
                res_partner customer ON customer.id = am.partner_id
            LEFT JOIN 
                street street ON street.id = inventory.street_id
            LEFT JOIN 
                plot_category category ON category.id = f.category_id
            LEFT JOIN 
                unit_category_type product ON product.id = f.unit_category_type_id
            LEFT JOIN 
                unit_size size ON size.id = f.size_id
            LEFT JOIN 
                unit_class class ON class.id = f.unit_class_id
            LEFT JOIN 
                previous_arrears pa ON pa.customer_id = customer.id
            WHERE
                am.move_type = 'out_invoice'
                AND am.state = 'posted'
                {"AND am.date >= '" + str(self.start_date) + "'" if self.start_date else ""}
                {"AND am.date <= '" + str(self.end_date) + "'" if self.end_date else ""}
                {"AND aml.product_id = " + str(self.product_id.id) if self.product_id else ""}
                {"AND class.id = " + str(self.unit_class_id.id) if self.unit_class_id else ""}
                AND am.company_id = {self.env.company.id}
                AND am.property_invoice_type IN ('maintenance_charges', 'society_charges')
            GROUP BY 
                customer.name, sector.name, street.name, inventory.name, category.name, product.name, size.name, class.name, am.property_invoice_type, am.company_id, am.partner_id, am.amount_residual_signed, pa.arrears
            ORDER BY 
                sector.name, street.name, inventory.name ASC;
            """

        # Execute the SQL query
        self._cr.execute(sql_query)
        data = self._cr.dictfetchall()

        # Convert the result to a DataFrame
        df = pd.DataFrame(data)
        # Capitalize column headings
        df.columns = map(str.capitalize, df.columns)
        # Export DataFrame to Excel
        # Create a BytesIO buffer to save the Excel file
        excel_buffer = BytesIO()
        # Use pandas to save the DataFrame to the buffer as an Excel file with proper column widths
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
            # Set column widths
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                col_idx = df.columns.get_loc(column)
                writer.sheets['Sheet1'].set_column(col_idx, col_idx, column_width)
        # Get the bytes data from the buffer
        excel_bytes = excel_buffer.getvalue()
        # Encode the bytes data using base64
        excel_base64 = base64.b64encode(excel_bytes)
        # Convert the base64 data to a string
        excel_base64_str = excel_base64.decode('utf-8')
        # Close the buffer
        excel_buffer.close()
        # Save the base64-encoded Excel data to the desired field in your model
        self.maintenance_summary_xl_report = excel_base64_str
        file_name = f'Maintenance Summary - [{datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")}].xlsx'

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=maintenance.summary.report.wizard&field=maintenance_summary_xl_report&download=true&id=%s&filename=%s' % (
                self.id, file_name),
        }
