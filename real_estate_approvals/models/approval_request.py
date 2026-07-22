from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    investor_id = fields.Many2one(
        'res.investor',
        string='Related Investor',
        ondelete='cascade',
        index=True,
    )
