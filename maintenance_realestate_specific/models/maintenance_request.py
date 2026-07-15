from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    def _get_default_value(self):
        return self.env['society'].search([], limit=1).id

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')], related='society_id.project_type')
    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket')
    # Odoo 19 migration note: 'helpdesk.ticket.type' (and the 'ticket_type_id' field on
    # helpdesk.ticket it related to) was a concept specific to the unavailable
    # 'website_axis_helpdesk' module. Core Odoo 19 'helpdesk' has no equivalent
    # "ticket type" model/field (it uses tag_ids for categorization instead), so this
    # field is commented out rather than deleted.
    # ticket_type_id = fields.Many2one('helpdesk.ticket.type', related='helpdesk_ticket_id.ticket_type_id')
    file_id = fields.Many2one('file')
    partner_id = fields.Many2one('res.partner', string="Member",  # domain=[('is_member','=',True)] removed: is_member is not a field on res.partner anywhere in this project
                                  context="{'form_view_ref': 'real_estate.view_partner_form'}")
    customer_name = fields.Char(string='Name', store=True, related='partner_id.name')
    contact_number = fields.Char(string='Contact Number', related='partner_id.phone', store=True)  # res.partner.mobile removed in Odoo 19, merged into phone
    # """if project type is housing society"""
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", store=True,
                                 default=_get_default_value)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", store=True)
    sector_id = fields.Many2one('sector', 'Sector')
    inventory_id = fields.Many2one('plot.inventory', string="Unit No")
    # """if project type is skyscraper"""
    project_id = fields.Many2one('society', 'Project', domain="[('is_society','=',True)]", store=True)
    building_id = fields.Many2one('society', 'Building', domain="[('is_society','!=',True)]", store=True)
    floor_id = fields.Many2one('sector', 'Floor')
    building_inventory_id = fields.Many2one('plot.inventory', string="Office No")
    source_type = fields.Selection([('customer', 'Customer'), ('internal', 'Internal')], default='customer')
    department_id = fields.Many2one('hr.department', string='Department', domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string='Reported By')
    employee_contact = fields.Char(string='contact', related='employee_id.mobile_phone')
    plot_name = fields.Char('Plot Number')
    street_id = fields.Many2one('street', string='Street', domain="[('sector_id','=',sector_id)]")
    #team_members = fields.Many2one('maintenance.team', string='Responsible', domain=[('id','=', 'maintenance_team_id')])


    @api.onchange('plot_name')
    def onchange_inventory_id(self):
        if self.plot_name:
            try:
                plot_obj = \
                    self.env['plot.inventory'].search(
                        [('name', '=', self.plot_name), ('project_type', '=', self.society_id.project_type)], limit=1)
            except Exception as e:
                raise ValidationError(_('Some Basic Data for member is not available.See Error :%s' % (e)))
            else:
                file_obj = self.env['file'].search([('inventory_id', '=', plot_obj.id)], limit=1)
                if file_obj:
                    self.file_id = file_obj.id
                    self.society_id = file_obj.society_id.id
                    self.phase_id = file_obj.phase_id.id
                    self.sector_id = file_obj.sector_id.id
                    self.street_id = file_obj.street_id.id
                    self.partner_id = file_obj.membership_id.id
                    self.inventory_id = file_obj.inventory_id.id
                else:
                    raise ValidationError(_('No Record Found.'))

    @api.onchange('sector_id', 'phase_id')
    def _onchange_sector_id(self):
        return {'domain': {
            'phase_id': [('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id), ('society_id', '=', self.society_id.id)],
            'inventory_id': [('sector_id', '=', self.sector_id.id), ('phase_id', '=', self.phase_id.id),
                             ('society_id', '=', self.society_id.id)]
        }
        }

    @api.onchange('stage_id')
    def onchange_maintenance_stages(self):
        # Odoo 19 migration note: the 'website_axis_helpdesk.stage_*' xmlids don't exist
        # (that module is unavailable). Core Odoo 19 'helpdesk' ships equivalent stage
        # records under its own module prefix ('helpdesk.stage_in_progress',
        # 'helpdesk.stage_solved', 'helpdesk.stage_cancelled' - see
        # odoo/addons/helpdesk/data/helpdesk_data.xml), so those are used instead.
        if self.stage_id == self.env.ref('maintenance.stage_1'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_in_progress').id
        if self.stage_id == self.env.ref('maintenance.stage_3'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_solved').id
        if self.stage_id == self.env.ref('maintenance.stage_4'):
            self.helpdesk_ticket_id.stage_id = self.env.ref('helpdesk.stage_cancelled').id