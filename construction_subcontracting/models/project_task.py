from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_subcontract_id = fields.Many2one('task.subcontract', string='Subcontract')
    subcontract_count = fields.Integer(string='# Subcontracts', compute='_compute_subcontract_count')

    def _compute_subcontract_count(self):
        data = self.env['task.subcontract']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for rec in self:
            rec.subcontract_count = counts.get(rec.id, 0)

    def action_create_subcontract(self):
        self.ensure_one()
        view_id = self.env.ref('construction_subcontracting.task_subcontract_form_view').id
        return {
            'name': _('Sub Contract'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'task.subcontract',
            'target': 'new',
            'context': {
                'from_task': True,
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

    def button_view_subcontract(self):
        self.ensure_one()
        return {
            'name': _('Sub Contracts'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'task.subcontract',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }
