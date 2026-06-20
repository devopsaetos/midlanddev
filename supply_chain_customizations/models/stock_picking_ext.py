from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        if any(hasattr(p, 'production_ids') and p.production_ids for p in self):
            return super(StockPicking, self.sudo()).button_validate()
        return super().button_validate()

    def _action_done(self):
        for picking in self:
            backdate = picking._get_backdate()
            if backdate:
                picking = picking.with_context(force_period_date=backdate)
                picking.write({'scheduled_date': backdate, 'date_done': backdate})
        return super()._action_done()

    def _get_backdate(self):
        ctx = self.env.context
        if ctx.get('active_model') == 'sale.order':
            return self.env['sale.order'].browse(ctx.get('active_id')).date_order
        if ctx.get('active_model') == 'purchase.order':
            return self.env['purchase.order'].browse(ctx.get('active_id')).date_order
        if ctx.get('active_model') == 'mrp.production':
            return self.env['mrp.production'].browse(ctx.get('active_id')).date_start
        return fields.Datetime.now()
