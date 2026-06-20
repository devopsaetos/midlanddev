# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class InventoryCreation(models.Model):
    _name = "create.inventory"
    _description = "Create Inventory"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char('Sequence No', required=True, copy=False, index=True, readonly=True,
                       default=lambda self: _('New'))
    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', required=True)
    sector_id = fields.Many2one('sector', required=True)
    inventory_line = fields.One2many('inventory.line', 'inventory_id')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submit For Approval'),
        ('approved', 'Approved'),
    ], string='Status', default='draft')

    total_inventory = fields.Integer(compute='_compute_line_inventory')



    @api.model
    def create(self, vals_list):
        vals_list = [vals_list] if not isinstance(vals_list, list) else vals_list
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("create.inventory") or _('New')
        return super(InventoryCreation, self).create(vals_list)

    @api.depends('inventory_line')
    def _compute_line_inventory(self):
        for rec in self:
            if rec.inventory_line:
                rec.total_inventory = len(rec.inventory_line)
            else:
                rec.total_inventory = 0


    def submit_bulk_inventory(self):
        for rec in self:
            rec.write({'status': 'submitted'})

    def select_all_inventory_lines(self):
        for rec in self:
            if rec.inventory_line:
                for line in rec.inventory_line:
                    line.is_select = True


    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
            }
        }


    def reset_to_draft(self):
        for rec in self:
            rec.write({'status': 'draft'})

    def create_bulk_inventory(self):
        selected_lines = self.inventory_line.filtered(lambda l: l.is_select)
        if not selected_lines:
            raise ValidationError(_("Please select at least one line before approving."))

        zero_nop_lines = selected_lines.filtered(lambda l: l.nop <= 0)
        if zero_nop_lines:
            raise ValidationError(_("NOP (Number of Plots) must be greater than 0 for all selected lines."))

        inventory = self.env["plot.inventory"]
        inventory_limit = inventory.search_count([('sector_id', '=', self.sector_id.id)]) + sum(selected_lines.mapped('nop'))
        if inventory_limit > self.sector_id.total_plots:
            raise ValidationError(_("Plot inventory limit exceeding the allowed limit"))

        for line in selected_lines:
            for rec in range(0, line.nop):
                inventory.create({
                    "society_id": self.society_id.id,
                    "phase_id": self.phase_id.id,
                    "sector_id": self.sector_id.id,
                    "street_id": line.street_id.id,
                    "category_id": line.category_id.id,
                    "size_id": line.size_id.id,
                    "unit_category_type_id": line.unit_category_type_id.id,
                    "unit_class_id": line.unit_class_id.id,
                    "project_type": self.project_type
                })

        self.write({'status': 'approved'})


class InventoryLine(models.Model):
    _name = "inventory.line"
    _rec_name = 'nop'
    _description = "Inventory Line"


    is_select = fields.Boolean(default=False)
    street_id = fields.Many2one('street')
    nop = fields.Integer('NOP')
    category_id = fields.Many2one('plot.category', 'Category', required=True)
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product', required=True)
    unit_class_id = fields.Many2one('unit.class', 'Type', required=True)
    size_id = fields.Many2one('unit.size', 'Size')
    inventory_id = fields.Many2one('create.inventory')

    @api.onchange('street_id')
    def _street_id(self):
        return {
            'domain': {
                'street_id': [('sector_id', '=', self.inventory_id.sector_id.id)],
            }
        }





