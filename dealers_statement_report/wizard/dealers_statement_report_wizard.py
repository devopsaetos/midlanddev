# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DealerStatementWizard(models.TransientModel):
    _name = 'dealer.statement.wizard'
    _description = 'Wizard to generate the Dealer Statement Report'

    investment_ids = fields.Many2many('investment', string='Investment')
    investor_id = fields.Many2one('res.investor', string='Investor')
    report_type = fields.Selection([
        ('summary', 'Summary'),
        ('detailed', 'Detailed'),
    ], default='detailed', required=True)
    date_from = fields.Date()
    date_to = fields.Date()

    @api.onchange('investor_id')
    def _onchange_investor_id(self):
        for rec in self:
            if rec.investor_id:
                return {'domain': {'investment_ids': [('partner_id', '=', rec.investor_id.id)]}}
            return {'domain': {'investment_ids': []}}

    def process_report(self):
        data = {'form': self.read(['investment_ids', 'investor_id', 'report_type', 'date_from', 'date_to'])[0]}
        return self.env.ref('dealers_statement_report.action_report_dealer_statements').report_action(self, data=data)
