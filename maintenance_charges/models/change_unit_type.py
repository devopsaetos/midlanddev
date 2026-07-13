# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ChangeUnitType(models.Model):
    _name = 'change.unit.type'
    _description = "Change Unit Type"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submit'),
        ('approve', 'Approve'),
        ('cancel', 'Cancel'),
    ], default='draft', tracking=True)

    name = fields.Char('Sequence Number', required=True, copy=False, index=True, readonly=True, default=lambda self: _('New'))
    date = fields.Date(default=fields.Date.today())
    tracking_id = fields.Char()
    file_id = fields.Many2one('file', string='File No')
    membership_id = fields.Many2one('res.partner', string='Member No')  # domain="[('is_member','=',1)]" removed: is_member is not a field on res.partner anywhere in this project
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector', readonly=False)
    street_id = fields.Many2one('street', readonly=False)

    inventory_id = fields.Many2one('plot.inventory', 'Plot No.')
    category_id = fields.Many2one('plot.category', store=True, string='Category', related="inventory_id.category_id", readonly=False)
    size_id = fields.Many2one('unit.size', 'Size', related="inventory_id.size_id", store=True)
    unit_category_type_id = fields.Many2one('unit.category.type', related="inventory_id.unit_category_type_id", store=True)
    unit_class_id = fields.Many2one('unit.class', related="inventory_id.unit_class_id", store=True, tracking=True)
    new_unit_class_id = fields.Many2one('unit.class', string="Select Type", tracking=True)
    unit_change_typy_line_ids = fields.One2many('change.unit.type.lines', 'unit_change_type_id', string='Change Type')

    from_app = fields.Boolean()
    submit_app = fields.Boolean(default=False)
    approved_app = fields.Boolean(default=False)

    @api.onchange('society_id', 'phase_id', 'sector_id', 'street_id')
    def _phase_domain(self):
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'street_id': [('sector_id', '=', self.sector_id.id)],
            'inventory_id': [('street_id', '=', self.street_id.id)]
        }
        }

    @api.onchange('inventory_id')
    def _onchange_inventory(self):
        if self.inventory_id:
            file = self.env['file'].search([('inventory_id', '=', self.inventory_id.id)])
            self.file_id = file.id
            self.membership_id = file.membership_id.id
            self.tracking_id = file.tracking_id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code("change.unit.type") or _('New')

        record = super(ChangeUnitType, self).create(vals)

        return record

    def button_submit(self):
        self.submit_app = True
        for rec in self:
            rec.state = 'submit'

    def button_approve(self):
        self.approved_app = True
        for record in self.unit_change_typy_line_ids:
            record.file_id.unit_class_id = record.new_unit_class_id.id
            record.inventory_id.unit_class_id = record.new_unit_class_id.id
            record.file_id.state = 'available'
        self.state = 'approve'
        # self.file_id.unit_class_id = self.new_unit_class_id.id
        # self.inventory_id.unit_class_id = self.new_unit_class_id.id
        # self.file_id.state = 'available'
        # self.state = 'approve'

    def button_cancel(self):
        self.state = 'cancel'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record when it is approved!'))

        return super(ChangeUnitType, self).unlink()


class ChangeUnitTypeLines(models.Model):
    _name = 'change.unit.type.lines'
    _description = 'Change Unit Type Lines'

    inventory_id = fields.Many2one('plot.inventory', 'Plot No.')
    category_id = fields.Many2one('plot.category', store=True, string='Category', related="inventory_id.category_id", readonly=False)
    size_id = fields.Many2one('unit.size', 'Size', related="inventory_id.size_id", store=True)
    unit_category_type_id = fields.Many2one('unit.category.type', related="inventory_id.unit_category_type_id", store=True)
    unit_class_id = fields.Many2one('unit.class', related="inventory_id.unit_class_id", store=True, tracking=True)
    tracking_id = fields.Char()
    file_id = fields.Many2one('file', string='File No')
    membership_id = fields.Many2one('res.partner', string='Member No')  # domain="[('is_member','=',1)]" removed: is_member is not a field on res.partner anywhere in this project
    new_unit_class_id = fields.Many2one('unit.class', string="Select Type", tracking=True)
    unit_change_type_id = fields.Many2one('change.unit.type', string="Unit Change Type")

    @api.onchange('inventory_id', 'unit_change_type_id.street_id', 'unit_change_type_id.sector_id')
    def _check_domain(self):
        print('domain')
        domain = {}
        if self.unit_change_type_id.street_id:
            domain['inventory_id'] = [('street_id', '=', self.unit_change_type_id.street_id.id)]
        return {'domain': domain}

    @api.onchange('inventory_id')
    def _inventory_data(self):
        for record in self:
            if record.inventory_id:
                file = self.env['file'].search([('inventory_id', '=', record.inventory_id.id)])
                record.file_id = file.id
                record.membership_id = file.membership_id.id
                record.tracking_id = file.tracking_id
