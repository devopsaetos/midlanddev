from odoo import fields, models, api, tools


class FilePaymentView(models.Model):
    _name = 'file.payment.view'
    _description = 'File Payment View'
    _auto = False


    invoice_date = fields.Date(string='Invoice Date')
    payment_date = fields.Date(string='Payment Date')
    payment_id = fields.Many2one('account.payment', string='Payment #')
    move_id = fields.Many2one('account.move', string='Invoice #')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_residual = fields.Float(string='Balance')
    payment_amount = fields.Float(string='Paid Amount')
    payment_amount_residual = fields.Float(string='Payment Remaining')
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('adv_and_securities', 'Advances and Securities'),
        ('installment', 'Installment'),
        ('initial_payment_plus_installment', 'Initial Payment + Installment'),
        ('transfer_application', 'Transfer Application'),
        ('rent', 'Rent'),
        ('others', 'Others'), ('token', 'Token'),
        ('investment', 'Investment'), ('investment_installment', 'Investment Installment'),
        ('maintenance', 'Maintenance Charges'), ('map_fee', 'Mapping Fee'),
        ('tax', 'PRA-Tax'), ('236k_sale', '236k-Sale'),
        ('236k_sale', '236k-Sale'),
        ('demarcation', 'Demarcation'),
        ('merger_adjustment', 'Merger Adjustment'),
    ], string='Invoice Type')

    file_id = fields.Many2one('file')
    midland_payment_ref = fields.Char(string='Building Payment')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''CREATE OR REPLACE VIEW %s AS (
            select row_number() over () as id,
                pay.date as payment_date,
                pay.amount_residual as payment_amount_residual,
                f.id as file_id,
                pay.id as payment_id,
                NULL::varchar as midland_payment_ref,
                COALESCE(multi.payment_amount, amount) as payment_amount,
                multi.invoice_id as move_id,
                invoice.property_invoice_type as property_invoice_type,
                invoice.amount_residual as invoice_residual,
                invoice.amount_total as invoice_amount,
                invoice.invoice_date as invoice_date
            from file f
            inner join account_payment pay on f.id = pay.file_id
            left join multi_invoice_payment multi on multi.payment_id = pay.id
            left join account_move invoice on invoice.id = multi.invoice_id
            where invoice.property_invoice_type IN (\'initial_payment\',\'installment\')
            AND pay.state != \'draft\'
        )''' % (self._table))
