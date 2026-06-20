from odoo import api, fields, models, _


class ProjectTaskBudgetExt(models.Model):
    _inherit = 'project.task'

    include_budget = fields.Boolean(string='Include For Budgets')
    task_budget_ids = fields.One2many('task.budget', 'task_id', string='Task Budgets')
    budget_count = fields.Integer(string='# Task Budgets', compute='_compute_budget_count')

    def _compute_budget_count(self):
        data = self.env['task.budget']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for rec in self:
            rec.budget_count = counts.get(rec.id, 0)

    def button_view_task_budget(self):
        self.ensure_one()
        return {
            'name': _('Task Budget'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'task.budget',
            'domain': [('task_id', '=', self.id)],
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'active_id': self.id,
            },
        }
