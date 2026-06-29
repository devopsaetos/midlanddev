from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class UnitsPlatter(models.Model):
    _name = 'units.platter'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Units Platter'

    project_type = fields.Selection([('skyscraper', 'Skyscraper'), ('housing_society', 'Housing Society')],
                                    default="housing_society")
    unit_selection_option = fields.Selection([('scanning', 'Scanning'), ('range', 'Range')
                                              ])
    name = fields.Char(copy=False, tracking=True, default=lambda self: _('New'))
    code = fields.Char(copy=False, readonly=True)

    # models relational fields
    unit_batch_id = fields.Many2one('unit.batch.generation', string='Batch')
    platter_line_ids = fields.One2many('units.platter.line', 'unit_platter_id')
    platter_size = fields.Integer('Platter Size', size=100)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)
    total_files = fields.Integer(string='Total Files', compute='_compute_total_files')
    available_files = fields.Integer(string='Available Files', compute='_compute_available_files')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string='Company')


    def active_platter(self):
        for rec in self:
            rec.state = 'active'

    def close_platter(self):
        for rec in self:
            rec.state = 'closed'

    def cancel_platter(self):
        for rec in self:
            rec.state = 'cancel'

    def open_files_addition(self):
        return {
            'name': _('QR') if self.unit_selection_option == 'scanning' else _('Range'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'open.file.qr.reading',
            'type': 'ir.actions.act_window',
            'context': {
                'default_batch_id': self.unit_batch_id.id,
                'default_platter_id': self.id,
                'default_unit_selection_option': self.unit_selection_option,
                'from_platter': True,
            },
            'target': 'new'
        }

    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.name and record.name != 'New':
                name = "%s - %s" % (record.name, record.code)
            result.append((record.id, name))
        return result

    @api.depends('platter_line_ids')
    def _compute_total_files(self):
        for rec in self:
            total = 0
            for lines in rec.platter_line_ids:
                total += 1
            # rec.total_files = len(rec.platter_line_ids)
            rec.total_files = total

    def _compute_available_files(self):
        for rec in self:
            rec.available_files = 0
            # rec.no_of_issued_files = len(rec.env['units.booking'].search([('unit_booking_allotment_id', '=', rec.id),
            #                                                               ('state', '=', 'file_created')]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('units.platter.sequence') or _('New')
        result = super().create(vals_list)
        return result


class UnitsPlatterLine(models.Model):
    _name = 'units.platter.line'
    _description = 'Units Platter Line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    price = fields.Float()
    batch_id = fields.Many2one('unit.batch.generation')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('assignment', 'Assignment'),
        ('print', 'Print'),
        ('allotment', 'Allotment'),
        ('issued', 'Issued'),
        ('file_created', 'File Created'),
        ('balloting', 'Balloting')
    ], related='units_booking_id.state', store=True)
    unit_platter_id = fields.Many2one('units.platter')
