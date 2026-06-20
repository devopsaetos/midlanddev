# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.product_tmpl_id:
                values_str = ", ".join(record.value_ids.mapped('name'))
                record.product_tmpl_id.message_post(body=_("Attribute Line Added: %s (%s)") % (record.attribute_id.name, values_str))
        return records

    def write(self, vals):
        if 'value_ids' in vals:
            for record in self:
                old_values = ", ".join(record.value_ids.mapped('name'))
                res = super(ProductTemplateAttributeLine, record).write(vals)
                new_values = ", ".join(record.value_ids.mapped('name'))
                if old_values != new_values:
                    record.product_tmpl_id.message_post(body=_("Attribute Values Updated for %s: %s -> %s") % (record.attribute_id.name, old_values, new_values))
                return res
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.product_tmpl_id:
                record.product_tmpl_id.message_post(body=_("Attribute Line Deleted: %s") % record.attribute_id.name)
        return super().unlink()
