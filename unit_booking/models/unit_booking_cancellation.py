from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from lxml import etree as ET


class UnitBookingCancellation(models.Model):
    _name = 'unit.booking.cancellation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Unit Booking Cancellation'

    name = fields.Char(copy=False, readonly=True, index=True, tracking=True, default=lambda self: _('New'))
    request_type = fields.Selection([('refund', 'Refund'),
                                     ('cancellation', 'Cancellation')], default='cancellation')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)
    unit_selection_option = fields.Selection([
        ('scanning', 'Scanning'), ('range', 'Range')
    ])
    date = fields.Date('Date', tracking=True, default=fields.Date.today())
    agent_id = fields.Many2one('res.partner', string='Dealer', related='unit_booking_allotment_id.partner_id',
                               tracking=True, store=True)
    unit_batch_id = fields.Many2one('unit.batch.generation', related='unit_booking_allotment_id.unit_batch_id',
                                    string='Batch', tracking=True, store=True)
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment', string='Allotment')
    unit_booking_cancellation_line_ids = fields.One2many('unit.booking.cancellation.line',
                                                         'unit_booking_cancellation_id')

    def open_file_cancellation_scanning(self):
        return {
            'name': _('QR') if self.unit_selection_option == 'scanning' else _('Range'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'open.file.qr.reading',
            'type': 'ir.actions.act_window',
            'context': {
                'default_unit_booking_cancellation_id': self.id,
                'default_allotment_id': self.unit_booking_allotment_id.id,
                'default_batch_id': self.unit_batch_id.id,
                'default_unit_selection_option': self.unit_selection_option,
            },
            'target': 'new'
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('unit.cancellation.request.sequence') or _('New')
        result = super().create(vals_list)
        return result

    def approve_cancellation(self):
        if not self.unit_booking_cancellation_line_ids:
            raise ValidationError('Please add details to approve.')

        for rec in self.unit_booking_cancellation_line_ids:
            rec.units_booking_id.state = 'open'
            rec.units_booking_id.agent_id = False
            rec.units_booking_id.sub_agent_id = False
            # rec.units_booking_id.history_ids = [(0, 0, {
            #     'state': 'issued',
            #     'date': fields.Date.today(),
            #     'print_state': '',
            #     'partner_id': self.partner_subagent_id.id if self.issue_to_subagent else self.partner_id.id,
            # })]
        self.state = 'approve'

    def cancel_cancellation(self):
        for rec in self:
            rec.state = 'cancel'


class UnitBookingCancellationLine(models.Model):
    _name = 'unit.booking.cancellation.line'
    _description = 'Unit Booking Cancellation Line'

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

    unit_booking_cancellation_id = fields.Many2one('unit.booking.cancellation')
