# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductRealestate(models.Model):
    _name = 'product.realestate'
    _description = 'Real Estate Product'
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    description = fields.Char()
    type = fields.Selection([('service', 'Service')], default='service')
    is_include_net_amount = fields.Boolean(string='Include in Net Amount')
    is_include_property_system = fields.Boolean(string='Include in Property System')
    product_id = fields.Many2one('product.product', string='Accounting Product',
                                  readonly=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.product_id:
                shadow = self.env['product.product'].sudo().create({
                    'name': rec.name,
                    'type': rec.type or 'service',
                    'description': rec.description,
                    'is_include_net_amount': rec.is_include_net_amount,
                    'is_include_property_system': rec.is_include_property_system,
                    'sale_ok': False,
                    'purchase_ok': False,
                })
                rec.product_id = shadow
        return records

    def unlink(self):
        if self.ids:
            # Clear transient invoice popup lines (bypass FK constraint timing)
            self.env.cr.execute(
                "DELETE FROM invoice_popup_line WHERE product_id IN %s",
                (tuple(self.ids),)
            )
            shadow_ids = tuple(self.mapped('product_id').ids)
            if shadow_ids:
                self.env.cr.execute(
                    "DELETE FROM invoice_popup_line WHERE product_id IN %s",
                    (shadow_ids,)
                )
                # Archive shadow products that have accounting history;
                # delete the rest so they don't accumulate as orphans.
                used_ids = set(self.env['account.move.line'].sudo().search(
                    [('product_id', 'in', list(shadow_ids))]
                ).mapped('product_id').ids)
                archive_ids = list(used_ids & set(shadow_ids))
                delete_ids = list(set(shadow_ids) - used_ids)
                if archive_ids:
                    self.env['product.product'].sudo().browse(archive_ids).write({'active': False})
                if delete_ids:
                    self.env['product.product'].sudo().browse(delete_ids).unlink()
        return super().unlink()

    def write(self, vals):
        res = super().write(vals)
        sync = {'name', 'type', 'description', 'is_include_net_amount',
                'is_include_property_system', 'active'}
        if sync & vals.keys():
            for rec in self:
                if rec.product_id:
                    shadow_vals = {k: vals[k] for k in sync & vals.keys()}
                    rec.product_id.sudo().write(shadow_vals)
        return res
