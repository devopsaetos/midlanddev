# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UnitBookingResetPrintState(models.TransientModel):
    _name = "unit.booking.reset.print.state"
    _description = "Unit Booking Reset Printing State of open files"

    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    prefix_id = fields.Many2one('unit.batch.generation.line')
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    search_line_ids = fields.One2many('unit.booking.reset.print.state.line', 'search_id')

    # what you want to reset boolean fields
    is_qr_printed = fields.Boolean(default=False)
    is_receipt_printed = fields.Boolean(default=False)
    is_ledger_printed = fields.Boolean(default=False)

    @api.onchange('batch_id', 'prefix_id')
    def onchange_method(self):
        domain = [('batch_id', '=', self.batch_id.id),
                  ('prefix_id', '=', self.prefix_id.id),
                  ('state', 'in', ['print', 'assignment'])]
        if self.is_qr_printed:
            domain.append(('is_qr_printed', '=', self.is_qr_printed))
        if self.is_receipt_printed:
            domain.append(('is_receipt_printed', '=', self.is_receipt_printed))
        if self.is_ledger_printed:
            domain.append(('is_ledger_printed', '=', self.is_ledger_printed))
        if self.prefix_id and self.batch_id:
            return {
                'domain': {
                    'unit_booking_starting_id': domain
                }
            }

    @api.onchange('unit_booking_starting_id')
    def onchange_starting_number(self):
        domain = [('number', '>=', self.unit_booking_starting_id.number),
                  ('batch_id', '=', self.unit_booking_starting_id.batch_id.id),
                  ('prefix_id', '=', self.unit_booking_starting_id.prefix_id.id),
                  ('state', 'in', ['print', 'assignment'])]

        if self.is_qr_printed:
            domain.append(('is_qr_printed', '=', self.is_qr_printed))
        if self.is_receipt_printed:
            domain.append(('is_receipt_printed', '=', self.is_receipt_printed))
        if self.is_ledger_printed:
            domain.append(('is_ledger_printed', '=', self.is_ledger_printed))
        if self.prefix_id and self.batch_id:
            return {
                'domain': {
                    'unit_booking_ending_id': domain,
                }
            }

    def constrains(self):
        if not self.is_qr_printed and not self.is_receipt_printed and not self.is_ledger_printed:
            raise ValidationError(_("Select at least one criteria before searching"))

    def search_related_records(self):
        self.search_line_ids.unlink()
        domain = [('batch_id', '=', self.batch_id.id),
                  ('prefix_id', '=', self.prefix_id.id),
                  ('state', 'in', ['print', 'assignment']),
                  ('number', '>=', self.unit_booking_starting_id.number),
                  ('number', '<=', self.unit_booking_ending_id.number)]
        self.constrains()
        if self.is_qr_printed:
            domain.append(('is_qr_printed', '=', self.is_qr_printed))
        if self.is_receipt_printed:
            domain.append(('is_receipt_printed', '=', self.is_receipt_printed))
        if self.is_ledger_printed:
            domain.append(('is_ledger_printed', '=', self.is_ledger_printed))
        record_set = self.env['units.booking'].search(domain)
        if record_set:
            for record in record_set:
                self.search_line_ids = [(0, 0, {
                    'units_booking_id': record.id,
                })]
        if not record_set:
            raise ValidationError(_('Record not found'))

        return {
            'name': _('Search'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def create_issuance_req(self):
        if not self.search_line_ids:
            raise ValidationError(_('Search Record First Before Proceeding'))
        if self.is_qr_printed and not self.is_receipt_printed and not self.is_ledger_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_qr_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'

        elif not self.is_qr_printed and self.is_receipt_printed and not self.is_ledger_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_receipt_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'

        elif not self.is_qr_printed and not self.is_receipt_printed and self.is_ledger_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_ledger_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'

        elif self.is_qr_printed and self.is_receipt_printed and self.is_ledger_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_qr_printed = False
                    rec.units_booking_id.is_receipt_printed = False
                    rec.units_booking_id.is_ledger_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'
        elif self.is_qr_printed and self.is_receipt_printed and not self.is_ledger_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_qr_printed = False
                    rec.units_booking_id.is_receipt_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'
        elif not self.is_receipt_printed and self.is_ledger_printed and self.is_qr_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_qr_printed = False
                    rec.units_booking_id.is_ledger_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'
        elif self.is_receipt_printed and self.is_ledger_printed and not self.is_qr_printed:
            for rec in self.search_line_ids:
                if rec.units_booking_id:
                    rec.units_booking_id.is_receipt_printed = False
                    rec.units_booking_id.is_ledger_printed = False
                    rec.units_booking_id.is_printed = False
                    rec.units_booking_id.state = 'assignment'

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Printing State reset",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }


class UnitBookingResetPrintStateLine(models.TransientModel):
    _name = "unit.booking.reset.print.state.line"
    _description = "Unit Booking Reset Print State Line"

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product',
                                            related='units_booking_id.unit_category_type_id')
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id')
    search_id = fields.Many2one('unit.booking.reset.print.state')

    # boolean fields
    is_printed = fields.Boolean(default=False, related='units_booking_id.is_printed')
    is_qr_printed = fields.Boolean(default=False, related='units_booking_id.is_qr_printed')
    is_receipt_printed = fields.Boolean(default=False, related='units_booking_id.is_receipt_printed')
    is_ledger_printed = fields.Boolean(default=False, related='units_booking_id.is_ledger_printed')
    state = fields.Selection([], related='units_booking_id.state')
