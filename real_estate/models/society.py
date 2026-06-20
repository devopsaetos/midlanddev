# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Society(models.Model):
    _name = 'society'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Society"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ], readonly = True)

    type = fields.Selection([
        ('rent','Rental'),
        ('sale','Sales'),
        ('both','Both')
    ], default='both')

    image = fields.Binary("Image", attachment=True,help="This field holds the image used as avatar for this contact, limited to 1024x1024px",)
    name = fields.Char('Name', required = True)
    
    is_society = fields.Boolean()
    
    code = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    branch_id = fields.Many2one('res.company',default=lambda self: self.env.company)
    
    partner_id = fields.Many2one('res.partner',"Project Manager")
    pricing_policy = fields.Selection([
        ('area', 'Area Base'),
        ('unit_base', 'Unit Base'),
    ],default='area')
    city_id = fields.Many2one('city', related='location_id.city_id', readonly=True)
    location_id = fields.Many2one('location')
    authority_id = fields.Many2one('res.authority','Authority')
    
    phase_line = fields.One2many('society','society_id')
    society_id = fields.Many2one('society',domain="[('is_society','=',True)]")
    
    sector_line = fields.One2many('sector','phase_id')
    land_owner_ids = fields.Many2many('res.partner')
    # project_owner_ids = fields.Many2many('res.partner', domain="[('is_member', '!=', 1)]")
    
    head_street_1 = fields.Char()
    head_street_2 = fields.Char()
    head_zip = fields.Char(change_default=True, related='head_city_id.zip', readonly=True)
    head_city_id = fields.Many2one('city',change_default=True)
    head_state_id = fields.Many2one("res.country.state",change_default=True, string='State', ondelete='restrict', related='head_city_id.state_id', readonly=True)
    head_country_id = fields.Many2one('res.country',change_default=True, string='Country', ondelete='restrict', related='head_city_id.state_id.country_id', readonly=True)
    head_email = fields.Char()
    head_phone = fields.Char()
    
    site_street_1 = fields.Char(change_default=True)
    site_street_2 = fields.Char(change_default=True)
    site_zip = fields.Char(change_default=True, related='site_city_id.zip', readonly=True, string='Zip ')
    site_city_id = fields.Many2one('city',change_default=True)
    site_state_id = fields.Many2one("res.country.state",change_default=True, string='State ', ondelete='restrict', related='site_city_id.state_id', readonly=True)
    site_country_id = fields.Many2one('res.country',change_default=True, string='Country ', ondelete='restrict', related='site_city_id.state_id.country_id', readonly=True)
    site_email = fields.Char()
    site_phone = fields.Char()

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('pricing_policy') and val['pricing_policy'] == 'unit_base':
                self.env.ref('real_estate.group_rsms_manager').implied_ids = [
                    (4, self.env.ref('real_estate.group_user_base_pricing').id)]
        return super(Society, self).create(vals_list)


    def write(self, vals):
        if vals.get('pricing_policy') and vals['pricing_policy'] == 'unit_base':
            self.env.ref('real_estate.group_rsms_manager').implied_ids = [
                (4, self.env.ref('real_estate.group_user_base_pricing').id)]
        elif vals.get('pricing_policy') and vals['pricing_policy'] == 'area':
            if self.env.ref('real_estate.group_user_base_pricing').id in self.env.ref(
                    'real_estate.group_rsms_manager').mapped('implied_ids').ids:
                self.env.ref('real_estate.group_rsms_manager').implied_ids = [
                    (3, self.env.ref('real_estate.group_user_base_pricing').id)]
                self.env.ref('real_estate.group_user_base_pricing').users = [(5,)]
        return super(Society, self).write(vals)
