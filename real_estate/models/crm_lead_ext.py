# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CrmLeadExt(models.Model):
    _inherit = 'crm.lead'

    crm_lead_line = fields.One2many('crm.lead.line', 'crm_lead_id')
    crm_lead_building = fields.One2many('crm.lead.line', 'crm_lead_id')
    crm_pipeline_ids = fields.One2many('crm.lead.line', 'crm_pipeline_id')
    society_id = fields.Many2one('society', string='Society',domain=[('is_society','=',True)])
    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ], related='society_id.project_type', store=True)
    is_existing = fields.Boolean(default=False)
    token_paid = fields.Boolean(default=False)
    plan_locked = fields.Boolean()
    party_type = fields.Selection([
        ('member', 'Member'),
        ('investor', 'Investor'),
    ], default='member', string='Party Type')
    investor_id = fields.Many2one('res.investor', string='Investor')

    def action_create_member(self):
        return {
            'name': _('Create Member'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.member',
            'view_id': self.env.ref('real_estate.view_partner_form').id,
            'type': 'ir.actions.act_window',
            'context': {'default_name': self.contact_name, 'current_view': 'realestate',
                        'default_project_type': self.project_type or 'housing_society'},
            'target': 'new',
        }

    def action_create_investor(self):
        return {
            'name': _('Create Investor'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.investor',
            'view_id': self.env.ref('real_estate.investor_registration_form_view').id,
            'type': 'ir.actions.act_window',
            'context': {'current_view': 'realestate'},
            'target': 'new',
        }

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        # Odoo 19's base crm.lead no longer has an _onchange_partner_id method to call -
        # partner-driven field updates were split into separate @api.depends computes
        # (_compute_contact_name, _compute_function, etc). This onchange only needs to
        # add real_estate's own reaction on top of those, so there's nothing to super() into.
        if self.partner_id:
            self.is_existing = True
            self.phone = self.partner_id.mobile
            self.city = self.partner_id.city_id.name

    def token_money(self):
        # if not self.plan_locked:
        #     raise ValidationError(_('Please create installment plan before creating token.'))
        data = []
        for rec in self.crm_lead_line:
            if rec:
                data.append((0,0,{
                        'phase_id': rec.phase_id.id,
                        'sector_id': rec.sector_id.id,
                        'street_id': rec.street_id.id,
                        'inventory_id': rec.inventory_id.id,
                        'category_id': rec.category_id.id,
                        'unit_category_type_id': rec.unit_category_type_id.id,
                        'size_id': rec.size_id.id,
                        'unit_class_id': rec.unit_class_id.id,
                }))
        context = {
                    'default_from_crm': True,
                    'default_plan_locked': self.plan_locked,
                    'default_crm_id': self.id,
                    'default_party_type': self.party_type,
                    'default_investor_id': self.investor_id.id,
                    'default_is_existing': self.is_existing,
                    'default_company_type': self.partner_id.company_type,
                    'default_partner_id': self.partner_id.id if self.is_existing else False,
                    'default_contact_name': self.contact_name,
                    'default_cp_phone_no': self.phone,
                    'default_phone_no': self.phone,
                    'default_email': self.email_from,
                    'default_society_id': self.society_id.id,
                    'default_token_line_ids': data,
                  }
        return {
            'res_model': 'token.money',
            'type': 'ir.actions.act_window',
            'context': context,
            # 'domain': [('customer_id', '=', self.customer_id)],
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.env['token.money'].search([('crm_id', '=', self.id)]).id,
            'view_id': self.env.ref("real_estate.validate_token_form").id if self.project_type == 'housing_society' else self.env.ref('land_development.validate_token_form').id,
            'target': 'self'
        }

    def propose_plan(self):
        return {
            'res_model': 'propose.plan',
            'type': 'ir.actions.act_window',
            'context': {'default_crm_id': self.id},
            # 'domain': [('customer_id', '=', self.customer_id)],
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.env['propose.plan'].search([('crm_id', '=', self.id)]).id,
            'view_id': self.env.ref("real_estate.propose_plan_form").id,
            'target': 'self'
        }


class CrmLeadExtLine(models.Model):
    _name = 'crm.lead.line'
    _description = 'Crm Lead Line'

    # society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', required=True, domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector', required=True, store=True, related="inventory_id.sector_id", readonly=False)
    street_id = fields.Many2one('street', store=True, related="inventory_id.street_id", readonly=False)
    category_id = fields.Many2one('plot.category', required=True, store=True, related="inventory_id.category_id", readonly=False)
    unit_category_type_id = fields.Many2one('unit.category.type', 'Product', required=True, store=True, related="inventory_id.unit_category_type_id", readonly=False)
    size_id = fields.Many2one('unit.size', related="inventory_id.size_id", store=True, readonly=False)
    unit_class_id = fields.Many2one('unit.class', 'Type', related="inventory_id.unit_class_id", store=True, readonly=False)
    inventory_id = fields.Many2one('plot.inventory', 'Unit')

    crm_lead_id = fields.Many2one('crm.lead')
    crm_pipeline_id = fields.Many2one('crm.lead')

    @api.onchange('phase_id', 'sector_id', 'street_id')
    def _phase_domain(self):
        if self.street_id:
            return {'domain': {
                'inventory_id': [('street_id', '=', self.street_id.id),('state','=','avalible_for_sale')],
            }
            }
        else:
            return {'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.crm_lead_id.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
                'inventory_id': [('sector_id', '=', self.sector_id.id),('state','=','avalible_for_sale')],
            }
            }

    @api.onchange('sector_id')
    def _inventory_domain(self):
        return {'domain': {
            'inventory_id': [('phase_id', '=', self.phase_id.id),('sector_id', '=', self.sector_id.id),('state','=','avalible_for_sale')],
        }
        }