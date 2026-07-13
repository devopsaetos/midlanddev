# -*- coding: utf-8 -*-
import base64
import datetime
from datetime import timedelta, datetime
from io import BytesIO
import pandas as pd
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class MaintenancePaymentSummaryWizard(models.TransientModel):
    _name = 'maintenance.payment.summary.wizard'
    _description = 'Maintenance Payment Summary Wizard'

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
    maintenance_payment_summary_xl = fields.Binary('Maintenance Summary Report Excel File')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def _default_unit_class(self):
        house = self.env['unit.class'].search([('name', '=', 'House')], limit=1)
        return house.id if house else False

    def generate_xlsx_report(self):
        # Determine the property_invoice_type condition based on product_id
        property_invoice_type_condition = (
            "AND am.property_invoice_type = 'maintenance_charges'"
            if self.product_id.name == 'Maintenance Charges'
            else "AND am.property_invoice_type = 'society_charges'"
        )

        # Construct the SQL query
        # Odoo 19 field-name fixes vs. the version this SQL was originally written for:
        #  - account_move: 'type' -> 'move_type', 'invoice_payment_state' -> 'payment_state'
        #  - account_payment: no 'payment_date' column (it's 'date'); cancelled state value
        #    is spelled 'canceled' (single L), not 'cancelled'.
        sql_query = f"""
            SELECT
                customer.name AS Customer,
                f.name as File,
                sector.name AS Sector,
                street.name AS Street,
                inventory.name AS House_No,
                product.name AS Product,
                INITCAP(am.property_invoice_type) as Property_Invoice_Type,
                am.name as Invoice,
                am.invoice_date as Invoice_Date,
                ap.name as Payment,
                mip.payment_date as Payment_Date, 
                am.amount_total as Total_Amount,
                mip.payment_amount as Payment_Amount,
                am.amount_residual as Amount_Due,
                mip.discount_amount as Discount_Amount,
                INITCAP(am.payment_state) as Payment_State
            FROM 
                multi_invoice_payment mip
            LEFT JOIN 
                account_payment ap on ap.id = mip.payment_id 
            LEFT JOIN
                account_move am ON am.id = mip.invoice_id
            LEFT JOIN 
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
                AND ap.state NOT IN ('draft', 'canceled')
                AND am.invoice_date >= '2023-11-01'
                AND ap.date >= '{str(self.from_date)}'
                AND ap.date <= '{str(self.to_date)}'
                AND f.unit_class_id = {str(self.unit_class_id.id)}
                AND aml.product_id = {str(self.product_id.id)}
                {"AND f.society_id = " + str(self.society_id.id) if self.society_id else ""}
                {"AND f.phase_id = " + str(self.phase_id.id) if self.phase_id else ""}
                {"AND ap.create_uid = " + str(self.created_by.id) if self.created_by else ""}
                {property_invoice_type_condition}
                {'AND sector.id IN (' + ','.join(map(str, self.sector_ids.ids)) + ')' if self.sector_ids else ''}
                {'AND street.id IN (' + ','.join(map(str, self.street_ids.ids)) + ')' if self.street_ids else ''}
                {'AND pc.id IN (' + ','.join(map(str, self.category_ids.ids)) + ')' if self.category_ids else ''}
                {'AND inventory.id IN (' + ','.join(map(str, self.inventory_ids.ids)) + ')' if self.inventory_ids else ''}
                {'AND product.id IN (' + ','.join(map(str, self.unit_category_type_ids.ids)) + ')' if self.unit_category_type_ids else ''}
            ORDER BY
                customer,
                invoice
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
            df.to_excel(writer, index=False, sheet_name='Maintenance Payments Summary')
            # Set column widths
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                col_idx = df.columns.get_loc(column)
                writer.sheets['Maintenance Payments Summary'].set_column(col_idx, col_idx, column_width)

        # Get the bytes data from the buffer
        excel_bytes = excel_buffer.getvalue()

        # Encode the bytes data using base64
        excel_base64 = base64.b64encode(excel_bytes)

        # Convert the base64 data to a string
        excel_base64_str = excel_base64.decode('utf-8')

        # Close the buffer
        excel_buffer.close()

        # Save the base64-encoded Excel data to the desired field in your model
        self.maintenance_payment_summary_xl = excel_base64_str
        file_name = f'Maintenance Payments Summary - [{datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")}].xlsx'

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=maintenance.payment.summary.wizard&field=maintenance_payment_summary_xl&download=true&id=%s&filename=%s' % (
            self.id, file_name),
        }
