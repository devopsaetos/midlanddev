from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError


class AllotmentRequest(models.Model):
    _name = 'allotment.request'
    _description = 'Allotment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char("Allotment Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    date = fields.Date('Date', readonly=True, tracking=True)
    file_id = fields.Many2one('file')
    membership_id = fields.Many2one('res.member', related='file_id.membership_id', string='Member No',
                                    tracking=True)
    membership_name = fields.Char(string='Name', related='membership_id.name')

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='file_id.society_id', readonly=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='file_id.phase_id', readonly=True)

    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id', readonly=True)
    unit_category_type_id = fields.Many2one('unit.category.type', related='file_id.unit_category_type_id',
                                            readonly=True, string='Product')

    sector_id = fields.Many2one('sector', string='Sector', required=True, )
    street_id = fields.Many2one('street', required=True, string='Street')
    inventory_id = fields.Many2one('plot.inventory', required=True, string='File Unit')
    size_id = fields.Many2one('unit.size', 'Size', related="inventory_id.size_id")
    unit_number = fields.Char(related='inventory_id.name', readonly=True)

    state = fields.Selection([
        ('draft', 'Submit'),
        ('preview', 'Review'),
        ('approve', 'Approved'),
        ('print', 'Printed'),
        ('issued', 'Issued'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    batch_id = fields.Many2one('allotment.request.batch')

    approved_date = fields.Date('Aprroved Date', readonly=True)
    approved_responsibe_id = fields.Many2one('res.users', 'Aprroved By', readonly=True)

    issued_date = fields.Date('Issued Date', readonly=True)
    issued_responsibe_id = fields.Many2one('res.users', 'Issued By', readonly=True)

    printed_date = fields.Date('Printed Date', readonly=True)
    printed_responsibe_id = fields.Many2one('res.users', 'Printed By', readonly=True)

    canceled_date = fields.Date('Canceled Date', readonly=True)
    canceled_responsibe_id = fields.Many2one('res.users', 'Cancelled By', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("allotment.request.sequence") or _('New')
        return super().create(vals_list)

    @api.onchange('phase_id', 'street_id')
    def _inventory_domain(self):
        return {'domain': {
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'inventory_id': [('street_id', '=', self.street_id.id)]
        }
        }

    def action_preview(self):
        self.ensure_one()
        return self.write({'stata': 'preview'})

    def action_approve(self):
        self.ensure_one()
        return self.write({'stata': 'approve'})

    def action_print(self):
        self.ensure_one()
        return self.write({'stata': 'print'})

    def action_issue(self):
        self.ensure_one()
        return self.write({'stata': 'issued'})

    def action_cancel(self):
        self.ensure_one()
        return self.write({'stata': 'cancel'})
