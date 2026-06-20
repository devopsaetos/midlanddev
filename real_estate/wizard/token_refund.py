from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TokenRefund(models.TransientModel):
    _name = 'token.refund'
    _description = "Token Refund"


    token_id = fields.Many2one('token.money')
    partner_id = fields.Many2one('res.member', string='Member Name')
    contact_name = fields.Char('Name')
    email = fields.Char('Email')
    cnic = fields.Char('CNIC')
    phone_no = fields.Char('Phone Number')
    society_id = fields.Many2one('society', string='Society')
    date = fields.Date(string='Valid Up To')
    crm_id = fields.Many2one('crm.lead')
    journal_id = fields.Many2one('account.journal', 'Payment Journal', domain=[('type','in',('cash','bank'))])
    cheque_name = fields.Char('Cheque Name')
    cheque_no = fields.Char('Cheque No')
    bank_ref = fields.Char('Bank Reference')
    token_refund_line_ids = fields.One2many('token.refund.line', 'token_refund_id')


    def token_refund_req(self):
        token_refund = self.env.ref('real_estate.token_refund')
        active_id = self._context.get('active_id', False)
        active_model = self._context.get('active_model', False)
        if active_model == 'token.money' and active_id:
            token = self.env['token.money'].browse(active_id)
            company = self.env.company
            if token.token_paid:
                invoice = self.env['account.move'].create({
                    'partner_id': self.partner_id.partner_id.id,
                    'token_id': self.token_id.id,
                    'type': 'in_invoice',
                    'company_id': company.id,
                    'invoice_date': fields.Date.today(),
                    'journal_id': company.knockoff_journal_id.id,
                    'invoice_line_ids': [(0, None, {
                        'product_id': token_refund.id,
                        'name': token_refund.name,
                        'quantity': 1.0,
                        'price_unit': token.token_fees,
                    })]
                })
                invoice.action_post()
                token.state = 'refund'
                token.validity_expire = False
                token.token_line_ids.inventory_id.state = 'avalible_for_sale'


class TokenRefundLine(models.TransientModel):
    _name = 'token.refund.line'
    _description = 'Token Refund Line'


    token_refund_id = fields.Many2one('token.refund',  readonly=True)
    token_fees = fields.Float(string="Token Money", digits='Product Price')
    category_id = fields.Many2one('plot.category', readonly=True)
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product', readonly=True)
