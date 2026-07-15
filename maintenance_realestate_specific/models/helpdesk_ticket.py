from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HelpDeskTicket(models.Model):
    # Odoo 19 migration note: previously inherited 'helpdesk.ticket' as provided by the
    # (unavailable) 'website_axis_helpdesk' module. Now inherits the real 'helpdesk.ticket'
    # model shipped by Odoo 19 Enterprise's core 'helpdesk' app.
    _inherit = 'helpdesk.ticket'

    def _default_value(self):
        return self.env['society'].search([], limit=1).id

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')], related='society_id.project_type', store=True)
    file_id = fields.Many2one('file')
    partner_id = fields.Many2one('res.partner', string="Member", store=True)  # domain="[('is_member','=',1)]" removed: is_member is not a field on res.partner anywhere in this project
    customer_name = fields.Char(string='Name', store=True, related='partner_id.name')
    contact_number = fields.Char(string='Contact Number', related='partner_id.phone', store=True)  # res.partner.mobile removed in Odoo 19, merged into phone
    employee_id = fields.Many2one('hr.employee', string='Reported By')
    employee_contact = fields.Char(string='contact', related='employee_id.mobile_phone')
    # """if project type is housing society"""
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", store=True,
                                 default=_default_value)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", store=True)
    sector_id = fields.Many2one('sector', 'Sector')
    inventory_id = fields.Many2one('plot.inventory', string="Unit No")
    street_id = fields.Many2one('street', string='Street')
    # """if project type is skyscraper"""
    project_id = fields.Many2one('society', 'Project', domain="[('is_society','=',True)]", store=True)
    building_id = fields.Many2one('society', 'Building', domain="[('is_society','!=',True)]", store=True)
    floor_id = fields.Many2one('sector', 'Floor')
    building_inventory_id = fields.Many2one('plot.inventory', string="Office No")
    source_type = fields.Selection([('customer', 'Customer'), ('internal', 'Internal')], default='customer')
    department_id = fields.Many2one('hr.department', string='Department', domain="[('company_id', '=', company_id)]")
    is_contact_no = fields.Boolean(string='is_contact', default=False)
    plot_name = fields.Char('Plot Number')
    helpdesk_ticket_count = fields.Integer(string='count', compute='_get_helpdesk_ticket_count')
    # Odoo 19 migration note: 'maintenance_team_id' on helpdesk.ticket was previously
    # provided by 'website_axis_helpdesk' (not available in this project). Re-defined
    # here directly against core Odoo's 'maintenance.team' model (from the 'maintenance'
    # app, now an explicit dependency) so send_to_maintenance() below keeps working.
    maintenance_team_id = fields.Many2one('maintenance.team', string='Maintenance Team')

    @api.depends('helpdesk_ticket_count')
    def _get_helpdesk_ticket_count(self):
        for rec in self:
            rec.helpdesk_ticket_count = len(rec.env['maintenance.request'].search([('helpdesk_ticket_id', '=', rec.id)]))

    @api.onchange('sector_id', 'phase_id')
    def _onchange_sector_id(self):
        if self.source_type != 'customer':
            return {'domain': {
                'phase_id': [('society_id', '=', self.society_id.id)],
                'sector_id': [('society_id', '=', self.society_id.id), ('phase_id', '=', self.phase_id.id)],
                'inventory_id': ['|', ('street_id', '=', self.street_id.id), ('sector_id', '=', self.sector_id.id)]
            }
            }

    @api.onchange('inventory_id')
    def onchange_inventory_id(self):
        if self.inventory_id:
            try:
                file_obj = self.env['file'].search([('inventory_id', '=', self.inventory_id.id),
                                                    ('project_type', '=', self.project_type)], limit=1)
            except Exception as e:
                raise ValidationError(_('Some Basic Data for member is not available.See Error :%s' % (e)))
            else:
                if file_obj:
                    self.file_id = file_obj.id
                    self.society_id = file_obj.society_id.id
                    self.phase_id = file_obj.phase_id.id
                    self.sector_id = file_obj.sector_id.id
                    self.street_id = file_obj.street_id.id
                    self.partner_id = file_obj.membership_id.id
                else:
                    raise ValidationError(_('No Record Found.'))

    def search_contact_number(self):

        return {
            'name': _('Search Record'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'search.record',
            'view_id': self.env.ref(
                'maintenance_realestate_specific.search_record_form_housing_society'
            ).id if self.project_type == 'housing_society' else self.env.ref(
                'maintenance_realestate_specific.search_record_form_skyscraper').id,
            'type': 'ir.actions.act_window',
            'context': {'default_project_type': self.project_type},
            'target': 'new',
        }

    def send_to_maintenance(self):
        if not self.maintenance_team_id:
            raise ValidationError(_('Please select maintenance team before assigning.'))

        data = {
            'helpdesk_ticket_id': self.id,
            'name': self.name,
            'file_id': self.file_id.id,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'maintenance_team_id': self.maintenance_team_id.id,
            'contact_number': self.contact_number,
            'source_type': self.source_type,
            'project_type': self.project_type,
            'department_id': self.department_id.id,
            'society_id': self.society_id.id,
            'phase_id': self.phase_id.id,
            'sector_id': self.sector_id.id,
            'inventory_id': self.inventory_id.id,
            'plot_name': self.plot_name,
            'street_id': self.street_id.id,
            'employee_id': self.employee_id.id,
            'description': self.description,
        }
        record = self.env['maintenance.request'].search([('helpdesk_ticket_id', '=', self.id)])
        if record:
            raise ValidationError(_('Ticket is Already Generated'))
        maintenance_req = record.create(data)
        return maintenance_req
        # return {
        #     'name': _('Maintenance Request'),
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'maintenance.request',
        #     'type': 'ir.actions.act_window',
        #     'res_id': self.env['maintenance.request'].search([('helpdesk_ticket_id', '=', self.id)]).id,
        #     'view_id': self.env.ref("maintenance.hr_equipment_request_view_form").id
        # }
