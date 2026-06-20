# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree as ET


class PlotInventory(models.Model):
    _name = 'plot.inventory'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Plot Inventory'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char('Plot number')
    serial_number = fields.Char('Serial Number', required=True, copy=False, readonly=True, index=True,
                                default=lambda self: _('New'))
    state = fields.Selection([
        ('avalible_for_sale', 'Available For Sale'),
        ('sold', 'Sold'),
        ('rented', 'Rented'),
        ('ofc_reserve', 'Office Reservation'),
        ('reserved', 'Reserved'),
        ('investor', "Investor's Reservation"),
        ('dispute', 'Legal Dispute'),
        ('mortgage', 'Mortgage')], default='avalible_for_sale', tracking=True)

    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]", tracking=True)
    phase_id = fields.Many2one('society', 'Phase', required=True, tracking=True)
    sector_id = fields.Many2one('sector', tracking=True)
    street_id = fields.Many2one('street', tracking=True)
    location_id = fields.Many2one('location')
    size_id = fields.Many2one('unit.size', 'Size', tracking=True)
    demarcation_id = fields.Many2one('demarcated.area', 'Demarcation')
    standard_area = fields.Float('Standard Area (sft)', tracking=True)
    actual_area = fields.Float('Actual Area', tracking=True)
    street = fields.Many2one('location', "Street ")
    unit_category_type_id = fields.Many2one('unit.category.type', tracking=True)
    unit_class_id = fields.Many2one('unit.class', tracking=True)
    net_area = fields.Float(string='Net Area', tracking=True)
    balcony_area = fields.Float(tracking=True)
    category_id = fields.Many2one('plot.category', 'Category', tracking=True)
    possession_status = fields.Selection([
        ('pending', 'Pending'),
        ('given', 'Givin')], string='Possession Status', default='pending', readonly=True)
    preference_factor_ids = fields.Many2many('factor')
    dispute_id = fields.Many2one('legal.dispute')
    token_id = fields.Many2one('token.money', 'Token')
    investor_units = fields.Integer('No. of Units')
    price_list = fields.One2many('price.list.line', 'unit_inventory_id')
    land_details_ids = fields.One2many('land.details', 'inventory_id')

    # Land Details

    khasra = fields.Char()
    old_khasra = fields.Char()
    area_purchase = fields.Char()
    cost = fields.Float('Cost Paid')
    khatuni = fields.Char()
    registery_no = fields.Char()
    registery_type = fields.Char()
    city_id = fields.Many2one('city')
    mauza = fields.Char()

    # Ex Owner Details
    ex_owner = fields.Char()
    cnic = fields.Char()


    # Investors Field
    investment_id = fields.Many2one('investment')
    partner_id = fields.Many2one('res.member')
    deal_price = fields.Float(compute='_compute_deal_price', store=True, readonly=False)
    investor_unit_price = fields.Float()
    list_price = fields.Float(compute='get_sale_amount')

    @api.depends('price_list')
    def get_sale_amount(self):
        self.list_price = 0
        for rec in self:
            for recs in rec.price_list:
                rec.list_price = recs.price



    @api.depends('investor_unit_price')
    def _compute_deal_price(self):
        for rec in self:
            rec.deal_price = rec.investor_unit_price

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'street_id': [('sector_id', '=', self.sector_id.id)],
        }
        }

    def action_sold(self):
        self.state = 'sold'

    def action_reserved(self):
        self.state = 'reserved'

    def action_mortgage(self):
        self.state = 'mortgage'

    def action_cancel(self):
        self.state = 'avalible_for_sale'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('serial_number', _('New')) == _('New'):
                # phase_id = self.env['society'].search([('id', '=', vals['phase_id'])])
                sector_id = self.env['sector'].search([('id', '=', vals['sector_id'])])
                street_id = self.env['street'].search([('id', '=', vals['street_id'])])
                category_id = self.env['plot.category'].search([('id', '=', vals['category_id'])])
                unit_category_type_id = self.env['unit.category.type'].search([('id', '=', vals['unit_category_type_id'])])
                # size_id = self.env['unit.size'].search([('id', '=', vals['size_id'])])

                record = self.env['ir.sequence'].search([('code', '=', 'plot.inventory.%s.%s.%s' % (
                sector_id.code, category_id.code, unit_category_type_id.code))])
                if record and not street_id:
                    vals['serial_number'] = self.env['ir.sequence'].next_by_code(record.code) or _('New')
                elif record and street_id:
                    new_record = self.env['ir.sequence'].create({
                        'name': '%s %s %s %s' % (
                        sector_id.code, street_id.code, category_id.code, unit_category_type_id.code),
                        'code': 'plot.inventory.%s.%s.%s.%s' % (
                            sector_id.code, street_id.code, category_id.code, unit_category_type_id.code),
                        'prefix': "%s-%s/%s-%s/" % (
                        sector_id.code, street_id.code, category_id.code, unit_category_type_id.code),
                        'padding': 3,
                        'company_id': False
                    })

                    vals['serial_number'] = self.env['ir.sequence'].next_by_code(new_record.code) or _('New')
                else:
                    new_record = self.env['ir.sequence'].create({
                        'name': '%s %s %s' % (sector_id.code, category_id.code, unit_category_type_id.code),
                        'code': 'plot.inventory.%s.%s.%s' % (
                        sector_id.code, category_id.code, unit_category_type_id.code),
                        'prefix': "%s-/%s-%s/" % (sector_id.code, category_id.code, unit_category_type_id.code),
                        'padding': 3,
                        'company_id': False
                    })

                    vals['serial_number'] = self.env['ir.sequence'].next_by_code(new_record.code) or _('New')

        return super().create(vals_list)

    @api.constrains('name')
    def duplicate_data(self):
        for rec in self:
            data = self.search([('name', '=', rec.name), ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('Plot Inventory Is Already Present'))

    def unlink(self):
        if self.state != 'avalible_for_sale':
            raise ValidationError("You are not allowed to delete record in %s state." % self.state)
        return super(PlotInventory, self).unlink()

    @api.model
    def fields_view_get(self, view_id=None, view_type=False, toolbar=False, submenu=False):
        res = super(PlotInventory, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                         submenu=submenu)
        is_user = self.env.user.has_group('real_estate.group_can_create_edit_delete_record')

        if is_user:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='plot_inventory']")
                doc.set('edit', 'true')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='plot_inventory']")
                doc.set('edit', 'true')
                doc.set('create', 'true')
                res['arch'] = ET.tostring(doc)
        else:
            if view_type == 'form':
                doc = ET.XML(res['arch'])
                doc.xpath("//form[@name='plot_inventory']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

            if view_type == 'tree':
                doc = ET.XML(res['arch'])
                doc.xpath("//tree[@name='plot_inventory']")
                doc.set('edit', 'false')
                doc.set('create', 'false')
                res['arch'] = ET.tostring(doc)

        return res