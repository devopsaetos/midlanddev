# -*- coding: utf-8 -*-
from odoo import api, models
class MidlandMembershipReport(models.AbstractModel):
    """
    Report parser for the combined Membership Form + Installment Plan PDF.
    Kept thin on purpose: all heavy field logic already lives on file/res.member,
    here we just expose convenience helpers to the QWeb template so the XML
    stays readable.
    """
    _name = 'report.midland_report.report_midland_membership_document'
    _description = 'Midland Membership Form Report Parser'

    def _get_kin_lines(self, file):
        """
        Next of Kin priority: file-specific kin lines first (per booking/file),
        fall back to the member's permanent kin lines if the file has none.
        """
        if file.kin_line_ids:
            return file.kin_line_ids
        return file.membership_id.kin_line_ids

    def _get_relation_label(self, kin_line):
        """Return a human readable relation label (selection label or custom 'other' text)."""
        if not kin_line:
            return ''
        if kin_line.relation_with_member == 'other' and kin_line.relation_name:
            return kin_line.relation_name
        selection = dict(kin_line._fields['relation_with_member'].selection)
        return selection.get(kin_line.relation_with_member, '')

    @api.model
    def _get_report_values(self, docids, data=None):
        files = self.env['file'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'file',
            'docs': files,
            'get_kin_lines': self._get_kin_lines,
            'get_relation_label': self._get_relation_label,
        }
