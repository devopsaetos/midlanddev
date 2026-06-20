from odoo import fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    total_po = fields.Integer(string='Purchase Orders', compute='_compute_purchase_order')

    def _compute_purchase_order(self):
        data = self.env['purchase.order']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.total_po = counts.get(task.id, 0)

    def button_purchase_order(self):
        self.ensure_one()
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('task_id', '=', self.id)],
        }
