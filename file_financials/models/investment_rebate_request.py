from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InvestmentRebateRequest(models.Model):
    _name = 'investment.rebate.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Investment Rebate'

    name = fields.Char('Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    deal_closure = fields.Selection([('rebate', 'Rebate')], default="rebate", string="Deal Closure")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    investor_id = fields.Many2one('res.investor', string="Investor")
    investment_id = fields.Many2one('investment', string="Investment")
    category_id = fields.Many2one('plot.category', string="Category")
    request_line_ids = fields.One2many('investment.rebate.request.line', 'rebate_request_id')
    state = fields.Selection(selection=[('draft', 'Draft'), ('validate', 'Validated'), ], string='Status', required=True, readonly=True, copy=False, tracking=True,
                             default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('rebate.request.sequence') or _('New')
        new_record = super().create(vals_list)
        return new_record

    def validate(self):
        if self.request_line_ids:
            for line in self.request_line_ids:
                if line.transaction_type == 'booking' and line.settlement_option == 'separate':
                    rebate_invoice = self.env['account.move'].create({
                        'partner_id': line.investment_id.partner_id.id if line.agent_type == 'dealer' else line.investment_id.marketing_company_id.id,
                        # 'branch_id': self.env.branch.id,
                        'move_type': 'in_invoice',
                        'investment_id': line.investment_id.id,
                        'invoice_date': fields.Date.today(),
                        'property_invoice_type': 'dealer_rebate',
                        # 'journal_id': self.env.company.account_journal_id.id,
                        'invoice_line_ids': [(0, 0, {
                            'product_id': self.env.ref('real_estate.rebate_product').id,
                            'name': self.env.ref('real_estate.rebate_product').name,
                            'account_id': self.env.ref('real_estate.rebate_product').product_id.property_account_income_id.id,
                            'price_unit': line.actual_amount,
                        })],
                    })
                    rebate_invoice.action_post()
                    line.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.rebate_given = line.actual_amount
                if line.transaction_type == 'booking' and line.settlement_option == 'net_off':
                    rebate_invoice = self.env['account.move'].create({
                        'partner_id': line.investment_id.partner_id.id if line.agent_type == 'dealer' else line.investment_id.marketing_company_id.id,
                        # 'branch_id': self.env.branch.id,
                        'move_type': 'out_refund',
                        'investment_id': line.investment_id.id,
                        'invoice_date': fields.Date.today(),
                        'property_invoice_type': 'dealer_rebate',
                        # 'journal_id': self.env.company.account_journal_id.id,
                        'invoice_line_ids': [(0, 0, {
                            'product_id': self.env.ref('real_estate.rebate_product').id,
                            'name': self.env.ref('real_estate.rebate_product').name,
                            'account_id': self.env.ref('real_estate.rebate_product').product_id.property_account_income_id.id,
                            'price_unit': line.actual_amount,
                        })],
                    })
                    rebate_invoice.action_post()
                    line.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.rebate_given = line.actual_amount
                if line.transaction_type == 'confirmation':
                    rebate_invoice = self.env['account.move'].create({
                        'partner_id': line.investment_id.partner_id.id if line.agent_type == 'dealer' else line.investment_id.marketing_company_id.id,
                        # 'branch_id': self.env.branch.id,
                        'move_type': 'in_invoice',
                        'investment_id': line.investment_id.id,
                        'invoice_date': fields.Date.today(),
                        'property_invoice_type': 'dealer_rebate',
                        # 'journal_id': self.env.company.account_journal_id.id,
                        'invoice_line_ids': [(0, 0, {
                            'product_id': self.env.ref('real_estate.rebate_product').id,
                            'name': self.env.ref('real_estate.rebate_product').name,
                            'account_id': self.env.ref('real_estate.rebate_product').product_id.property_account_income_id.id,
                            'price_unit': line.actual_amount,
                        })],
                    })
                    rebate_invoice.action_post()
                    line.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.move_id = rebate_invoice.id
                    line.investment_rebate_line_id.rebate_given = line.actual_amount
        self.state = 'validate'


class InvestmentRebateRequestLine(models.Model):
    _name = 'investment.rebate.request.line'
    _description = 'Investment Rebate Line'

    select = fields.Boolean(default=False, string="Select")
    investment_rebate_line_id = fields.Many2one('rebate.on.allotment')
    investor_id = fields.Many2one('res.investor', string="Dealer")
    investment_id = fields.Many2one('investment', string="Investment #", related='investment_rebate_line_id.investment_id')
    calculated_rebate = fields.Float(string="Calculated Rebate")
    settlement_option = fields.Selection([('net_off', 'Net Off'), ('separate', 'Separate'), ('files', 'Files')], tracking=True)
    actual_amount = fields.Float(string="Actual Amount")
    agent_type = fields.Selection([('dealer', 'Dealer'), ('marketing_company', 'Marketing Company')], string="Agent Type", required=True,
                                  tracking=True)
    transaction_type = fields.Selection([('booking', 'Booking'), ('confirmation', 'Confirmation')], string="Transaction Type", required=True,
                                        tracking=True)
    move_id = fields.Many2one('account.move')
    rebate_request_id = fields.Many2one('investment.rebate.request')
