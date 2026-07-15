# -*- coding: utf-8 -*-
import base64
import datetime
from datetime import timedelta, datetime
from io import BytesIO
import pandas as pd
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class MonthWiseReportWizard(models.TransientModel):
    _name = 'month.wise.report.wizard'
    _description = 'Month Wise Report Wizard'

    society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('society_id','=',society_id)]")
    sector_ids = fields.Many2many('sector', string='Sector', domain="[('phase_id','=',phase_id)]")
    street_ids = fields.Many2many('street', string='Street', domain="[('sector_id', 'in', sector_ids)]")
    category_ids = fields.Many2many('plot.category', string='Category')
    unit_category_type_ids = fields.Many2many('unit.category.type', string="Product")
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    inventory_ids = fields.Many2many('plot.inventory', domain="[('street_id','in',street_ids)]")
    unit_class_id = fields.Many2one('unit.class', default=lambda self: self._default_unit_class())
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    created_by = fields.Many2one('res.users')
    frequency = fields.Selection(
        string='Frequency',
        selection=[('more_than_three', 'More Than Three'),
                   ('less_than_three', 'Less Than Three')],
        required=False)
    month_wise = fields.Selection(
        string='Month Wise',
        selection=[('yes', 'Yes'),
                   ('no', 'No'), ], default='yes')

    maintenance_summary_xl_report = fields.Binary('Maintenance Summary Report Excel File')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def _default_unit_class(self):
        house = self.env['unit.class'].search([('name', '=', 'House')], limit=1)
        return house.id if house else False

    def generate_xlsx_report(self):
        # Generate the list of months
        months = []
        if self.month_wise == 'yes':
            current_date = self.from_date
            while current_date <= self.to_date:
                months.append(current_date.strftime("%b-%y"))
                current_date += relativedelta(months=1)

        # Determine the property_invoice_type condition based on product_id
        property_invoice_type_condition = (
            "AND am.property_invoice_type = 'maintenance_charges'"
            if self.product_id.name  == 'Maintenance Charges'
            else "AND am.property_invoice_type = 'society_charges'"
        )

        # Construct the SQL query
        # Odoo 19: account_move columns renamed vs. the version this SQL was written for -
        # 'type' -> 'move_type' and 'invoice_payment_state' -> 'payment_state' (aliased back
        # to invoice_payment_state below so the rest of the query/pandas code is unaffected).
        sql_query = f"""
            WITH base_invoices AS (
                SELECT
                    am.id AS invoice_id,
                    am.invoice_date,
                    am.amount_residual_signed,
                    am.amount_total_signed,
                    am.payment_state AS invoice_payment_state,
                    customer.name AS customer_name,
                    sector.name AS sector,
                    street.name AS street,
                    inventory.name AS house_no,
                    product.name AS product,
                    am.property_invoice_type 
                FROM 
                    account_move am 
                JOIN 
                    account_move_line aml ON am.id = aml.move_id
                LEFT JOIN 
                    file f ON f.id = am.file_ids
                LEFT JOIN 
                    society s ON s.id = f.society_id
                LEFT JOIN 
                    society p ON p.id = f.phase_id
                LEFT JOIN 
                    plot_inventory inventory ON inventory.id = f.inventory_id
                LEFT JOIN 
                    sector sector ON sector.id = inventory.sector_id
                LEFT JOIN 
                    res_partner customer ON customer.id = am.partner_id
                LEFT JOIN 
                    street street ON street.id = inventory.street_id
                LEFT JOIN 
                    unit_category_type product ON product.id = f.unit_category_type_id
                LEFT JOIN 
                    plot_category pc ON pc.id = f.category_id
                LEFT JOIN 
                    product_product pp ON pp.id = aml.product_id
                WHERE
                    am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.date >= '2023-11-01'
                    AND am.date >= '{str(self.from_date)}'
                    AND am.date <= '{str(self.to_date)}'
                    AND f.unit_class_id = {str(self.unit_class_id.id)}
                    AND aml.product_id = {str(self.product_id.id)}
                    {"AND f.society_id = " + str(self.society_id.id) if self.society_id else ""}
                    {"AND f.phase_id = " + str(self.phase_id.id) if self.phase_id else ""}
                    {"AND am.create_uid = " + str(self.created_by.id) if self.created_by else ""}
                    {property_invoice_type_condition}
                    {'AND sector.id IN (' + ','.join(map(str, self.sector_ids.ids)) + ')' if self.sector_ids else ''}
                    {'AND street.id IN (' + ','.join(map(str, self.street_ids.ids)) + ')' if self.street_ids else ''}
                    {'AND pc.id IN (' + ','.join(map(str, self.category_ids.ids)) + ')' if self.category_ids else ''}
                    {'AND inventory.id IN (' + ','.join(map(str, self.inventory_ids.ids)) + ')' if self.inventory_ids else ''}
                    {'AND product.id IN (' + ','.join(map(str, self.unit_category_type_ids.ids)) + ')' if self.unit_category_type_ids else ''}
            ), 
            months AS (
                SELECT 
                    generate_series(
                        date_trunc('month', DATE '{str(self.from_date)}'), 
                        date_trunc('month', DATE '{str(self.to_date)}'), 
                        '1 month' :: interval
                    ) AS month_start
            ), 
            grouped_invoices AS (
                SELECT 
                    bi.customer_name,
                    bi.sector,
                    bi.street,
                    bi.house_no,
                    bi.product,
                    bi.property_invoice_type,
                    m.month_start,
                    to_char(m.month_start, 'Mon-YY') AS month, 
                    COUNT(
                        CASE WHEN bi.invoice_payment_state = 'paid' THEN 1 END
                    ) AS total_paid, 
                    COUNT(
                        CASE WHEN bi.invoice_payment_state != 'paid' THEN 1 END
                    ) AS total_unpaid, 
                    SUM(
                        CASE WHEN bi.invoice_payment_state != 'paid' THEN bi.amount_residual_signed ELSE 0 END
                    ) AS unpaid_amount, 
                    
                    SUM(
                        CASE WHEN bi.amount_residual_signed != bi.amount_total_signed THEN bi.amount_total_signed - bi.amount_residual_signed ELSE 0 END
                    ) AS paid_amount,
                    SUM(
                        CASE WHEN bi.invoice_payment_state = 'paid' THEN bi.amount_total_signed - bi.amount_residual_signed ELSE 0 END
                    ) AS month_due 
                FROM 
                    base_invoices bi 
                CROSS JOIN months m 
                WHERE 
                    bi.invoice_date >= m.month_start 
                    AND bi.invoice_date < (
                        m.month_start + '1 month' :: interval
                    ) 
                GROUP BY 
                    bi.customer_name,
                    bi.sector,
                    bi.street,
                    bi.house_no,
                    bi.product,
                    bi.property_invoice_type,
                    m.month_start
            ) 
            SELECT 
                gi.customer_name,
                gi.sector,
                gi.street,
                gi.house_no,
                gi.product,
                gi.property_invoice_type, 
                gi.month,
                gi.month_start,
                gi.total_paid, 
                gi.total_unpaid, 
                gi.unpaid_amount, 
                gi.paid_amount, 
                gi.month_due 
            FROM 
                grouped_invoices gi 
            ORDER BY 
                gi.sector, gi.month_start;
        """

        # Execute the SQL query
        self._cr.execute(sql_query)
        data = self._cr.dictfetchall()

        # Convert the result to a DataFrame
        df = pd.DataFrame(data)

        # Capitalize column headings
        df.columns = map(str.capitalize, df.columns)

        # Convert Month_start to datetime for sorting
        df['Month_start'] = pd.to_datetime(df['Month_start'])

        # Create a pivot table
        pivot_df = df.pivot_table(
            index=['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'],
            columns=df['Month_start'].dt.strftime('%b-%Y'),
            values='Paid_amount',
            aggfunc='sum',
            fill_value=0
        )

        # Flatten multi-level column index
        pivot_df.columns = [col for col in pivot_df.columns]

        # Add Total Unpaid and Total Paid columns
        pivot_df['Total Unpaid Amount'] = df.groupby(['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'])[
            'Unpaid_amount'].sum()
        pivot_df['Total Paid Amount'] = df.groupby(['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'])[
            'Paid_amount'].sum()

        # Add columns for count of paid invoices and unpaid invoices
        pivot_df['Total Paid Invoices'] = df.groupby(['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'])[
            'Total_paid'].sum()
        pivot_df['Total Unpaid Invoices'] = df.groupby(['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'])[
            'Total_unpaid'].sum()

        # Reset index to make 'Customer_name', 'Sector', 'Street', 'House_no', 'Product', and 'Property_invoice_type' columns
        pivot_df = pivot_df.reset_index()

        # Sort the columns to ensure months are in chronological order
        sorted_columns = ['Customer_name', 'Sector', 'Street', 'House_no', 'Product', 'Property_invoice_type'] + \
                         ['Total Paid Invoices', 'Total Unpaid Invoices', 'Total Paid Amount', 'Total Unpaid Amount'] + \
                         sorted(pivot_df.columns[6:-4], key=lambda x: datetime.strptime(x, '%b-%Y'))
        pivot_df = pivot_df[sorted_columns]

        # Export DataFrame to Excel
        # Create a BytesIO buffer to save the Excel file
        excel_buffer = BytesIO()

        # Use pandas to save the DataFrame to the buffer as an Excel file with proper column widths
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            pivot_df.to_excel(writer, index=False)
            # Set column widths
            for column in pivot_df:
                column_width = max(pivot_df[column].astype(str).map(len).max(), len(column))
                col_idx = pivot_df.columns.get_loc(column)
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
        file_name = f'Maintenance Month Wise Summary - [{datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")}].xlsx'

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=month.wise.report.wizard&field=maintenance_summary_xl_report&download=true&id=%s&filename=%s' % (
                self.id, file_name),
        }