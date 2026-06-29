from odoo import fields, models, api


class TransferApplicationExt(models.Model):
    _inherit = 'transfer.application'

    dealer_id = fields.Many2one('res.partner', 'Dealer', domain=[('is_unit_booking_agent', '=', True)])
