# -*- coding: utf-8 -*-
import base64
from odoo.exceptions import AccessError, ValidationError
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _


class MaintenanceElectricityInvoicesWizard(models.TransientModel):
    _name = 'maintenance.electricity.invoices.wizard'
    _description = 'Maintenance Electricity Invoices Wizard'

    till_date = fields.Date(string="Till Date")
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('society_id.id','=',society_id)]")
    sector_ids = fields.Many2many('sector', domain="[('society_id.id', '=', society_id), ('phase_id.id', '=', phase_id)]")
    category_id = fields.Many2one('plot.category', 'Category')
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product')
    unit_class_id = fields.Many2one('unit.class')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    street_id = fields.Many2one('street', string='Street', domain="[('sector_id', 'in', sector_ids)]")
    house_id = fields.Many2one('plot.inventory', string='House',
                               domain="[('sector_id', 'in', sector_ids), ('street_id', '=', street_id)]")
    file_ids = fields.Many2many('file', string='Files')

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def generate_invoices(self):
        for rec in self:
            domain = []
            month_first_day = rec.till_date.replace(day=1)
            today_date = fields.Date.today()
            month_last_day = datetime(month_first_day.year, month_first_day.month, 1) + relativedelta(months=1, days=-1)
            if rec.street_id:
                domain.append(('street_id', '=', rec.street_id.id))

            if rec.house_id:
                domain.append(('inventory_id', '=', rec.house_id.id))

            domain.append(('society_id', '=', rec.society_id.id))
            domain.append(('phase_id', '=', rec.phase_id.id))
            domain.append(('sector_id', 'in', rec.sector_ids.ids))
            domain.append(('file_status', '!=', 'draft'))
            domain.append(('category_id', '=', rec.category_id.id))
            domain.append(('unit_class_id', '=', rec.unit_class_id.id))
            domain.append(('membership_id', '!=', False))
            if rec.file_ids:
                domain = [('id', 'in', rec.file_ids.ids)]

            files = self.env['file'].search(domain)
            print("TOTAL FILES >>>>>>>>>>>> ", len(files))
            total_inv = 0
            for file_rec in files:
                move_line_records = self.env['account.move.line'].search([
                    ('product_id', '=', rec.product_id.id),
                    ('move_id.partner_id', '=', file_rec.membership_id.id),
                    ('move_id.state', '=', 'posted'),
                    ('move_id.date', '>=', month_first_day),
                    ('move_id.date', '<=', month_last_day),
                    ('move_id.file_ids', '=', file_rec.id)
                ])
                move_records = self.env['account.move'].sudo().browse(move_line_records.mapped('move_id.id'))
                exemption_obj = self.env['maintenance.exemption.history'].search(
                    [('file_id', '=', file_rec.id), ('exemption_state', '=', 'active'),
                     ('product_id.id', '=', rec.product_id.id),
                     ('from_date', '<=', today_date), ('to_date', '>=', today_date)])

                if move_records:
                    print(
                        f"Invoice already exists for {file_rec.name} in {month_first_day.strftime('%B')}. Skipping...")
                    continue
                installment_number = file_rec.maintenance_history_ids[
                                         -1].installment_number + 1 if file_rec.maintenance_history_ids else 1
                maintenance_charges_line = self.env['maintenance.charges.line'].sudo().search(
                    [('category_id', '=', rec.category_id.id),
                     ('unit_class_id', '=', rec.unit_class_id.id),
                     ('maintenance_charges_id.society_id.company_id',
                      '=', self.env.company.id)])
                maintenance_charges_line.filtered(
                    lambda line: file_rec.unit_category_type_id.area_marla in range(line.from_no, line.to_no))
                if maintenance_charges_line:
                    for charge_line in maintenance_charges_line:
                        if round(file_rec.unit_category_type_id.area_marla) in range(charge_line.from_no,
                                                                                     charge_line.to_no + 1):
                            maintenance_rule_line = charge_line.maintenance_charges_type_id.maintenance_charges_type_line_ids.filtered(
                                lambda l: l.product_id.id == rec.product_id.id)
                            if maintenance_rule_line:
                                amount = False
                                if exemption_obj:
                                    if exemption_obj.exemption_type == 'percentage' and exemption_obj.exemption_percent:
                                        amount = maintenance_rule_line.amount / 100 * (
                                                100 - exemption_obj.exemption_percent)
                                    elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'partial' and exemption_obj.exemption_amount:
                                        amount = maintenance_rule_line.amount - exemption_obj.exemption_amount
                                    elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'full':
                                        amount = 0.0
                                else:
                                    amount = maintenance_rule_line.amount
                                # For Service Charges / Electricity
                                if rec.product_id.id == 22943:
                                    if exemption_obj and exemption_obj.exemption_nature == 'full':
                                        pass
                                    else:
                                        prod = [(0, 0, {
                                            'product_id': rec.product_id.id,
                                            'name': rec.product_id.name,
                                            'account_id': rec.product_id.property_account_income_id.id,
                                            'price_unit': amount
                                        })]
                                        invoice = self.env['account.move'].create({
                                            'partner_id': file_rec.membership_id.id,
                                            # 'branch_id': self.env.branch.id,  # res.branch not available in this project
                                            'move_type': 'out_invoice',
                                            'maintenance_charges_id': charge_line.maintenance_charges_id.id,
                                            'invoice_date': month_first_day,
                                            'journal_id': self.env.company.account_journal_id.id,
                                            'invoice_line_ids': prod,
                                            'property_invoice_type': 'society_charges',
                                        })
                                        invoice.file_ids = file_rec.id
                                        invoice.action_post()
                                        print("FILE ID:>>>>>>>", file_rec.id)
                                        print("INVOICE ID:>>>>>>>", invoice.id)
                                        file_rec.maintenance_history_ids.create({
                                            'date': month_first_day,
                                            'installment_number': installment_number,
                                            'amount': invoice.amount_total,
                                            'invoice_created': True,
                                            'invoice_id': invoice.id,
                                            'amount_paid': invoice.amount_total - invoice.amount_residual,
                                            'residual': invoice.amount_residual,
                                            'payment_status': invoice.payment_state,
                                            'file_id': file_rec.id
                                        })
                                # For Maintenance Charges
                                if rec.product_id.id == 103:
                                    if exemption_obj and exemption_obj.exemption_nature == 'full':
                                        pass
                                    else:
                                        prod = [(0, 0, {
                                            'product_id': rec.product_id.id,
                                            'name': rec.product_id.name,
                                            'account_id': rec.product_id.property_account_income_id.id,
                                            'price_unit': amount
                                        })]
                                        invoice = self.env['account.move'].create({
                                            'partner_id': file_rec.membership_id.id,
                                            # 'branch_id': self.env.branch.id,  # res.branch not available in this project
                                            'move_type': 'out_invoice',
                                            'maintenance_charges_id': charge_line.maintenance_charges_id.id,
                                            'invoice_date': month_first_day,
                                            'journal_id': self.env.company.account_journal_id.id,
                                            'invoice_line_ids': prod,
                                            'property_invoice_type': 'maintenance_charges',
                                        })
                                        invoice.file_ids = file_rec.id
                                        invoice.action_post()
                                        total_inv = total_inv + 1
                                        print("FILE ID:>>>>>>>", file_rec.id)
                                        print("INVOICE ID:>>>>>>>", invoice.id)
                                        file_rec.maintenance_history_ids.create({
                                            'date': month_first_day,
                                            'installment_number': installment_number,
                                            'amount': invoice.amount_total,
                                            'invoice_created': True,
                                            'invoice_id': invoice.id,
                                            'amount_paid': invoice.amount_total - invoice.amount_residual,
                                            'residual': invoice.amount_residual,
                                            'payment_status': invoice.payment_state,
                                            'file_id': file_rec.id
                                        })
            print('Total Invoices >>>> ', total_inv)


