# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class AccountMoveExt(models.Model):
    _inherit = 'account.move'

    property_invoice_type = fields.Selection(selection_add=[('booking_allotment', 'Booking Allotment'),
                                                            ('allotment_installment', 'Allotment Installment'),
                                                            ('registration', 'Registration'),
                                                            ('security', 'Security'),
                                                            ('dealer_rebate', 'Rebate'),
                                                            ('renewal', 'Renewal'),
                                                            ('buy_back', 'Buy Back'),
                                                            ('dealer_cancellation', 'Dealer Cancellation')])
    open_file_issuance_id = fields.Many2one('open.file.issuance.request')
    booking_allotment_id = fields.Many2one('unit.booking.allotment')
    units_booking_id = fields.Many2one('units.booking')
    dealer_renewal_id = fields.Many2one('dealer.renewal.req')
    dealer_cancellation_id = fields.Many2one("dealer.cancellation.req")
    buy_back_id = fields.Many2one('buy.back')
