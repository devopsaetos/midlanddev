from odoo import api, fields, models


class StockTransaction(models.Model):
    _inherit = 'stock.transaction'

    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    def action_create_moves(self):
        result = super().action_create_moves()
        # If base returned a dialog (e.g. insufficient qty), propagate immediately
        if isinstance(result, dict) and result.get('type') == 'ir.actions.act_window':
            return result
        self._write_overhead_to_cost_sheets()
        return result

    def _write_overhead_to_cost_sheets(self):
        for line in self.line_ids.filtered(
            lambda l: l.task_cost_sheet_id and l.state == 'confirm'
        ):
            overhead_type = line.task_cost_sheet_id.project_id.overhead_type
            if not overhead_type:
                continue
            rate = self.project_id.rate or 0.0
            unit_price = line.product_id.standard_price
            overhead_value = (line.scrap_qty * unit_price) * (rate / 100)
            line_vals = {
                'product_id': line.product_id.id,
                'description': line.product_id.name,
                'quantity': line.scrap_qty,
                'uom_id': line.product_uom_id.id,
                'unit_price': unit_price,
                'over_head_value': overhead_value,
            }
            if overhead_type == 'labour':
                line.task_cost_sheet_id.write({'bills_line_ids': [(0, 0, line_vals)]})
            elif overhead_type == 'material':
                line.task_cost_sheet_id.write({'material_task_cost_line_ids': [(0, 0, line_vals)]})


class StockTransactionLine(models.Model):
    _inherit = 'stock.transaction.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        store=True,
        domain="[('task_id', '=', parent.task_id)]",
    )

    @api.onchange('task_cost_sheet_id')
    def _onchange_task_cost_sheet_id(self):
        if self.task_cost_sheet_id:
            self.analytic_account_id = self.task_cost_sheet_id.analytic_account_id
        if self.transaction_id.task_id:
            return {'domain': {'task_cost_sheet_id': [('task_id', '=', self.transaction_id.task_id.id)]}}
        return {'domain': {'task_cost_sheet_id': []}}
