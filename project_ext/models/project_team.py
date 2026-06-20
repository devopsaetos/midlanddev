from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTeam(models.Model):
    _name = 'project.team'
    _description = 'Project Team'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    description = fields.Html()
    email = fields.Char(string='E-mail')
    default_hrs = fields.Float(string='Default Daily Hours', default=8)
    image = fields.Image(
        string='Image',
        max_width=1024,
        max_height=1024,
        attachment=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    member_ids = fields.Many2many(
        comodel_name='res.users',
        relation='project_agile_team_member_rel',
        column1='team_id',
        column2='member_id',
        string='Team Members',
        required=True,
    )
    project_ids = fields.One2many(
        'project.project',
        'team_id',
        string='Projects',
    )
    project_count = fields.Integer(
        string='# Projects',
        compute='_compute_project_count',
    )
    product_owner_ids = fields.Many2many(
        comodel_name='res.users',
        string='Project Owners',
        compute='_compute_product_owner_ids',
    )

    def _compute_project_count(self):
        data = self.env['project.project']._read_group(
            [('team_id', 'in', self.ids)],
            ['team_id'],
            ['__count'],
        )
        counts = {team.id: count for team, count in data}
        for rec in self:
            rec.project_count = counts.get(rec.id, 0)

    @api.depends('project_ids', 'project_ids.user_id')
    def _compute_product_owner_ids(self):
        for rec in self:
            rec.product_owner_ids = rec.project_ids.mapped('user_id')

    def unlink(self):
        linked_ids = self.env['project.project'].search([]).mapped('team_id').ids
        for rec in self:
            if rec.id in linked_ids:
                raise UserError(
                    _('You cannot delete team "%s" because it is linked to a project.') % rec.name
                )
        return super().unlink()

    @api.constrains('member_ids')
    def _check_members(self):
        for rec in self:
            if not rec.member_ids:
                raise UserError(_('Please add at least one member to the team.'))

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams.mapped('member_ids').fix_team_id()
        return teams

    def write(self, vals):
        prev_members = {rec.id: rec.member_ids.ids for rec in self} if 'member_ids' in vals else {}
        res = super().write(vals)
        if 'member_ids' in vals:
            all_member_ids = set()
            for rec in self:
                prev = set(prev_members.get(rec.id, []))
                curr = set(rec.member_ids.ids)
                all_member_ids |= prev ^ curr
            if all_member_ids:
                self.env['res.users'].browse(list(all_member_ids)).fix_team_id()
        return res

    def action_view_projects(self):
        self.ensure_one()
        return {
            'name': _('Projects'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
        }

    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if domain is None:
            domain = []
        if 'filter_by_team_id' in self.env.context and self.env.context.get('filter_by_team_id'):
            domain = [('id', '=', self.env.context['filter_by_team_id'])] + domain
        return super().name_search(name, domain=domain, operator=operator, limit=limit)
