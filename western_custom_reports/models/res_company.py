from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    bank_name        = fields.Char(string='Bank Name')
    bank_routing     = fields.Char(string='Bank Routing')
    bank_swift       = fields.Char(string='Swift Code')
    bank_acc_number  = fields.Char(string='Account Number')
    bank_beneficiary = fields.Text(string='Beneficiary Name')
    bank_address1    = fields.Text(string='Bank Address 1')
    bank_address2    = fields.Text(string='Bank Address 2')