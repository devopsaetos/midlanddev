from odoo import api, fields, models


class MaterialPurchaseRequisition(models.Model):
    _inherit = 'material.purchase.requisition'

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}


class RequisitionLine(models.Model):
    _inherit = 'requisition.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        store=True,
        domain="[('task_id', '=', parent.task_id)]",
    )

    @api.onchange('task_cost_sheet_id')
    def _onchange_action_operation(self):
        if self.requisition_id.task_id:
            return {'domain': {'task_cost_sheet_id': [('task_id', '=', self.requisition_id.task_id.id)]}}
        return {'domain': {'task_cost_sheet_id': []}}
