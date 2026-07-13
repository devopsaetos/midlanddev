# -*- coding: utf-8 -*-
from odoo import fields, models


class PlotMergerApplicationMidlandExt(models.Model):
    _inherit = 'plot.merger.application'

    # real_estate/file_financials declare these as account.move (they can't depend on
    # midland_invoicing — it depends on them, via file_financials — so this is the only
    # module in the chain allowed to point them at midland.invoice).
    merger_fee_invoice_id = fields.Many2one('midland.invoice', string='Merger Fee Invoice')
    credit_note_id = fields.Many2many(
        'midland.invoice', 'plot_merger_credit_note_rel', string='Credit Note')
