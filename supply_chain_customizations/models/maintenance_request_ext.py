from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    material_requisition = fields.Integer(compute='_compute_material_requisition')
    line_ids = fields.One2many('maintenance.request.line', 'maintenance_request_id')



    @api.model
    def _compute_material_requisition(self):
        self.material_requisition = len(self.env['issue.requistion'].search([('maintenance_request_id', '=', self.id)]))

    def on_issue_requisition(self):
        result = {
            'name': (_('Material Requisition')),
            'res_model': 'issue.requistion',
            'type': 'ir.actions.act_window',
            'context': {'default_maintenance_request_id': self.id},
            'view_type': 'form',
            'view_id': self.env.ref("supply_chain_customizations.issue_requistion_view_form").id,
            'target': 'self',
        }
        res_ids = self.env['issue.requistion'].search([('maintenance_request_id', '=', self.id)]).ids

        if len(res_ids) < 2:
            result['domain'] = []
            result['view_mode'] = 'form'
            result['view_id'] = self.env.ref("supply_chain_customizations.issue_requistion_view_form").id,
            result['res_id'] = self.env['issue.requistion'].search([('maintenance_request_id', '=', self.id)]).id
        else:
            result['domain'] = [('maintenance_request_id', '=', self.id)]
            result['view_mode'] = 'list,form'

        return result


class MaintenanceRequestLine(models.Model):
    _name = 'maintenance.request.line'
    _description = 'Material Request Line'

    maintenance_request_id = fields.Many2one('maintenance.request')
    product_id = fields.Many2one('product.product', 'Product', required=True)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string="UoM", store=True, readonly=False)
    quantity = fields.Float(string="Quantity", default=1.0)

