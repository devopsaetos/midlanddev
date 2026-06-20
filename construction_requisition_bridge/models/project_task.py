from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    material_requisition_count = fields.Integer(
        string='Material Requisitions',
        compute='_compute_material_requisition_count',
    )
    purchase_requisition_count = fields.Integer(
        string='Purchase Requisitions (RFQ)',
        compute='_compute_purchase_requisition_count',
    )

    def _compute_material_requisition_count(self):
        data = self.env['material.purchase.requisition']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.material_requisition_count = counts.get(task.id, 0)

    def _compute_purchase_requisition_count(self):
        data = self.env['requisition.order']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.purchase_requisition_count = counts.get(task.id, 0)

    def action_create_material_requisition(self):
        self.ensure_one()
        return {
            'name': _('Material Requisition'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'material.purchase.requisition',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            },
        }

    def action_create_purchase_requisition(self):
        self.ensure_one()
        return {
            'name': _('Purchase Requisition'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'requisition.order',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            },
        }

    def button_view_material_requisitions(self):
        self.ensure_one()
        return {
            'name': _('Material Requisitions'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'material.purchase.requisition',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }

    def button_view_purchase_requisitions(self):
        self.ensure_one()
        return {
            'name': _('Purchase Requisitions'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'requisition.order',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }
