from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    task_subcontract_id = fields.Many2one('task.subcontract', string='Sub Contract')
    task_id = fields.Many2one('project.task', string='Task')
    project_id = fields.Many2one('project.project', string='Project')
