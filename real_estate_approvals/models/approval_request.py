from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    investor_id = fields.Many2one(
        'res.investor',
        string='Related Investor',
        ondelete='cascade',
        index=True,
    )

    def write(self, vals):
        res = super().write(vals)
        if 'request_status' in vals:
            new_status = vals['request_status']
            for req in self:
                if not req.investor_id:
                    continue
                investor = req.investor_id.sudo()
                if new_status == 'approved' and investor.state == 'in_process':
                    investor.write({'state': 'approve'})
                elif new_status == 'refused' and investor.state == 'in_process':
                    investor.write({'state': 'draft'})
        return res
