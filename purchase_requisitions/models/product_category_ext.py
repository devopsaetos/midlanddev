# -*- coding: utf-8 -*-

from odoo import api, fields, models, _



class ProductCategoryExt(models.Model):
    _inherit = "product.category"

    is_expense = fields.Boolean(string='Expense')

    @api.depends('name')
    def name_get(self):
        result = []
        for record in self:
            if self.env.context.get('from_purchasing'):
                name = record.name
            else:
                name = record.complete_name
            result.append((record.id, name))
        return result