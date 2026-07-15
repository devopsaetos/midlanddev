from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HelpdeskTicket(models.Model):
    # Odoo 19 migration note: previously inherited 'helpdesk.ticket' as provided by the
    # (unavailable) 'website_axis_helpdesk' module. Now inherits the real 'helpdesk.ticket'
    # model shipped by Odoo 19 Enterprise's core 'helpdesk' app. See
    # maintenance_realestate_specific/models/helpdesk_ticket.py (converted earlier in this
    # same migration batch) for the precedent this follows.
    _inherit = 'helpdesk.ticket'

    partner_id = fields.Many2one('res.partner', string="Member", store=True)  # domain="[('is_member','=',1)]" removed: is_member is not a field on res.partner anywhere in this project
    customer_name = fields.Char(string='Name', store=True, related='partner_id.name')
    contact_number = fields.Char(string='Contact Number', related='partner_id.phone', store=True)  # res.partner.mobile removed in Odoo 19, merged into phone
    employee_id = fields.Many2one('hr.employee', string='Reported By')
    employee_contact = fields.Char(string='Contact', related='employee_id.mobile_phone')
    source_type = fields.Selection([('customer', 'Customer'), ('internal', 'Internal')], default='customer')
    department_id = fields.Many2one('hr.department', string='Department', domain="[('company_id', '=', company_id)]")
    is_contact_no = fields.Boolean(string='is_contact', default=False)
    helpdesk_ticket_count = fields.Integer(string='count', compute='_get_helpdesk_ticket_count')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    plot_id = fields.Many2one('plot.inventory')
    # Odoo 19 migration note: 'maintenance_team_id' on helpdesk.ticket was previously
    # provided by 'website_axis_helpdesk' (not available in this project). Re-defined here
    # directly against core Odoo's 'maintenance.team' model (from the 'maintenance' app,
    # now an explicit dependency) so send_to_maintenance() below keeps working - same fix
    # applied in maintenance_realestate_specific.
    maintenance_team_id = fields.Many2one('maintenance.team', string='Maintenance Team')



    @api.depends('helpdesk_ticket_count')
    def _get_helpdesk_ticket_count(self):
        for rec in self:
            rec.helpdesk_ticket_count = len(
                rec.env['maintenance.request'].search([('helpdesk_ticket_id', '=', rec.id)]))

    def send_to_maintenance(self):
        if not self.maintenance_team_id:
            raise ValidationError(_('Please select maintenance team before assigning.'))

        data = {
            'helpdesk_ticket_id': self.id,
            'name': self.name,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'maintenance_team_id': self.maintenance_team_id.id,
            'contact_number': self.contact_number,
            'source_type': self.source_type,
            'department_id': self.department_id.id,
            'employee_id': self.employee_id.id,
            'description': self.description,
            'society_id': self.society_id.id or False,
            'phase_id': self.phase_id.id or False,
            'sector_id': self.sector_id.id or False,
            'plot_id': self.plot_id.id or False,
        }
        record = self.env['maintenance.request'].search([('helpdesk_ticket_id', '=', self.id)])
        if record:
            raise ValidationError(_('Ticket is Already Generated'))
        maintenance_req = record.create(data)
        return maintenance_req
