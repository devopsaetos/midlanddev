# -*- coding: utf-8 -*-
import calendar

from odoo import api, fields, models


class ProjectReceivablesReport(models.AbstractModel):
    """PDF version of the wizard's Excel report - same rows, same columns."""
    _name = 'report.project_receivables_report.receivables_pdf'
    _description = 'Project Receivables Report (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['project.receivables.wizard'].browse(docids)
        reports = []
        for wizard in wizards:
            rows = wizard._rows()
            money_keys = [c[1] for c in wizard.COLUMNS if c[3] == 'money']
            reports.append({
                'title': wizard._report_title(),
                # Group company (root of the project's company tree - Shabraj
                # Developers for Capital Valley) for the logo and address.
                'company': (wizard.society_id.company_id.root_id or wizard.society_id.company_id
                            or self.env.company).sudo(),
                'month_label': '%s %s' % (calendar.month_name[int(wizard.month)], wizard.year),
                'rows': rows,
                'totals': {k: sum(r[k] or 0.0 for r in rows) for k in money_keys},
            })
        return {
            'doc_ids': docids,
            'doc_model': 'project.receivables.wizard',
            'docs': wizards,
            'reports': reports,
            'printed_by': self.env.user.name,
            'print_date': fields.Date.context_today(self).strftime('%d-%m-%Y'),
        }
