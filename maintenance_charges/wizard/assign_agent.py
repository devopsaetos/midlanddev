# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MaintenanceAgentWizard(models.TransientModel):
    _name = 'maintenance.agent.wizard'
    _description = 'Maintenance Agent Wizard'

    maintenance_recovery_agent_id = fields.Many2one('res.users', domain="[('maintenance_recovery_agent', '=', True)]")
    society_id = fields.Many2one('society', string='Society', domain="[('is_society', '=', True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('is_society', '!=', True)]")
    sector_id = fields.Many2one('sector', string='Sector')
    street_id = fields.Many2one('street', string='Street')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product')
    size_id = fields.Many2one('unit.size', string='Size')
    unit_class_id = fields.Many2one('unit.class', string='Type')
    street_ids = fields.Many2many('street')

    @api.onchange('society_id', 'phase_id', 'sector_id', 'street_id', 'category_id', 'unit_category_type_id', 'size_id', 'unit_class_id')
    def _phase_domain(self):
        domain = [('maintenance_recovery_agent_id', '=', False)]
        if self.society_id:
            domain.append(('society_id', '=', self.society_id.id))
        if self.phase_id:
            domain.append(('phase_id', '=', self.phase_id.id))
        if self.sector_id:
            domain.append(('sector_id', '=', self.sector_id.id))
        if self.street_id:
            domain.append(('street_id', '=', self.street_id.id))
        if self.category_id:
            domain.append(('category_id', '=', self.category_id.id))
        if self.unit_category_type_id:
            domain.append(('unit_category_type_id', '=', self.unit_category_type_id.id))
        if self.size_id:
            domain.append(('size_id', '=', self.size_id.id))
        if self.unit_class_id:
            domain.append(('unit_class_id', '=', self.unit_class_id.id))
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'street_id': [('sector_id', '=', self.sector_id.id)],
            'street_ids': [('sector_id', '=', self.sector_id.id)],
        }
        }

    def assign_agent(self):
        if self.street_ids:
            domain = [('street_id', 'in', self.street_ids.ids),('maintenance_recovery_agent_id', '=', False)]
            if self.society_id:
                domain.append(('society_id', '=', self.society_id.id))
            if self.phase_id:
                domain.append(('phase_id', '=', self.phase_id.id))
            if self.sector_id:
                domain.append(('sector_id', '=', self.sector_id.id))
            if self.category_id:
                domain.append(('category_id', '=', self.category_id.id))
            if self.unit_category_type_id:
                domain.append(('unit_category_type_id', '=', self.unit_category_type_id.id))
            if self.size_id:
                domain.append(('size_id', '=', self.size_id.id))
            if self.unit_class_id:
                domain.append(('unit_class_id', '=', self.unit_class_id.id))
            files = self.env['file'].search(domain)
            if not files:
                raise ValidationError(_("No files found in selected streets."))
            for file in files:
                if file.maintenance_recovery_agent_id:
                    raise ValidationError(_("Agent on file: %s is already assign, Skipping." % file.name))

                file.maintenance_recovery_agent_id = self.maintenance_recovery_agent_id.id
                # if file.recovery_agent_history:
                #     file.recovery_agent_history.status = 'inactive'
                #     file.recovery_agent_history.filtered(lambda l:not l.end_date).end_date = fields.Date.today()
                # file.recovery_agent_history = [(0, 0, {
                #     'agent_id': self.agent_id.id,
                #     'start_date': fields.Date.today(),
                #     'status': 'active',
                #     'file_id': file.id
                # })]

            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': "All Selected Files are assign to Selected Agent.",
                    'img_url': '/web/image/%s/%s/image_1024' % ('res.users',
                                                                self.maintenance_recovery_agent_id.id) if self.maintenance_recovery_agent_id.image_1024 else '/web/static/src/img/smile.svg',
                    'type': 'rainbow_man',
                }
            }
