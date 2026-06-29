from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from lxml import etree as ET


class UnitBookingIssuance(models.Model):
    _name = 'unit.booking.issuance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Unit Booking Issuance'

    name = fields.Char(copy=False, readonly=True, index=True, tracking=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)
    unit_selection_option = fields.Selection([('scanning', 'Scanning'), ('range', 'Range')], tracking=True)
    issue_to_subagent = fields.Boolean()
    from_allotment_to_issuance = fields.Boolean(default=False)
    date = fields.Date('Date', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Agent', required=True, tracking=True)
    partner_subagent_id = fields.Many2one('res.partner', string='Sub Agent', tracking=True)
    unit_batch_id = fields.Many2one('unit.batch.generation', string='Batch', tracking=True)
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment', store=True)
    no_of_units = fields.Integer(compute='_compute_total_units', store=True)
    unit_booking_issuance_line_ids = fields.One2many('unit.booking.issuance.line', 'unit_booking_issuance_id')

    @api.depends('unit_booking_issuance_line_ids')
    def _compute_total_units(self):
        for rec in self:
            rec.no_of_units = len(rec.unit_booking_issuance_line_ids.mapped('units_booking_id'))

    def open_file_issuance_scanning(self):
        return {
            'name': _('QR') if self.unit_selection_option == 'scanning' else _('Range'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'open.file.qr.reading',
            'type': 'ir.actions.act_window',
            'context': {
                'default_issuance_id': self.id,
                'default_batch_id': self.unit_batch_id.id,
                'default_allotment_id': self.unit_booking_allotment_id.id,
                'default_unit_selection_option': self.unit_selection_option,
                'from_issuance': True,
            },
            'target': 'new'
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('booking.issuance') or _('New')
        result = super().create(vals_list)
        return result

    def approve_issuance(self):
        if not self.unit_booking_issuance_line_ids:
            raise ValidationError('Please add details to approve.')

        for rec in self.unit_booking_issuance_line_ids:
            rec.units_booking_id.state = 'issued'
            rec.units_booking_id.agent_id = self.partner_id.id
            rec.units_booking_id.sub_agent_id = self.partner_subagent_id.id if self.issue_to_subagent else False
            rec.units_booking_id.history_ids = [(0, 0, {
                'state': 'issued',
                'date': fields.Date.today(),
                'print_state': '',
                'partner_id': self.partner_subagent_id.id if self.issue_to_subagent else self.partner_id.id,
            })]
        self.state = 'approve'

    def cancel_issuance(self):
        for rec in self:
            rec.state = 'cancel'

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(UnitBookingIssuance, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                               submenu=submenu)
        try:
            check_from_allotment = self.env.context['from_allotment_to_issuance']
        except:
            check_from_allotment = False
        if not check_from_allotment:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)
        if not check_from_allotment:
            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

        return res


class UnitBookingIssuanceLine(models.Model):
    _name = 'unit.booking.issuance.line'
    _description = 'Unit Booking Issuance Line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    price = fields.Float()
    batch_id = fields.Many2one('unit.batch.generation')

    unit_booking_issuance_id = fields.Many2one('unit.booking.issuance')
