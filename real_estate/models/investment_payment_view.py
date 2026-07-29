from odoo import fields, models, api,tools


class InvestmentPaymentView(models.Model):
    _name = 'investment.payment.view'
    _description = 'Investment Payment View'
    _auto = False


    payment_date = fields.Date()
    payment_id = fields.Many2one('account.payment')
    # midland_payment_id (Many2one to midland.payment) is added by
    # midland_invoicing/models/investment_payment_view_ext.py - real_estate
    # doesn't depend on midland_invoicing, so the field can't be declared
    # here even though this view's own SQL already unions in midland_payment
    # rows (plain SQL against the table, no model dependency needed for that).
    move_id = fields.Many2one('account.move')
    # Which product.realestate (Booking/Confirmation Amount/Balloon Payment/...)
    # this payment's invoice was actually raised for - property_invoice_type
    # only distinguishes "Investment" vs "Investment Installment" broadly, not
    # which specific installment this was, so the product is the real signal
    # of "what type of invoice" this payment settled.
    product_id = fields.Many2one('product.realestate', string='Invoice Type')
    payment_amount = fields.Float()
    payment_amount_residual = fields.Float()

    investment_id = fields.Many2one('investment')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
               CREATE OR REPLACE VIEW %s AS (
               select
                    row_number() over () as id,
                    payment_date, payment_amount_residual, investment_id,
                    payment_id, midland_payment_id, payment_amount, move_id, product_id
               from (
                    -- old flow: plain account.payment linked straight to the deal
                    select
                        pay.date as payment_date,
                        pay.amount_residual as payment_amount_residual,
                        i.id as investment_id,
                        pay.id as payment_id,
                        NULL::integer as midland_payment_id,
                        COALESCE(multi.payment_amount, pay.amount) as payment_amount,
                        multi.invoice_id as move_id,
                        NULL::integer as product_id
                    from investment i
                    inner join account_payment pay on i.id = pay.investment_id and pay.state = 'paid'
                    left join multi_invoice_payment multi on pay.id = multi.payment_id

                    union all

                    -- receive_payment()'s auto-payment path (midland_invoicing) -
                    -- these never go through account.payment at all, so the old
                    -- branch above never picked them up. One row per invoice
                    -- actually paid (not per payment), matching the old flow's
                    -- per-invoice granularity for a payment covering several.
                    select
                        mp.date as payment_date,
                        0 as payment_amount_residual,
                        mp.investment_id as investment_id,
                        NULL::integer as payment_id,
                        mp.id as midland_payment_id,
                        mpl.payment_amount as payment_amount,
                        mi.jv_id as move_id,
                        (select mil.product_id from midland_invoice_line mil
                         where mil.invoice_id = mi.id
                         order by mil.id asc limit 1) as product_id
                    from midland_payment mp
                    inner join midland_payment_line mpl on mpl.payment_id = mp.id
                    inner join midland_invoice mi on mi.id = mpl.invoice_id
                    where mp.investment_id is not null and mp.state != 'cancelled'
               ) combined
               )''' % (self._table,)
                            )
