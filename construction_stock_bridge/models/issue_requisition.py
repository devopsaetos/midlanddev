from odoo import api, fields, models


class IssueRequistion(models.Model):
    _inherit = 'issue.requistion'

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    def _get_stock_transaction_lines(self):
        lines = []
        for line in self.line_ids:
            rec_dict = {
                'product_id': line.product_id.id,
                'product_uom_id': line.uom_id.id,
                'scrap_qty': line.quantity,
                'total_req_qty': line.quantity,
                'check_req': True,
                'analytic_account_id': line.analytic_account_id.id or False,
                'memo_text': line.memo_text or False,
                'task_cost_sheet_id': line.task_cost_sheet_id.id or False,
            }
            lines.append((0, 0, rec_dict))
        return lines

    def _get_stock_transaction(self):
        res = super()._get_stock_transaction()
        res['project_id'] = self.project_id.id or False
        res['task_id'] = self.task_id.id or False
        return res


class IssueRequistionLine(models.Model):
    _inherit = 'issue.requistion.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        store=True,
        domain="[('task_id', '=', parent.task_id)]",
        options="{'no_quick_create': True, 'no_create_edit': True}",
    )

    @api.onchange('task_cost_sheet_id')
    def _onchange_task_cost_sheet_id(self):
        if self.task_cost_sheet_id:
            self.analytic_account_id = self.task_cost_sheet_id.analytic_account_id
        if self.issue_requistion_id.task_id:
            return {'domain': {'task_cost_sheet_id': [('task_id', '=', self.issue_requistion_id.task_id.id)]}}
        return {'domain': {'task_cost_sheet_id': []}}
