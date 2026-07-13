# Odoo 19 migration note: this entire file is NOT imported by models/__init__.py.
# It inherits 'issue.requistion', a model provided by the 'issue_requistion' module,
# which does not exist anywhere in this Odoo 19 project (only in an old Odoo 13 source
# tree). Importing this file would raise an error at module-load time because the base
# model it _inherit's would not be registered. Left in place, untouched, for reference/
# documentation purposes only - see __manifest__.py and models/__init__.py for the
# corresponding notes, and this module's final migration report for a note about
# 'supply_chain_customizations', which independently reimplements an 'issue.requistion'
# model natively for Odoo 19 and could potentially be used to restore this integration.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class IssueRequistion(models.Model):
    _inherit = 'issue.requistion'

    maintenance_request_id = fields.Many2one('maintenance.request')

    def action_set_issued(self):
        res = super(IssueRequistion, self).action_set_issued()
        if self.maintenance_request_id:
            self.maintenance_request_id.line_ids = self._get_lines()
        # self.maintenance_request_id.write({'line_ids': self._get_lines()})
        return res



    def _get_lines(self):
        lines = []
        for rec in self.line_ids:
            lines.append((0, 0, {'product_id': rec.product_id.id,
                                 'uom_id': rec.uom_id.id,
                                 'quantity': rec.quantity,
                                 }))
        return lines
