# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Preference(models.Model):
    _name = 'preference'
    _rec_name = 'factor_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Plot Preference"

    factor_id = fields.Many2one('factor', 'Factor', required=True)
    basis = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix')
    ])
    file_value_type = fields.Selection([('sale_price', 'Sale Price'), ('net_price', 'Net Price')], default='sale_price', string='File Value')
    discount = fields.Float(string='Discount')
    value = fields.Float(store=True, related='factor_id.percentage')
    approved = fields.Boolean('Include in Price')
    total = fields.Float(store=True, compute='_compute_total_value', readonly=False)

    file_id = fields.Many2one('file')

    @api.depends('file_value_type', 'value', 'discount', 'basis')
    def _compute_total_value(self):
        for rec in self:
            if rec.basis:
                file_price = rec.file_id.sale_amount if rec.file_value_type == 'sale_price' else rec.file_id.net_sale_amount
                rec.total = rec.value if rec.basis == 'fix' else [file_price * rec.value / 100][0]
                if rec.discount:
                    rec.total -= rec.total * rec.discount / 100
                    rec.total = round(rec.total, 2)
                    if rec.total < 0:
                        rec.total = 0
                        rec.discount = 0
                        raise UserError(_('Discounted price cannot be negative.'))
    # @api.depends('value', 'basis', 'file_id.sale_amount')
    # def _compute_total_value(self):
    #     for rec in self:
    #         if rec.basis:
    #             rec.total = rec.value if rec.basis == 'fix' else [rec.file_id.sale_amount * rec.value / 100][0]

    @api.constrains('value', 'basis')
    def _check_percentage(self):
        for rec in self:
            if rec.basis == 'percentage' and rec.value > 100:
                raise ValidationError(_("Value in preferences could not exceed 100 percentage while basis is percentage"))


class Factor(models.Model):
    _name = 'factor'
    _description = "Factor"

    name = fields.Char(required=True)
    percentage = fields.Float(digits=(14, 4))
    product_id = fields.Many2one('product.product', string="Product")