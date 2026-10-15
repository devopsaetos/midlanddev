# -*- coding: utf-8 -*-
from odoo import api, models


class ReportPettyCashSummary(models.AbstractModel):
    _name = 'report.dev_petty_cash.report_petty_cash_summary'
    _description = 'Petty Cash Report (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['petty.cash.report'].browse(docids)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'petty.cash.report',
            'docs': docs,
            'report_data': {wiz.id: wiz._get_report_data() for wiz in docs},
        }
