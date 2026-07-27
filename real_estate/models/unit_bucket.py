# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class UnitBucket(models.Model):
    _name = 'unit.bucket'
    _description = 'Unit Bucket'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True)
    code = fields.Char()
    # A bucket groups plots of different sizes/streets under one package
    # (e.g. Bucket 1 = 10 units of 5 Marla + 5 units of 3 Marla + 20 units
    # of 3.5 Marla) - plot.inventory.bucket_id is the other side of this.
    plot_inventory_ids = fields.One2many('plot.inventory', 'bucket_id', string='Units')
    total_units = fields.Integer(compute='_compute_total_units')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Code must be unique'),
    ]

    @api.depends('plot_inventory_ids')
    def _compute_total_units(self):
        for rec in self:
            rec.total_units = len(rec.plot_inventory_ids)

    def action_view_units(self):
        self.ensure_one()
        return {
            'name': _('Units'),
            'type': 'ir.actions.act_window',
            'res_model': 'plot.inventory',
            'view_mode': 'list,form',
            'domain': [('bucket_id', '=', self.id)],
            'context': {'default_bucket_id': self.id},
        }
