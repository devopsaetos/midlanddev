from odoo import api, fields, models


class PurchaseOrderExt(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        selected_products = self._context.get('request_line_ids')
        if not selected_products:
            return res
        selected_line_ids = self.env['requisition.line'].browse(selected_products)
        if not selected_line_ids:
            return res
        # Inject task_cost_sheet_id into already-built order_line tuples
        if 'order_line' in res:
            new_lines = []
            lines = list(selected_line_ids)
            for i, (cmd, _, vals) in enumerate(res.get('order_line', [])):
                if i < len(lines):
                    sheet = lines[i].task_cost_sheet_id
                    if sheet:
                        vals['task_cost_sheet_id'] = sheet.id
                new_lines.append((cmd, _, vals))
            res['order_line'] = new_lines
        # Inject project/task from requisition header
        first = selected_line_ids[0]
        if first.requisition_id.project_id and 'project_id' not in res:
            res['project_id'] = first.requisition_id.project_id.id
        if first.requisition_id.task_id and 'task_id' not in res:
            res['task_id'] = first.requisition_id.task_id.id
        return res


class PurchaseOrderLineExt(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('task_cost_sheet_id')
    def _onchange_task_cost_sheet_domain(self):
        if self.order_id.task_id:
            return {'domain': {'task_cost_sheet_id': [('task_id', '=', self.order_id.task_id.id)]}}
        return {'domain': {'task_cost_sheet_id': []}}
