from odoo import api, fields, models, _


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductProduct, self.with_context(create_product_product=True)).create(vals_list)
        for product, vals in zip(products, vals_list):
            if not (self.env.context.get('create_from_tmpl') and len(product.product_tmpl_id.product_variant_ids) == 1):
                product._set_standard_price(vals.get('standard_price') or 0.0)
        # self.clear_caches()
        return products

    def write(self, values):
        res = super(ProductProduct, self).write(values)
        if 'standard_price' in values:
            self._set_standard_price(values['standard_price'])
        # if 'attribute_value_ids' in values:
        #     self.clear_caches()
        return res


    def _set_standard_price(self, value):
        ''' Store the standard price change in order to be able to retrieve the cost of a product for a given date'''
        PriceHistory = self.env['product.price.history']
        for product in self:
            active_obj = False
            active_model = self._context.get('active_model') if self._context.get('active_model') else (self._context.get('params').get('model') if self._context.get('params') else False)
            active_id = self._context.get('active_id') if self._context.get('active_id') else (self._context.get('params').get('id') if self._context.get('params') else False)
            if active_model and active_id:
                active_obj = self.env[active_model].browse(active_id)
            PriceHistory.create({
                'product_id': product.id,
                'cost': value,
                'company_id': self._context.get('force_company', self.env.company.id),
                'datetime': active_obj.date_planned if active_obj and active_model == 'purchase.order' else (active_obj.date_start if active_obj and active_model == 'mrp.production' else fields.Date.today()),
                'stock_move_id': self._context.get('stock_move_id') or False,
                'reference': self.name if active_model == 'product.template' else (active_obj.name if active_obj else False)
            })


class ProductPriceHistory(models.Model):
    _name = 'product.price.history'
    _rec_name = 'datetime'
    _order = 'datetime desc'
    _description = 'Product Price List History'

    def _get_default_company_id(self):
        return self._context.get('force_company', self.env.company.id)


    company_id = fields.Many2one('res.company', string='Company',
                                 default=_get_default_company_id, required=True)
    product_id = fields.Many2one('product.product', 'Product', ondelete='cascade', required=True)
    datetime = fields.Date('Date')
    reference = fields.Char()
    stock_move_id = fields.Many2one('stock.move', 'Stock Move')
    cost = fields.Float('Cost', digits=(16, 2))




