from odoo import api, fields, models, tools, _

class EvaluationConnector(models.Model):
    _name = "evaluation.connector"
    _description = "Evaluation Connector"

    field_id = fields.Many2one('evaluation.criteria', required=True)
    value = fields.Char('Value')
    requisition_order_id = fields.Many2one('requisition.order', ondelete="cascade")
    quotation_order_id = fields.Many2one('quotation.order', ondelete="cascade")





class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    requisition_order_id =  fields.Many2one('requisition.order' )