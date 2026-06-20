from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    overhead_type = fields.Selection([
        ('labour', 'Labour'),
        ('material', 'Material'),
    ], string='Overhead Application Basis')
    rate = fields.Float(string='Absorption Rate (%)')
