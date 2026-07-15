# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MaintenanceInquiryWizard(models.TransientModel):
    _name = 'maintenance.inquiry.wizard'
    _description = 'Maintenance Inquiry Wizard'

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('society_id.id','=',society_id)]")
    sector_id = fields.Many2one('sector')
    street_id = fields.Many2one('street', string='Street', domain="[('sector_id', '=', sector_id)]")
    # product_id = fields.Many2one('unit.category.type', 'Product')
    house_id = fields.Many2one('plot.inventory', string='House',
                               domain="[('sector_id', '=', sector_id), ('street_id', '=', street_id)]")
    category_id = fields.Many2one('plot.category', 'Category')
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    size_id = fields.Many2one('unit.size', 'Size')
    unit_class_id = fields.Many2one('unit.class', string="Type")
    file_id = fields.Many2one('file', string='File')
    partner_id = fields.Many2one('res.partner', string='Member')
    maintenance_inquiry_line_ids = fields.One2many('maintenance.inquiry.line', 'maintenance_inquiry_wizard_id',
                                                   string='Maintenance Inquiry Lines')

    @api.onchange('house_id')
    def onchange_house_id(self):
        for rec in self:
            file = self.env['file'].sudo().search([('inventory_id', '=', rec.house_id.id)], limit=1)
            if rec.house_id:
                rec.partner_id = file.membership_id.id
                rec.category_id = file.category_id.id
                rec.unit_category_type_id = file.unit_category_type_id.id
                rec.size_id = file.size_id.id
                rec.unit_class_id = file.unit_class_id.id
                rec.file_id = file.id

    def get_maintenance_inquiry(self):
        for rec in self:
            rec.maintenance_inquiry_line_ids.unlink()
            if rec.house_id and rec.file_id:
                set_date = '2023-11-01'
                for line in rec.file_id.maintenance_history_ids.filtered(lambda l: str(l.date) >= set_date):
                    self.env['maintenance.inquiry.line'].sudo().create({
                        'date': line.date,
                        'amount': line.amount,
                        'installment_number': line.installment_number,
                        'invoice_created': line.invoice_created,
                        'invoice_id': line.invoice_id.id if line.invoice_id else None,
                        'payment_date': line.payment_date,
                        'amount_paid': line.amount_paid,
                        'residual': line.residual,
                        'payment_status': line.payment_status,
                        'state': line.state,
                        'maintenance_inquiry_wizard_id': rec.id
                    })
        return {
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def print_pdf(self):
        for rec in self:
            report = self.env.ref('maintenance_statement_inquiry.action_maintenance_inquiry_report').report_action(rec)
            return report

class MaintenanceInquiryLines(models.TransientModel):
    _name = 'maintenance.inquiry.line'
    _description = 'Maintenance Inquiry Lines'

    maintenance_inquiry_wizard_id = fields.Many2one('maintenance.inquiry.wizard')
    date = fields.Date(string="Date")
    amount = fields.Float(string="Amount")
    installment_number = fields.Integer(string="Sr. No")
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', string="Invoice#")
    state = fields.Char(string='Status')
    payment_date = fields.Date('Payment Date')
    amount_paid = fields.Float('Amount Paid')
    residual = fields.Float('Amount Due')
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'), ('cancel', 'Cancelled')],
        string='Status')
