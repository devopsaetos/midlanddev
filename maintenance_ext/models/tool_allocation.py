from odoo import fields, models, api, _
import datetime


class ToolsAllocation(models.Model):
    _name = 'tools.allocation'
    _description = 'Tools Allocation'
    _rec_name = 'asset_id'
    # Odoo 19 migration note: added 'mail.thread'/'mail.activity.mixin'. The original
    # form view had a dead 'oe_chatter' div (its message_follower_ids/activity_ids/
    # message_ids sub-fields were already all commented out in the source) and
    # 'employee_id' below already used track_visibility='onchange' - both only work on
    # models that inherit mail.thread, which this model never did, so tracking/chatter
    # were completely inert pre-migration. Added the mixins (matching every other model
    # in this project's sibling modules that uses <chatter/>, e.g.
    # purchase_requisitions' material.purchase.requisition) so the now-converted
    # <chatter/> view element (views/tools_allocation.xml) and tracking=True below
    # actually function instead of erroring/no-oping at runtime.
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Serial Number', required=True, copy=False, readonly=True, index=True,
                                default=lambda self: _('New'))
    maintenance_request_id = fields.Many2one('maintenance.request', readonly=True)
    # Odoo 19 migration note: the model was renamed from 'account.asset.asset' (old Odoo
    # <=12 naming) to 'account.asset' starting with Odoo 13 - fixed here to the current
    # name, and 'account_asset' added to this module's manifest 'depends' so the comodel
    # is guaranteed registered (same pattern as sibling module 'unit_booking').
    asset_id = fields.Many2one('account.asset', required=True)
    to_location = fields.Char(required=True)
    employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
    issue_date = fields.Datetime()
    return_date = fields.Datetime()
    state = fields.Selection([
        ('draft','Draft'),
        ('issued','Issued'),
        ('returned','Returned')
    ], default='draft')
    is_issued = fields.Boolean(default=False)
    is_returned = fields.Boolean(default=False)


    def on_issued(self):
        self.state = 'issued'
        self.issue_date = datetime.datetime.now()
        self.is_issued = True


    def on_return(self):
        self.state = 'returned'
        self.return_date = datetime.datetime.now()
        self.is_returned = True

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code("tools") or _('New')

        return super(ToolsAllocation, self).create(vals)
