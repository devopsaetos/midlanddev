from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectCategory(models.Model):
    _name = 'project.category'
    _description = 'Project Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string='Code', size=10, index=True, copy=False)
    attach_pdf = fields.Boolean(string='Attach PDF')
    stage_ids = fields.Many2many(
        comodel_name='project.project.stage',
        string='Project Stages',
    )
    sub_category_ids = fields.One2many(
        'project.sub.category',
        'category_id',
        string='Sub Categories',
    )
    sub_category_count = fields.Integer(
        string='# Sub Categories',
        compute='_compute_sub_category_count',
    )

    _sql_constraints = [
        ('project_category_code_unique', 'UNIQUE(code)', 'Project category code must be unique.'),
    ]

    def _compute_sub_category_count(self):
        data = self.env['project.sub.category']._read_group(
            [('category_id', 'in', self.ids)],
            ['category_id'],
            ['__count'],
        )
        counts = {cat.id: count for cat, count in data}
        for rec in self:
            rec.sub_category_count = counts.get(rec.id, 0)

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            rec.code = self._generate_code(rec.name)

    @api.model
    def _generate_code(self, text):
        if not text:
            return ''
        parts = text.split()
        if len(parts) == 1:
            return parts[0][:3].upper()
        return ''.join(p[0].upper() for p in parts)

    @api.constrains('stage_ids')
    def _check_stage_ids(self):
        for rec in self:
            if not rec.stage_ids:
                raise UserError(_('Stages cannot be empty for category "%s".') % rec.name)

    def unlink(self):
        linked_ids = self.env['project.project'].search([]).mapped('category_id').ids
        for rec in self:
            if rec.id in linked_ids:
                raise UserError(
                    _('You cannot delete category "%s" because it is linked to a project.') % rec.name
                )
        return super().unlink()


class ProjectSubCategory(models.Model):
    _name = 'project.sub.category'
    _description = 'Project Sub Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'category_id, name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(string='Code', size=10, index=True, copy=False)
    category_id = fields.Many2one(
        'project.category',
        string='Category',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        ('project_sub_category_code_unique', 'UNIQUE(code)', 'Project sub-category code must be unique.'),
    ]

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            rec.code = self._generate_code(rec.name)

    @api.model
    def _generate_code(self, text):
        if not text:
            return ''
        parts = text.split()
        if len(parts) == 1:
            return parts[0][:3].upper()
        return ''.join(p[0].upper() for p in parts)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') and vals.get('name'):
                vals['code'] = self._generate_code(vals['name'])
        return super().create(vals_list)

    def unlink(self):
        linked_ids = self.env['project.project'].search([]).mapped('sub_category_id').ids
        for rec in self:
            if rec.id in linked_ids:
                raise UserError(
                    _('You cannot delete sub-category "%s" because it is linked to a project.') % rec.name
                )
        return super().unlink()
