from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    issue_requisition_count = fields.Integer(
        string='Issue Requisitions',
        compute='_compute_issue_requisition_count',
    )
    stock_transaction_count = fields.Integer(
        string='Stock Transactions',
        compute='_compute_stock_transaction_count',
    )

    def _compute_issue_requisition_count(self):
        data = self.env['issue.requistion']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.issue_requisition_count = counts.get(task.id, 0)

    def _compute_stock_transaction_count(self):
        data = self.env['stock.transaction']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'],
        )
        counts = {task.id: count for task, count in data}
        for task in self:
            task.stock_transaction_count = counts.get(task.id, 0)

    def action_create_issue_requisition(self):
        self.ensure_one()
        return {
            'name': _('Issue Requisition'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'issue.requistion',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            },
        }

    def action_create_stock_transaction(self):
        self.ensure_one()
        return {
            'name': _('Stock Transaction'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'stock.transaction',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            },
        }

    def button_view_issue_requisitions(self):
        self.ensure_one()
        return {
            'name': _('Issue Requisitions'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'issue.requistion',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }

    def button_view_stock_transactions(self):
        self.ensure_one()
        return {
            'name': _('Stock Transactions'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'stock.transaction',
            'domain': [('task_id', '=', self.id)],
            'context': dict(self._context),
        }
