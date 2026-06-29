from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class Allotment(models.TransientModel):
    _name = 'allotment'
    _rec_name = 'allotment_type'
    _description = 'Allotment'

    allotment_type = fields.Selection([('new', 'New'), ('transfer', 'Transfer')], default='new', string='Allotment Type')
    date = fields.Date(string='Date')
    society_id = fields.Many2one('society', string='Society', required=True, domain="[('is_society', '=', True)]")
    phase_id = fields.Many2one('society', string='Phase', required=True, domain="[('is_society', '!=', True)]")
    sector_id = fields.Many2one('sector', string='Sector')
    category_id = fields.Many2one('plot.category', string='Category')
    size_id = fields.Many2one('unit.size', string='Size')
    file_id = fields.Many2one('file', string='File No')
    membership_id = fields.Many2one('res.member', string='Member No')
    unit_category_type_id = fields.Many2one('unit.category.type')
    search_line_ids = fields.Boolean(default=False)
    allotment_line_ids = fields.One2many('allotment.line', 'allotment_id')
    file_ids = fields.Many2many('file')

    @api.onchange('allotment_type')
    def _allotment_type(self):
        if self.allotment_type != 'new':
            return {'domain': {
                'file_id': [('history_ids', '!=', False)], }
            }
        else:
            return {'domain': {
                'file_id': [], }
            }

    @api.onchange('society_id', 'phase_id', 'sector_id', 'category_id', 'unit_category_type_id', 'size_id', 'file_id', 'membership_id')
    def _phase_domain(self):
        if self.membership_id:
            return {'domain': {
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('file_status', '=', 'approve'),
                             ('project_type', '=', 'housing_society'),
                             ('membership_id', '=', self.membership_id.id),
                             ]
            }
            }
        elif self.file_id:
            return {'domain': {
                'file_ids': [('id', '=', self.file_id.id)]
            }
            }
        elif self.sector_id:
            return {'domain': {
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('file_status', '=', 'approve'),
                             ('project_type', '=', 'housing_society'),
                             ('society_id', '=', self.society_id.id),
                             ('phase_id', '=', self.phase_id.id),
                             ('sector_id', '=', self.sector_id.id)
                             ]
            }
            }
        elif self.category_id:
            return {'domain': {
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('file_status', '=', 'approve'),
                             ('project_type', '=', 'housing_society'),
                             ('society_id', '=', self.society_id.id),
                             ('phase_id', '=', self.phase_id.id),
                             ('category_id', '=', self.category_id.id)
                             ]
            }
            }
        elif self.unit_category_type_id:
            return {'domain': {
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('file_status', '=', 'approve'),
                             ('project_type', '=', 'housing_society'),
                             ('society_id', '=', self.society_id.id),
                             ('phase_id', '=', self.phase_id.id),
                             ('unit_category_type_id', '=', self.unit_category_type_id.id)
                             ]
            }
            }
        elif self.size_id:
            return {'domain': {
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('file_status', '=', 'approve'),
                             ('project_type', '=', 'housing_society'),
                             ('society_id', '=', self.society_id.id),
                             ('phase_id', '=', self.phase_id.id),
                             ('size_id', '=', self.size_id.id)
                             ]
            }
            }
        else:
            return {'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'file_ids': [('inventory_id', '=', False), ('unit_number', '=', False),
                             ('payment_states', '=', 'close'),
                             ('project_type', '=', 'housing_society'),
                             ('society_id', '=', self.society_id.id),
                             ('phase_id', '=', self.phase_id.id),
                             ]
            }
            }


    def create_allotment_request(self):
        if not self.file_ids:
            raise UserError(_("Please Select the files"))
        else:
            lines = []

            for rec in self.file_ids:
                lines.append((0, 0, {
                    'file_id': rec.id,
                    'membership_id': rec.membership_id.id,
                    'tracking_no': rec.tracking_id,
                    'society_id': rec.society_id.id,
                    'phase_id': rec.phase_id.id,
                    'unit_category_type_id': rec.unit_category_type_id.id,
                    'category_id': rec.category_id.id,
                    'sector_id': rec.sector_id.id if rec.sector_id else False,
                    'street_id': rec.street_id.id if rec.street_id else False,
                    'inventory_id': rec.inventory_id.id if rec.street_id else False,
                    'preference_ids': [(6, 0, rec.preference_ids.ids)]
                }))

            self.env['allotment.batch'].create({
                'date': fields.Date.today(),
                'batch_responsibe_id': self.env.user.id,
                'batch_line_ids': lines})

    def run_allotment(self):

        for line in self.allotment_line_id:
            line.file_id.inventory_id = line.inventory_id.id


class AllotmentLine(models.TransientModel):
    _name = 'allotment.line'
    _description = 'Allotment Line'

    allotment_id = fields.Many2one('allotment')
    check = fields.Boolean(default=False)
    file_id = fields.Many2one('file', string='File No', readonly=True)
    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    tracking_no = fields.Char(string='Tracking ID', related='file_id.tracking_id', readonly=True)
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id',
                                 readonly=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id',
                               readonly=True)
    sector_id = fields.Many2one('sector', string='Sector')
    street_id = fields.Many2one('street', string='Street')
    inventory_id = fields.Many2one('plot.inventory', string='File Unit')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product', readonly=True)
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id', readonly=True)
    preference_ids = fields.Many2many('preference', readonly=True)
