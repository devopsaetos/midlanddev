from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    task_cost_sheet_id = fields.Many2one(
        'task.cost.sheet',
        string='Cost Sheet',
        store=True,
        domain="[('task_id', '=', parent.task_id)]",
    )
