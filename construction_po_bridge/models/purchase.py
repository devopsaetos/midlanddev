from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        store=True,
        domain="[('task_id', '=', parent.task_id)]",
    )

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move)
        res['task_cost_sheet_id'] = self.task_cost_sheet_id.id or False
        return res
