# -*- coding: utf-8 -*-
from datetime import datetime

from odoo.exceptions import UserError
from pytz import timezone

from odoo import models, api, _


class MaintenanceRecoveryReport(models.AbstractModel):
    _name = 'report.maintenance_recovery.maintenance_recovery_report'
    _description = 'Maintenance Recovery Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))

        query = """
            SELECT
                s.name AS sector_name,
                p.name AS product_name,
                rc.id AS company_id,
				f.name AS file_name,
				rp.name AS customer_name,
                -- Odoo 19: account_move.state is the workflow state (draft/posted/cancel) and
                -- never holds 'paid' - it never did even in the pre-migration v13 code this was
                -- ported from (account.invoice's old 'paid' state field was removed when
                -- account.invoice was merged into account.move). The actual payment status
                -- field is `payment_state`, which does have a 'paid' value (see the same
                -- state -> payment_state fix applied in maintenance_recovery_batch). Original
                -- (always-false) expressions kept commented below each corrected line.
                -- SUM(CASE WHEN m.state = 'paid' THEN m.amount_total ELSE 0 END) AS total_paid,
                SUM(CASE WHEN m.payment_state = 'paid' THEN m.amount_total ELSE 0 END) AS total_paid,
                -- SUM(CASE WHEN m.state != 'paid' THEN m.amount_total ELSE 0 END) AS total_not_paid,
                SUM(CASE WHEN m.payment_state != 'paid' THEN m.amount_total ELSE 0 END) AS total_not_paid,
                -- COUNT(CASE WHEN m.state = 'paid' THEN 1 END) AS count_paid_invoices,
                COUNT(CASE WHEN m.payment_state = 'paid' THEN 1 END) AS count_paid_invoices,
                -- COUNT(CASE WHEN m.state != 'paid' THEN 1 END) AS count_not_paid_invoices
                COUNT(CASE WHEN m.payment_state != 'paid' THEN 1 END) AS count_not_paid_invoices
            FROM
                account_move m
            INNER JOIN file f ON m.file_ids = f.id
            INNER JOIN sector s ON f.sector_id = s.id
            INNER JOIN unit_category_type p ON f.unit_category_type_id = p.id
            INNER JOIN unit_size us ON f.size_id = us.id
            -- Odoo 19: `file` has no `company_id` column (verified against
            -- real_estate/models/file.py) - company is only reachable via
            -- file.society_id -> society.company_id. Original direct join kept commented.
            -- INNER JOIN res_company rc ON f.company_id = rc.id
            INNER JOIN society soc ON f.society_id = soc.id
            INNER JOIN res_company rc ON soc.company_id = rc.id
			INNER JOIN res_partner rp ON m.partner_id = rp.id
            -- Odoo 19: 'unit.type' is not a model in this codebase; f.unit_class_id points at
            -- 'unit.class' (table unit_class), not a non-existent 'unit_type' table. Original
            -- join kept commented.
            -- LEFT JOIN unit_type ut ON f.unit_class_id = ut.id
            LEFT JOIN unit_class ut ON f.unit_class_id = ut.id
            WHERE 1=1
            AND m.property_invoice_type = 'maintenance_charges'
            AND m.file_ids IS NOT NULL
        """
        if docs.date_from:
            query += "AND m.invoice_date >= '%s' " % docs.date_from

        if docs.date_to:
            query += "AND m.invoice_date <= '%s' " % docs.date_to

        if docs.sector_ids:
            sector_ids = ','.join(map(str, docs.sector_ids.ids))
            query += "AND s.id IN (%s) " % sector_ids

        if docs.product_id:
            product_id = ','.join(map(str, docs.product_id.ids))
            query += "AND p.id IN (%s) " % product_id

        if docs.size_id:
            query += "AND us.id = '%s' " % (str(docs.size_id.id))

        if docs.type_id:
            query += "AND ut.id = '%s' " % (str(docs.type_id.id))

        query += "GROUP BY s.name, p.name, rc.id, f.name,rp.name"

        self.env.cr.execute(query)
        result = self.env.cr.fetchall()
        sectors_data = {}
        for row in result:
            sector_name, product_name, company_id, file_name,customer_name,total_paid, total_not_paid, count_paid, count_not_paid = row
            if sector_name not in sectors_data:
                sectors_data[sector_name] = []
            sectors_data[sector_name].append({
                'product_name': product_name,
                'company_id': company_id,
                'file_name': file_name,
                'customer_name': customer_name,
                'count_not_paid': count_not_paid,
                'count_paid': count_paid,
                'total_not_paid': total_not_paid,
                'total_paid': total_paid
            })

        products_data = {}
        for row in result:
            sector_name, product_name, company_id, file_name, customer_name, total_paid, total_not_paid, count_paid, count_not_paid = row
            if sector_name not in products_data:
                products_data[sector_name] = []

            # Check if the product exists for the sector, if not, add a new dictionary
            existing_product = next(
                (product for product in products_data[sector_name] if product['name'] == product_name), None)
            if existing_product is None:
                new_product = {
                    'name': product_name,
                    'total_paid': total_paid,
                    'total_not_paid': total_not_paid,
                    'count_paid': count_paid,
                    'count_not_paid': count_not_paid
                }
                products_data[sector_name].append(new_product)
            else:
                # If the product already exists, update its values
                existing_product['total_paid'] += total_paid
                existing_product['total_not_paid'] += total_not_paid
                existing_product['count_paid'] += count_paid
                existing_product['count_not_paid'] += count_not_paid

        # Convert products_data to a list of dictionaries
        products_list = [{'name': name, 'products': products} for name, products in products_data.items()]
        sectors_list = [{'name': name, 'products': products} for name, products in sectors_data.items()]
        # company = sectors_list[0]['products'][0]['company_id']
        # company_id = self.env['res.company'].browse(company)
        company_id = sectors_list[0]['products'][0]['company_id'] if sectors_list and sectors_list[0]['products'] else None
        company = self.env['res.company'].browse(company_id) if company_id else None
        grand_total_count_not_paid = 0
        grand_total_count_paid = 0
        grand_total_not_paid = 0
        grand_total_paid = 0
        for sector in sectors_data.values():
            for product in sector:
                grand_total_count_not_paid += product['count_not_paid']
                grand_total_count_paid += product['count_paid']
                grand_total_not_paid += product['total_not_paid']
                grand_total_paid += product['total_paid']
        return {
            # 'data': record,
            'docs': docs,
            'sectors': sectors_list,
            'products': products_list,  # Include the product totals in the return dictionary
            'result': result,
            'company': company,
            'date_from': docs.date_from if docs.date_from else None,
            'date_to': docs.date_to if docs.date_to else None,
            'sector_ids': docs.sector_ids if docs.sector_ids else None,
            'size_id': docs.size_id if docs.size_id else None,
            'type_id': docs.type_id if docs.type_id else None,
            'product_id': docs.product_id if docs.product_id else None,
            'grand_total_count_not_paid': grand_total_count_not_paid,
            'grand_total_count_paid': grand_total_count_paid,
            'grand_total_not_paid': grand_total_not_paid,
            'grand_total_paid': grand_total_paid,
        }
