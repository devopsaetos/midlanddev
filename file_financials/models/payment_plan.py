from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import dateutil.parser


class PaymentPlanExt(models.Model):
    _inherit = 'payment.plan'
    _description = 'Payment Plan'

    investment_id = fields.Many2one('investment', string="Investment No.")
