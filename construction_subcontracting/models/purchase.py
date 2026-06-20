from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    task_subcontract_id = fields.Many2one('task.subcontract', string='Sub Contract')
    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    def button_confirm(self):
        res = super().button_confirm()
        for order in self:
            if not order.task_subcontract_id:
                continue
            for line in order.order_line:
                if not line.subcontract_line_id:
                    continue
                plan_line = self.env['subtract.plan.products'].browse(line.subcontract_line_id)
                if plan_line.exists():
                    plan_line.order_qty += line.product_qty
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    task_subcontract_id = fields.Many2one(related='order_id.task_subcontract_id', store=True)
    subcontract_line_id = fields.Integer(string='Subcontract Line Id')
