from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class MaintenanceCollectionWizard(models.TransientModel):
    _name = 'maintenance.collection.report'
    _description = "Maintenance Collection Report"

    def filter_category_ids(self):
        distinct_category_ids = self.env['file'].search([]).mapped('category_id').ids
        return [('id', 'in', distinct_category_ids)]

    def filter_unit_category_type_ids(self):
        distinct_unit_category_type_ids = self.env['file'].search([]).mapped('unit_category_type_id').ids
        return [('id', 'in', distinct_unit_category_type_ids)]

    category_ids = fields.Many2many('plot.category', string='Category', domain=lambda self: self.filter_category_ids())
    unit_category_type_ids = fields.Many2many('unit.category.type', string='Product',
                                              domain=lambda self: self.filter_unit_category_type_ids())
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    sector_id = fields.Many2many('sector', string='Sector', domain="[('society_id.company_id', '=', company_id)]")
    date_from = fields.Date(default=lambda self: (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Date To', default=fields.Date.today())
    invoice_type = fields.Selection(
        string='Invoice_type',
        selection=[('maintenance_charges', 'Maintenance Charges'),
                   ('society_charges', 'Society Charges'), ],
        required=False, dafault='maintenance_charges')

    # def filter_category_ids(self):
    #     distinct_category_ids = self.env['file'].search([]).mapped('category_id').ids
    #     return [('id', 'in', distinct_category_ids)]
    #
    # investor_ids = fields.Many2many('res.partner', string="Dealer", domain=[('is_investor', '=', 1)])
    # investment_id = fields.Many2one('investment', string="Investment")
    # unit_category_type_ids = fields.Many2many('unit.category.type', string="Product")
    # category_id = fields.Many2one('plot.category', domain=lambda self: self.filter_category_ids())
    # society_id = fields.Many2one('society', string='Society', domain="[('is_society','=',True)]")
    # phase_id = fields.Many2one('society', string='Phase', domain="[('society_id.id','=',society_id)]")

    # file_type = fields.Selection(
    #     string='File Type',
    #     selection=[('open', 'Open'),
    #                ('file', 'File'), ],
    #     required=False, default='file')

    def print(self):
        datas = {
            # 'investor_ids': self.investor_ids,
            # 'investment_id': self.investment_id,
            # 'file_type': self.file_type,
            'sector_id': self.sector_id,
            'category_id': self.category_ids,
            'unit_category_type_ids': self.unit_category_type_ids,
            # 'phase_id': self.phase_id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'invoice_type': self.invoice_type,
        }
        return self.env.ref("maintenance_collection_report.action_maintenance_collection_report").report_action(self, data=datas)
