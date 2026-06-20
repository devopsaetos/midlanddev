from odoo import fields, models, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    team_ids = fields.Many2many(
        comodel_name='project.team',
        relation='project_agile_team_member_rel',
        column1='member_id',
        column2='team_id',
        string='Enrolled in Teams',
    )
    team_id = fields.Many2one(
        comodel_name='project.team',
        string='Current Team',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'team_ids' in vals:
            self.fix_team_id()
        return res

    def fix_team_id(self):
        for record in self:
            if record.team_id not in record.team_ids:
                record.sudo().team_id = record.team_ids[:1]

    def change_team(self, team_id):
        self.ensure_one()
        if self.id == self.env.user.id and self.team_id in self.team_ids:
            self.sudo().team_id = team_id
        else:
            raise AccessError(_('You are only allowed to change your own current team.'))

    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if domain is None:
            domain = []
        if self.env.context.get('filter_by_team_id'):
            domain = [('team_ids', 'in', [self.env.context['filter_by_team_id']])] + domain
        return super().name_search(name, domain=domain, operator=operator, limit=limit)
