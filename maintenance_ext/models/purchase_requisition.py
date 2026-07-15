from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MaterialPurchaseRequisition(models.Model):
    _inherit = "material.purchase.requisition"

    maintenance_request_id = fields.Many2one('maintenance.request')