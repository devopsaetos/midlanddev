from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet', string='Cost Sheet', store=True,
        domain="[('task_id', '=', task_id)]",
    )

    @api.onchange('task_id')
    def _onchange_task_id_cost_sheet(self):
        self.task_cost_sheet_id = False
