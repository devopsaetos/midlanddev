from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class ProjectProject(models.Model):
    _inherit = 'project.project'

    team_id = fields.Many2one('project.team', string='Team')
    category_id = fields.Many2one('project.category', string='Category')
    sub_category_id = fields.Many2one(
        'project.sub.category',
        string='Sub Category',
        domain="[('category_id', '=', category_id)]",
    )

    attach_pdf_required = fields.Boolean(related='category_id.attach_pdf', store=True)
    attach_pdf = fields.Binary(string='Attach PDF File')


    # team members reflected from team
    member_ids = fields.Many2many(
        comodel_name='res.users',
        string='Team Members',
        related='team_id.member_ids',
        readonly=True,
    )


    @api.onchange('category_id')
    def _onchange_category_id(self):
        self.sub_category_id = False

