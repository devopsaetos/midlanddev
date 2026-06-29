from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InvestmentRebateWizard(models.TransientModel):
    _name = 'investment.rebate.wizard'
    _description = 'Investment Rebate'

    deal_closure = fields.Selection([('rebate', 'Rebate')], default="rebate", string="Deal Closure")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    investor_id = fields.Many2one('res.investor', string="Investor")
    investment_id = fields.Many2one('investment', string="Investment")
    category_id = fields.Many2one('plot.category', string="Category")
    search_line_ids = fields.One2many('investment.rebate.wizard.line', 'rebate_search_id')

    def search_records(self):
        for rec in self:
            domain = []
            if rec.date_from:
                domain.append(('investment_id.booking_date', '>=', rec.date_from))
            if rec.date_to:
                domain.append(('investment_id.booking_date', '<=', rec.date_to))
            if rec.investor_id:
                domain.append(('investment_id.partner_id.id', '=', rec.investor_id.id))
            domain.append(('move_id', '=', False))
            domain.append(('rebate_given', '=', 0))
            lines = self.env['rebate.on.allotment'].search(domain)
            if lines:
                rec.search_line_ids = False
                for line in lines:
                    rebate_amount = 0
                    if line.transaction_type == 'confirmation':
                        record = self.env['file'].search(
                            [('investment_id', '=', line.investment_id.id), ('file_status', '=', 'approve')])
                        if record:
                            for file in record:
                                rebate_amount += file.net_sale_amount * (line.total_rebate / 100)
                    else:
                        rebate_amount += line.total_rebate if line.calculation_basis == 'fix' else line.investment_id.total_amount * (
                                    line.total_rebate / 100)
                    # self.env['investment.rebate.wizard.line'].create({
                    rec.search_line_ids = [(0, 0, {
                        'investment_rebate_line_id': line.id,
                        'agent_type': line.agent_type,
                        'transaction_type': line.transaction_type,
                        'investor_id': line.investment_id.partner_id.id,
                        'investment_id': line.investment_id.id,
                        # 'calculated_rebate': line.total_rebate if line.calculation_basis == 'fix' else line.investment_id.total_amount * (line.total_rebate / 100),
                        'calculated_rebate': rebate_amount,
                        'settlement_option': line.settlement_option,
                        'rebate_search_id': rec.id
                    })]
            return {
                'context': self.env.context,
                'view_mode': 'form',
                # 'view_id': view.id,
                'res_model': self._name,
                'res_id': rec.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def create_rebate_request(self):
        for rec in self:
            if rec.search_line_ids:
                line_ids = rec.search_line_ids.filtered(lambda l: l.select == True)
                request_lines = []
                for lines in line_ids:
                    request_lines.append((0, 0, {
                        'select': True,
                        'investment_rebate_line_id': lines.investment_rebate_line_id.id,
                        'agent_type': lines.agent_type,
                        'transaction_type': lines.transaction_type,
                        'investor_id': lines.investor_id.id,
                        'investment_id': lines.investment_id,
                        'calculated_rebate': lines.calculated_rebate,
                        'settlement_option': lines.settlement_option,
                        'actual_amount': lines.actual_amount
                    }))
                rebate_request = self.env['investment.rebate.request'].create({
                    'deal_closure': rec.deal_closure,
                    'date_from': rec.date_from,
                    'date_to': rec.date_to,
                    'investor_id': rec.investor_id.id,
                    'investment_id': rec.investment_id.id,
                    'request_line_ids': request_lines
                })
                if rebate_request:
                    return {
                        'name': _('Rebate Request'),
                        'res_model': 'investment.rebate.request',
                        'type': 'ir.actions.act_window',
                        'context': {},
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': rebate_request.id,
                        'domain': [('id', '=', rebate_request.id)],
                        'target': 'self'
                    }


class InvestmentRebateLine(models.TransientModel):
    _name = 'investment.rebate.wizard.line'
    _description = 'Investment Rebate Line'

    select = fields.Boolean(default=False, string="Select")
    investment_rebate_line_id = fields.Many2one('rebate.on.allotment')
    investor_id = fields.Many2one('res.investor', string="Dealer")
    investment_id = fields.Many2one('investment', string="Investment #",
                                    related='investment_rebate_line_id.investment_id')
    calculated_rebate = fields.Float(string="Calculated Rebate")
    settlement_option = fields.Selection([('net_off', 'Net Off'), ('separate', 'Separate'), ('files', 'Files')],
                                         tracking=True)
    agent_type = fields.Selection([('dealer', 'Dealer'), ('marketing_company', 'Marketing Company')],
                                  string="Agent Type", required=True,
                                  tracking=True)
    transaction_type = fields.Selection([('booking', 'Booking'), ('confirmation', 'Confirmation')],
                                        string="Transaction Type", required=True,
                                        tracking=True)
    actual_amount = fields.Float(string="Actual Amount")
    rebate_search_id = fields.Many2one('investment.rebate.wizard')
