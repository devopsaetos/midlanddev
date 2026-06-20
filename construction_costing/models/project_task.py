from odoo import fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    cost_sheet_count = fields.Integer(string='Cost Sheets', compute='_compute_cost_sheet_count')

    def _compute_cost_sheet_count(self):
        data = self.env['task.cost.sheet']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.cost_sheet_count = counts.get(task.id, 0)

    def action_create_costsheet(self):
        self.ensure_one()
        if self.cost_sheet_count > 0:
            raise UserError(_('You cannot create more than one Cost Sheet per task.'))
        view_id = self.env.ref('construction_costing.task_cost_sheet_form_view').id
        return {
            'name': _('Cost Sheet'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'task.cost.sheet',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def button_view_costsheet(self):
        self.ensure_one()
        return {
            'name': _('Cost Sheets'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'task.cost.sheet',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }
