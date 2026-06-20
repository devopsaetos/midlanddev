# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Sector(models.Model):
    _name = 'sector'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Sector"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ], readonly=True)

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]", copy=False)
    phase_id = fields.Many2one('society', 'Phase', required=True, copy=False)
    total_plots = fields.Integer()
    area = fields.Float()

    plot_inventory_ids = fields.One2many('plot.inventory', 'sector_id')
    file_ids = fields.One2many('file', 'sector_id')
    floor_planning_ids = fields.One2many('floor.planning', 'sector_id')
    company_id = fields.Many2one('res.company', string="Company", tracking=True)
    branch_id = fields.Many2one('res.company', string="Branch", tracking=True)

    floor_type = fields.Selection([
        ('residential', 'Residential'),
        ('parking', 'Parking'),
        ('commercial', 'Commercial'),
    ])

    @api.constrains('name', 'code', 'branch_id')
    def duplicate_data(self):
        for rec in self:
            if self.search([('name', '=', rec.name),
                            ('branch_id', '=', rec.branch_id.id), ('id', '!=', rec.id)]):
                raise ValidationError(
                    _(f"name: {rec.name} is already available with branch:{rec.branch_id.name}"))

    _sql_constraints = [
        ('code_uniq', 'unique (code)',
         'Code must be unique !'),
    ]

    @api.constrains('floor_planning_ids')
    def _check_floor_planning_area(self):
        if self.floor_planning_ids:
            planning_area = sum(self.floor_planning_ids.mapped('rent_area')) + sum(self.floor_planning_ids.mapped('common_area'))
            if planning_area > self.area:
                raise ValidationError('Planning area cannot exceed the "Floor Area" limit.')

    @api.onchange('society_id')
    def _phase_domain(self):
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
            }
        }

    @api.onchange('branch_id')
    def _branch_domain(self):
        return {'domain': {
            'branch_id': [('company_id', '=', self.env.company.id)],
        }
        }

    def write(self, val):

        if val.get('total_plots') and val.get('total_plots') < self.plot_inventory_ids.search_count([('sector_id','=',self.id)]):
            raise ValidationError("You could not decrease number of plots more than plots already in inventory")
        
        return super(Sector, self).write(val)
