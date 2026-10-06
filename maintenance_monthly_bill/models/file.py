# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.fields import Domain


class File(models.Model):
    _inherit = 'file'

    # starting point for the first Monthly Bill of a house (later bills take the
    # previous bill's reading); usually filled by the Excel import
    meter_no = fields.Char('Meter No')
    opening_meter_reading = fields.Float('Opening Meter Reading', digits=(16, 0))

    # A file's normal display name is the member's tracking number (MRN-...), which is the
    # same for all of a member's files. Inside the bill wizard (context key
    # 'show_unit_number') show and search by the plot number instead.

    @api.depends_context('show_unit_number')
    @api.depends('unit_number', 'membership_id')
    def _compute_display_name(self):
        if not self.env.context.get('show_unit_number'):
            return super()._compute_display_name()
        for rec in self:
            rec.display_name = ' - '.join(filter(None, [rec.unit_number, rec.membership_id.name]))

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if self.env.context.get('show_unit_number') and value and operator in ('ilike', 'like', '=ilike', '='):
            domain = Domain.OR([domain, Domain('unit_number', operator, value)])
        return domain
