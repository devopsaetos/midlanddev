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

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(CrmLeadExt, self)._onchange_partner_id()

        if self.partner_id:
            self.is_existing = True
            self.mobile = self.partner_id.mobile
            self.city = self.partner_id.city_id.name

        return res

    @api.depends('sequence_name')
    def name_get(self):
        result = []
        for rec in self:
            name = rec.sequence_name
            result.append((rec.id, name))
        return result

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
                    'default_is_existing': self.is_existing,
                    'default_company_type': self.partner_id.company_type,
                    'default_partner_id': self.partner_id.id if self.is_existing else False,
                    'default_contact_name': self.contact_name,
                    'default_cp_phone_no': self.mobile,
                    'default_phone_no': self.mobile,
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