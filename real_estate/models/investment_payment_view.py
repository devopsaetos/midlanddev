from odoo import fields, models, api,tools


class InvestmentPaymentView(models.Model):
    _name = 'investment.payment.view'
    _description = 'Investment Payment View'
    _auto = False


    payment_date = fields.Date()
    payment_id = fields.Many2one('account.payment')
    move_id = fields.Many2one('account.move')
    payment_amount = fields.Float()
    payment_amount_residual = fields.Float()

    investment_id = fields.Many2one('investment')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
               CREATE OR REPLACE VIEW %s AS (
               select 
                    row_number() over () as id,
                    pay.date as payment_date,
                    pay.amount_residual as payment_amount_residual,
                    i.id as investment_id,
                    --pay.payment_date as payment_date,
                    pay.id as payment_id,
                    COALESCE(multi.payment_amount,amount) as payment_amount,
                    multi.invoice_id as move_id
                    from 
                    investment i
                    inner join account_payment pay on i.id =pay.investment_id and pay.state = 'posted'
                    left join multi_invoice_payment multi on pay.id = multi.payment_id
                    
               )''' % (self._table,)
                            )
