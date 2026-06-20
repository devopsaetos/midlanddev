# -*- coding: utf-8 -*-

from odoo import models, fields, api


class DemarcatedArea(models.Model):
    _name = 'demarcated.area'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'inventory_id'
    _description = "Demarcated Area"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    inventory_id = fields.Many2one('plot.inventory', required=True)
    checker_id = fields.Many2one('res.partner', 'Checked By')
    surveyor_id = fields.Many2one('res.partner', 'Surveyor')
    user_id = fields.Many2one('res.users', 'Entered By', default=lambda self: self.env.user.id)
    total_area = fields.Float('Total Area')
    actual_area = fields.Float('Actual Area', copy=False)
    access_short = fields.Float('Access/short', compute='_compute_area_def')

    dimension_line = fields.One2many('plot.dimension', 'demarcation_id')
    plot_image = fields.Binary(attachment=True, string='Plot Image')

    @api.depends('total_area', 'actual_area')
    def _compute_area_def(self):
        self.access_short = 0.0
        if self.actual_area:
            self.access_short = (self.actual_area - self.total_area) or 0.0

    @api.onchange('inventory_id', 'actual_area')
    def _plot_inventory(self):
        self.total_area = self.inventory_id.size_id.standard_area

    _sql_constraints = [
        ('inventory_id_uniq', 'unique (inventory_id)', 'The Demarcated file if this plot is already exist!'),
    ]


class PlotDimension(models.Model):
    _name = 'plot.dimension'
    _description = "Plot Dimension"

    dimension = fields.Selection([
        ('long_dimension', 'Long Dimension'),
        ('short_dimension', 'Short Dimension')], required=True)
    name = fields.Char()
    value = fields.Char()
    bounded_by = fields.Char()
    cardinal = fields.Selection([
        ('east', 'E'),
        ('south_east', 'SE'),
        ('south', 'S'),
        ('south_west', 'SW'),
        ('west', 'W'),
        ('north_west', 'NW'),
        ('north', 'N'),
        ('north_east', 'NE')], string='Cardinal Direction')

    demarcation_id = fields.Many2one('demarcated.area')
