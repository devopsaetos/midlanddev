# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PlotInventoryStatus(models.TransientModel):
    _name = "plot.inventory.status"
    _description = "Plot Inventory Status"

    state = fields.Selection([
        ('avalible_for_sale', 'Avalible For Sale'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
        ('mortgage', 'Mortgage')])


    def status_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['plot.inventory'].browse(active_ids):
            print (record.id)
            if record.state != self.state:
                record.state = self.state
        return {'type': 'ir.actions.act_window_close'}