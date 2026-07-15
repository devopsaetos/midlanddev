from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceRequest(models.Model):
    # Odoo 19 migration note: previously inherited 'helpdesk.ticket' fields provided by the
    # (unavailable) 'website_axis_helpdesk' module indirectly via maintenance_team_id etc.
    # 'maintenance.request' itself is core Odoo, unaffected - see helpdesk_ticket.py and
    # __manifest__.py for the helpdesk/issue_requistion dependency notes.
    _inherit = ['maintenance.request']



    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket')
    # Odoo 19 migration note: 'helpdesk.ticket.type' (and the 'ticket_type_id' field on
    # helpdesk.ticket it related to) was a concept specific to the unavailable
    # 'website_axis_helpdesk' module. Core Odoo 19 'helpdesk' has no equivalent "ticket
    # type" model/field (it uses tag_ids for categorization instead), so this field is
    # commented out rather than deleted - same fix applied in maintenance_realestate_specific.
    # ticket_type_id = fields.Many2one('helpdesk.ticket.type', related='helpdesk_ticket_id.ticket_type_id')
    source_type = fields.Selection([('customer', 'Customer'), ('internal', 'Internal')], default='customer')
    department_id = fields.Many2one('hr.department', string='Department', domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string='Reported By')
    employee_contact = fields.Char(string='contact', related='employee_id.mobile_phone')
    partner_id = fields.Many2one('res.partner', string="Member")  # domain=[('is_member','=',True)] removed: is_member is not a field on res.partner anywhere in this project
    customer_name = fields.Char(string='Name', store=True, related='partner_id.name')
    contact_number = fields.Char(string='Contact Number', related='partner_id.phone', store=True)  # res.partner.mobile removed in Odoo 19, merged into phone
    tools_allocation = fields.Integer(compute='_compute_tools_allocation')
    # Odoo 19 migration note: 'material_requisition' counts/opens records of 'issue.requistion',
    # a model provided by the unavailable 'issue_requistion' module. Commented out rather than
    # deleted - see __manifest__.py for the full note (incl. a possible 'supply_chain_customizations'
    # based restoration path for the project owner to evaluate).
    # material_requisition = fields.Integer(compute='_compute_material_requisition')
    purchase_requisition = fields.Integer(compute='_compute_purchase_requisition')
    line_ids = fields.One2many('maintenance.request.line', 'maintenance_request_id')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    plot_id = fields.Many2one('plot.inventory')


    def _compute_tools_allocation(self):
        # Odoo 19 migration note: previously decorated '@api.model' and assigned directly
        # to 'self.tools_allocation'/'self.id', which raises "expected singleton" as soon
        # as this compute runs over more than one record at once (e.g. any list/kanban
        # view) - not a version-specific issue, but a real bug fixed while touching this
        # method during the migration. Rewritten batch-safe, matching the loop pattern
        # already used by helpdesk_ticket.py's _get_helpdesk_ticket_count.
        for rec in self:
            rec.tools_allocation = len(self.env['tools.allocation'].search([('maintenance_request_id', '=', rec.id)]))

    # Odoo 19 migration note: computed 'material_requisition' via the unavailable
    # 'issue.requistion' model - commented out along with the field above.
    # def _compute_material_requisition(self):
    #     for rec in self:
    #         rec.material_requisition = len(self.env['issue.requistion'].search([('maintenance_request_id', '=', rec.id)]))

    def _compute_purchase_requisition(self):
        # Odoo 19 migration note: same batch-safety fix as _compute_tools_allocation above.
        for rec in self:
            rec.purchase_requisition = len(self.env['material.purchase.requisition'].search([('maintenance_request_id', '=', rec.id)]))

    # Odoo 19 migration note: opened the unavailable 'issue.requistion' model / the
    # 'issue_requistion.issue_requistion_view_form' view (neither exists in this project).
    # Commented out along with the 'material_requisition' field/compute above - the
    # corresponding stat button was also removed from views/maintenance_request.xml.
    # def on_issue_requisition(self):
    #     result = {
    #         'name': (_('Material Requisition')),
    #         'res_model': 'issue.requistion',
    #         'type': 'ir.actions.act_window',
    #         'context': {'default_maintenance_request_id': self.id},
    #         'view_type': 'form',
    #         'view_id': self.env.ref("issue_requistion.issue_requistion_view_form").id,
    #         'target': 'self',
    #     }
    #     res_ids = self.env['issue.requistion'].search([('maintenance_request_id', '=', self.id)]).ids
    #
    #     if len(res_ids) < 2:
    #         result['domain'] = []
    #         result['view_mode'] = 'form'
    #         result['view_id'] = self.env.ref("issue_requistion.issue_requistion_view_form").id,
    #         result['res_id'] = self.env['issue.requistion'].search([('maintenance_request_id', '=', self.id)]).id
    #     else:
    #         result['domain'] = [('maintenance_request_id', '=', self.id)]
    #         result['view_mode'] = 'list,form'
    #
    #     return result


    def on_tool_allocation(self):
        result = {
            'name': (_('Tools Allocation')),
            'res_model': 'tools.allocation',
            'type': 'ir.actions.act_window',
            'context': {'default_maintenance_request_id': self.id},
            'view_type': 'form',
            'view_id': self.env.ref("maintenance_ext.tools_allocation_view_form").id,
            'target': 'self',
        }
        res_ids = self.env['tools.allocation'].search([('maintenance_request_id', '=', self.id)]).ids

        if len(res_ids) < 2:
            result['domain'] = []
            result['view_mode'] = 'form'
            result['view_id'] = self.env.ref("maintenance_ext.tools_allocation_view_form").id,
            result['res_id'] = self.env['tools.allocation'].search([('maintenance_request_id', '=', self.id)]).id
        else:
            result['domain'] = [('maintenance_request_id', '=', self.id)]
            result['view_mode'] = 'list,form'

        return result

    def on_purchase_requisition(self):
        result = {
            'name': (_('Purchase Allocation')),
            'res_model': 'material.purchase.requisition',
            'type': 'ir.actions.act_window',
            'context': {'default_maintenance_request_id': self.id},
            'view_type': 'form',
            'view_id': self.env.ref("purchase_requisitions.material_purchase_requisition_form_view").id,
            'target': 'self',
        }
        res_ids = self.env['material.purchase.requisition'].search([('maintenance_request_id', '=', self.id)]).ids

        if len(res_ids) < 2:
            result['domain'] = []
            result['view_mode'] = 'form'
            result['view_id'] = self.env.ref("purchase_requisitions.material_purchase_requisition_form_view").id,
            result['res_id'] = self.env['material.purchase.requisition'].search([('maintenance_request_id', '=', self.id)]).id
        else:
            result['domain'] = [('maintenance_request_id', '=', self.id)]
            result['view_mode'] = 'list,form'

        return result

    @api.onchange('stage_id')
    def onchange_maintenance_stages(self):
        # Odoo 19 migration note: the 'website_axis_helpdesk.stage_*' xmlids don't exist
        # (that module is unavailable). Core Odoo 19 'helpdesk' ships equivalent stage
        # records under its own module prefix ('helpdesk.stage_in_progress',
        # 'helpdesk.stage_solved', 'helpdesk.stage_cancelled' - see
        # odoo/addons/helpdesk/data/helpdesk_data.xml), so those are used instead - same
        # fix applied in maintenance_realestate_specific.
        if self.stage_id == self.env.ref('maintenance.stage_1'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_in_progress').id
        if self.stage_id == self.env.ref('maintenance.stage_3'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_solved').id

        if self.stage_id == self.env.ref('maintenance.stage_4'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_cancelled').id

    # @api.onchange('stage_id')
    # def stage_change_notification(self):
    #     if self.stage_id == self.env.ref('maintenance.stage_3'):
            # hod_id = self.employee_id.parent_id.user_id.partner_id
            # if hod_id:
            #     message = f"Hello {self.employee_id.parent_id.name}, The Request Raised By {self.employee_id.name} Has Been Repaired."
            #     notification_ids = []
            #     for user in hod_id:
            #         notification_ids.append((0, 0, {
            #             'res_partner_id': user.id,
            #             'notification_type': 'inbox'}))
            #     self.message_notify(
            #         partner_ids=hod_id.ids,
            #         body=message,
            #
            #
            #         email_layout_xmlid='mail.mail_notification_light',
            #     )
            #     # self.message_post(body=message,
            #     #                   message_type='notification',
            #     #                   subtype='mail.mt_comment',
            #     #                   notification_ids=notification_ids)
            # message = f"Hello {self.employee_id.parent_id.name}, The Request Raised By {self.employee_id.name} Has Been Resolved."
            # self.send_internal_notifications(message, [self.employee_id.parent_id.user_id], self.employee_id.name)



class MaintenanceRequestLine(models.Model):
    _name = 'maintenance.request.line'
    _description = 'Material Request Line'

    maintenance_request_id = fields.Many2one('maintenance.request')
    product_id = fields.Many2one('product.product', 'Product', required=True)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string="UoM", store=True, readonly=False)
    quantity = fields.Float(string="Quantity", default=1.0)