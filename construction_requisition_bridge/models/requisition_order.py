from odoo import api, fields, models


class RequisitionOrder(models.Model):
    _inherit = 'requisition.order'

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    def button_approve(self):
        res = super().button_approve()
        for order in self:
            if not order.project_id and not order.task_id:
                continue
            qos = self.env['quotation.order'].search([('requisition_rfq_id', '=', order.id)])
            qos.write({
                'project_id': order.project_id.id or False,
                'task_id': order.task_id.id or False,
            })
            for qo in qos:
                for qo_line in qo.order_line:
                    rfq_line = qo_line.requisition_line_id
                    if rfq_line and rfq_line.task_cost_sheet_id:
                        qo_line.task_cost_sheet_id = rfq_line.task_cost_sheet_id
        return res


class RequisitionOrderLine(models.Model):
    _inherit = 'requisition.order.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        domain="[('task_id', '=', parent.task_id)]",
    )

    @api.onchange('task_cost_sheet_id')
    def _onchange_task_id(self):
        if self.order_id.task_id:
            return {'domain': {'task_cost_sheet_id': [('task_id', '=', self.order_id.task_id.id)]}}
        return {'domain': {'task_cost_sheet_id': []}}
