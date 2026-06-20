from odoo import fields, models, api, tools


class FileInstallmentPayments(models.Model):
    _name = 'file.installment.payment'
    _description = 'File Installment Payments'

    multi_invoice_line_id = fields.Many2one('multi.invoice.payment', string='Multi Invoice Line')
    name = fields.Char(string="Name")
    invoice_id = fields.Many2one('account.move', string='Invoice #', related='multi_invoice_line_id.invoice_id')
    invoice_date = fields.Date(string='Invoice Date', related='invoice_id.invoice_date')
    payment_id = fields.Many2one('account.payment', string='Payment #')
    payment_date = fields.Date(string='Payment Date', related='payment_id.date')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_residual = fields.Float(string='Balance')
    payment_amount = fields.Float(string='Paid Amount')
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
    ], string='Invoice Type', related='invoice_id.property_invoice_type')
    invoice_payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment State', related='invoice_id.payment_state')

    file_id = fields.Many2one('file')


class FileAdditionalPayments(models.Model):
    _name = 'file.additional.payment'
    _description = 'File Additional Payments'

    multi_invoice_line_id = fields.Many2one('multi.invoice.payment', string='Multi Invoice Line')
    name = fields.Char(string="Name")
    invoice_id = fields.Many2one('account.move', string='Invoice #', related='multi_invoice_line_id.invoice_id')
    invoice_date = fields.Date(string='Invoice Date', related='invoice_id.invoice_date')
    payment_id = fields.Many2one('account.payment', string='Payment #')
    payment_date = fields.Date(string='Payment Date', related='payment_id.date')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_residual = fields.Float(string='Balance')
    payment_amount = fields.Float(string='Paid Amount')
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
    ], string='Invoice Type', related='invoice_id.property_invoice_type')
    invoice_payment_state = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment State', related='invoice_id.payment_state')

    file_id = fields.Many2one('file')