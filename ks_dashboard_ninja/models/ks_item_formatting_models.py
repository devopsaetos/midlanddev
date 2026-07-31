# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.exceptions import UserError


class KsNumberFormat(models.Model):
    _name = 'ks.number.format'
    _description = 'Number formats for Dashboard Ninja'

    name = fields.Char(required=True)
    number_format_line_ids = fields.One2many('ks.number.format.line', 'number_format_id')

    def _is_protected_format(self):
        """Check if the record is a protected format (Global or Indian) by XML ID"""
        xml_ids = ['ks_dashboard_ninja.ks_number_format_global','ks_dashboard_ninja.ks_number_format_indian']
        protected_records = [self.env.ref(xml_id, raise_if_not_found=False) for xml_id in xml_ids]
        protected_ids = [ record.id for record in protected_records if hasattr(record, 'id')]

        return self.id in protected_ids

    def write(self, vals):
        """Prevent writing to Global and Indian formatting options"""
        protected_records = self.filtered(lambda r: r._is_protected_format())
        if protected_records:
            raise UserError('You cannot modify Global Format or Indian Format. These are system-defined formats.')
        return super(KsNumberFormat, self).write(vals)

    def unlink(self):
        """Prevent deletion of Global and Indian formatting options"""
        protected_records = self.filtered(lambda r: r._is_protected_format())
        if protected_records:
            raise UserError('You cannot delete Global Format or Indian Format. These are system-defined formats.')
        return super(KsNumberFormat, self).unlink()

class KsNumberFormatLine(models.Model):
    _name = 'ks.number.format.line'
    _description = 'Number format Lines for Dashboard Ninja'
    _order = 'power_of_ten ASC'

    suffix = fields.Char(size=10, required=True)
    power_of_ten = fields.Integer(required=True, help="Power of ten (exponent) for the number format (e.g., 3 for 10³ = 1,000). Must be between 0 and 24.")
    number_format_id = fields.Many2one('ks.number.format')

    _power_of_ten_uniq = models.Constraint(
        "UNIQUE (number_format_id, power_of_ten)", 'The power of ten should be unique per format record.'
    )

    _power_of_ten_range = models.Constraint(
        'check(power_of_ten >= 2 and power_of_ten <= 18)', 'Power of ten must be between 2 and 18.',
    )

