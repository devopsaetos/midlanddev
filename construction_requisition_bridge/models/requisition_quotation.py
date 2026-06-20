from odoo import api, fields, models


class QuotationOrder(models.Model):
    _inherit = 'quotation.order'

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}


class QuotationOrderLine(models.Model):
    _inherit = 'quotation.order.line'

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

    def action_create_po_vendor_wise(self):
        existing_po_ids = self.env['purchase.order'].search([]).ids
        result = super().action_create_po_vendor_wise()
        new_pos = self.env['purchase.order'].search([('id', 'not in', existing_po_ids)])
        quotation_lines = self.env['quotation.order.line'].browse(
            self.env.context.get('active_ids', [])
        )
        for po in new_pos:
            source_line = quotation_lines[:1]
            po.write({
                'project_id': source_line.order_id.project_id.id or False,
                'task_id': source_line.order_id.task_id.id or False,
            })
            for po_line in po.order_line:
                if not po_line.product_id:
                    continue
                qo_line = quotation_lines.filtered(
                    lambda l: l.product_id == po_line.product_id
                )[:1]
                if qo_line and qo_line.task_cost_sheet_id:
                    po_line.task_cost_sheet_id = qo_line.task_cost_sheet_id
        return result
