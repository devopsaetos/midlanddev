from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FileQrScanning(models.TransientModel):
    _name = 'file.qr.scanning'
    _description = 'Buy Back File Qr Scanning'

    # models relational fields
    units_booking_id = fields.Many2one('units.booking')
    file_qr_line_ids = fields.One2many('file.qr.scanning.line', 'file_qr_id')
    issue_to_sub_dealer = fields.Boolean()
    buy_back_id = fields.Many2one('buy.back')

    @api.onchange('buy_back_id')
    def onchange_method(self):
        if self.issue_to_sub_dealer:
            return {
                'domain': {
                    'units_booking_id': [
                        ('sub_agent_id', '=', self.buy_back_id.partner_id.id),
                        ('state', 'in', ['allotment', 'issued']),
                        ('agent_id', '=', self.buy_back_id.main_dealer_id.id)]
                }
            }
        elif not self.issue_to_sub_dealer:
            return {
                'domain': {
                    'units_booking_id': [
                        ('state', 'in', ['allotment', 'issued']),
                        ('agent_id', '=', self.buy_back_id.partner_id.id),
                        ('sub_agent_id', '=', False)]
                }
            }

    @api.onchange('units_booking_id')
    def on_change_status(self):
        lines = []
        for rec in self.filtered(
                lambda self: self.units_booking_id.id not in self.file_qr_line_ids.mapped('units_booking_id.id')):
            if rec.units_booking_id:
                val = {'units_booking_id': rec.units_booking_id.id,
                       }
                lines.append((0, 0, val))
                rec.file_qr_line_ids = lines
            rec.units_booking_id = False
        self.units_booking_id = False

    def proceed_to_qr(self):
        for rec in self.file_qr_line_ids:
            if rec.units_booking_id not in self.buy_back_id.buy_back_line_ids.mapped('units_booking_id'):
                self.buy_back_id.buy_back_line_ids = [(0, 0, {
                    'units_booking_id': rec.units_booking_id.id,
                })]


class FileQrScanningLine(models.TransientModel):
    _name = 'file.qr.scanning.line'
    _description = 'Buy Back Open File Qr Scanning Line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='units_booking_id.unit_category_type_id')
    price = fields.Float(related='units_booking_id.sale_amount')
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment',
                                                related='units_booking_id.unit_booking_allotment_id')
    state = fields.Selection(related='units_booking_id.state')
    file_qr_id = fields.Many2one('file.qr.scanning')
