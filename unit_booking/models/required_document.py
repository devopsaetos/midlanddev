from odoo import fields, models, api


class RequiredDocumentsDetail(models.Model):
    _name = 'required.documents.detail'
    _description = 'Required Documents Detail'

    units_booking_id = fields.Many2one('units.booking')
    description = fields.Char()
    attachment = fields.Binary(attachment=True, required=True)
    party = fields.Selection([
        ('self', 'Self'),
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ])
    date = fields.Date(default=fields.Date.today())