from odoo import api, fields, models, _





class StockMoveExt(models.Model):
    _inherit = 'stock.move'

    transaction_type = fields.Char('Transaction Type')
    stock_transaction_id = fields.Many2one('stock.transaction')
    stock_transaction_line_id = fields.Many2one('stock.transaction.line')


    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in self:
            if move.picking_id:
                backdate = move.picking_id.scheduled_date
                if backdate:
                    m = move.with_context(force_period_date=backdate)
                    m.write({'date': backdate})
                    move_lines = self.env['stock.move.line'].search([('move_id', '=', m.id)])
                    move_lines.write({'date': backdate})
        return res

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        vals = super()._prepare_account_move_vals(credit_account_id, debit_account_id, journal_id, qty, description,
                                                  svl_id, cost)

        if self.picking_id and self.picking_id.scheduled_date:
            vals['date'] = self.picking_id.scheduled_date
        return vals






