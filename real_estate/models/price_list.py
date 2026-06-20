# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import functools
from datetime import date
from dateutil.relativedelta import relativedelta


def is_set(list):
    try:
        def func(s, o):
            if o in s:
                raise Exception
            return s.union([o])

        functools.reduce(func, list, set())
        return True
    except:
        return False


def dynamic_selection():

    select = [('unit', "Unit"), ('generic', "Generic"), ('sq_ft', 'Area Based')]
    return select


class PriceList(models.Model):
    _name = 'price.list'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Price List"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True)

    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', required=True)
    starting_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    price_list_type = fields.Selection(selection=lambda self: dynamic_selection(), default="unit")
    pricelist_line = fields.One2many('price.list.line', 'line_id')
    price_list_line_generic = fields.One2many('price.list.line', 'line_id')

    @api.onchange('society_id', 'phase_id')
    def _phase_domain(self):
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
        }
        }

    @api.onchange('society_id')
    def _reset_values(self):
        for rec in self:
            if rec.society_id:
                rec.phase_id = ''

    @api.constrains('pricelist_line', 'starting_date', 'end_date')
    def _check_double(self):
        record = self.search(
            [('id', '!=', self.id), ('society_id', '=', self.society_id.id), ('phase_id', '=', self.phase_id.id),
             '|',
             '|',
             '|',
             '&',
             ('starting_date', '<=', self.starting_date),
             ('end_date', '=', False),

             '&',
             ('starting_date', '<=', self.starting_date),
             ('end_date', '>=', self.starting_date),

             '|',
             '&',
             ('starting_date', '<=', self.end_date),
             ('end_date', '=', False),

             '&',
             ('starting_date', '<=', self.end_date),
             ('end_date', '>=', self.end_date),
             '&',
             ('starting_date', '>=', self.starting_date),
             ('end_date', '<=', self.end_date),

             ]
        )

        if not record and not self.end_date:
            record = self.search([
                ('starting_date', '>=', self.starting_date),
                ('id', '!=', self.id),
                ('society_id', '=', self.society_id.id),
                ('phase_id', '=', self.phase_id.id),
            ])

        if record:
            raise ValidationError(_("Dates are already fall in Price List :: %s" % (record.mapped('name')[0])))

        # if not is_set([(rec.size_id.id, rec.category_id.id, rec.sector_id.id,) for rec in self.pricelist_line]):
        #     raise ValidationError(_("Duplication in same category"))

    def write(self,vals):
        res = super(PriceList, self).write(vals)
        mx_sdate = self.pricelist_line.search([('line_id', '=', self.id)]).mapped('starting_date')
        # p_lines = max(mx_sdate) if mx_sdate else False
        # if p_lines:
        #     sql_query = '''
        #         SELECT min(id)
        #         FROM price_list_line
        #         WHERE line_id = %s
        #         and  end_date > (
        #             SELECT max(starting_date)
        #             FROM price_list_line
        #             WHERE line_id = %s
        #             )
        #         );''' %(self.id,self.id)
        #     self.env.cr.execute(sql_query)
        #     result = self.env.cr.fetchall()
        #     record = self.pricelist_line.browse(result[0][0])
        #     record.end_date = fields.Date.from_string(p_lines) + relativedelta(days=-1)

        return res


class PriceListLine(models.Model):
    _name = 'price.list.line'
    _description = "Price List Line"

    size_id = fields.Many2one('unit.size', store=True, related='unit_inventory_id.size_id', readonly=False)
    category_id = fields.Many2one('plot.category', required=True, store=True, related='unit_inventory_id.category_id', readonly=False)
    unit_class_id = fields.Many2one('unit.class', store=True, related='unit_inventory_id.unit_class_id', readonly=False)
    unit_category_type_id = fields.Many2one('unit.category.type',
                                            required=True, store=True, related='unit_inventory_id.unit_category_type_id', readonly=False)
    unit_inventory_id = fields.Many2one('plot.inventory')
    area = fields.Integer(string='Area')
    starting_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    sector_id = fields.Many2one('sector', store=True, related='unit_inventory_id.sector_id', readonly=False)
    price = fields.Float()
    line_id = fields.Many2one('price.list')


    @api.onchange('sector_id')
    def _domain_sector_id(self):
        return {'domain': {
            'sector_id': [
                ('phase_id', '=', self.line_id.phase_id.id),
            ]
        }}

    @api.constrains('unit_inventory_id', 'starting_date', 'end_date')
    def _check_double(self):
        for rec in self:
            if rec.end_date > rec.line_id.end_date:
                raise ValidationError(_("You can not exceed ending date of price list."))

            if rec.starting_date < rec.line_id.starting_date:
                raise ValidationError(_("You can not fix starting date, less then the starting date of the price list."))


            if rec.starting_date > rec.end_date:
                raise ValidationError(_("End Date must come after Start Date."))

            record = []
            if rec.unit_inventory_id:
                record = rec.search(
                    [
                        ('id', '!=', rec.id),
                        ('line_id', '=', rec.line_id.id),
                        ('unit_inventory_id', '=', rec.unit_inventory_id.id),
                        ('unit_category_type_id', '=', rec.unit_category_type_id.id),
                        ('category_id', '=', rec.category_id.id),
                        ('size_id', '=', rec.size_id.id),
                        ('sector_id', '=', rec.sector_id.id)
                    ])
                if record:
                    raise ValidationError(_("New line with same entries are not allowed."))
            else:
                record = rec.search(
                    [
                        ('id', '!=', rec.id),
                        ('line_id', '=', rec.line_id.id),
                        ('unit_category_type_id', '=', rec.unit_category_type_id.id),
                        ('category_id', '=', rec.category_id.id),
                        ('size_id', '=', rec.size_id.id),
                        ('sector_id', '=', rec.sector_id.id)
                    ])
                if record:
                    raise ValidationError(_("New line with same entries are not allowed."))

            #     if recs and recs.starting_date == self.starting_date:
            #         raise ValidationError(_("New Line with same starting date is not allowed"))
                # if self.starting_date < rec.starting_date:
                #     raise ValidationError(_("New Line with starting date less then the starting dates of other lines is not allowed"))

    @api.onchange('size_id')
    def on_line_create(self):
        if not self.starting_date and not self.end_date:
            self.starting_date, self.end_date = self.line_id.starting_date, self.line_id.end_date

    # @api.onchange('size_id', 'category_id', 'sector_id')
    # def _inventory_domain(self):
    #     return {'domain': {
    #         'unit_inventory_id': [
    #             ('size_id', '=', self.size_id.id),
    #             ('category_id', '=', self.category_id.id),
    #             ('sector_id', '=', self.sector_id.id)
    #         ]
    #     }
    #     }

    @api.onchange('unit_inventory_id')
    def _unit_inventory_id(self):
        if self.unit_inventory_id:
            self.area = self.unit_inventory_id.standard_area
        else:
            self.area = 0
        return {
            'domain': {
                'unit_inventory_id': [('phase_id', '=', self.line_id.phase_id.id)],
            }
        }
