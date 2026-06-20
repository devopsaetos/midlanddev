from odoo import api, fields, models, tools, _


class EvaluationCriteria(models.Model):
    _name = "evaluation.criteria"
    _description = "Evaluation Criteria"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Attribute Name")
    value = fields.Char()
