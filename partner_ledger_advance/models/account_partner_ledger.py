# -*- coding: utf-8 -*-
from copy import deepcopy

from odoo import _, models
from odoo.tools import SQL

OPENING = 'opening_balance'


class PartnerLedgerCustomHandler(models.AbstractModel):
    """Partner Ledger: an Opening Balance column next to Debit / Credit, the Balance column
    titled Closing Balance, and each unfolded partner framed by an Opening Balance line
    (always, even when zero) and a Closing Balance line. Opening and closing include the
    advance accounts (see account_report.py)."""
    _inherit = 'account.partner.ledger.report.handler'

    def _show_opening_closing(self, options):
        return any(col['expression_label'] == OPENING for col in options.get('columns', []))

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # only the Partner Ledger itself, not the reports built on this handler (follow-ups)
        if self._name != 'account.partner.ledger.report.handler' or options.get('hide_initial_balance'):
            return
        columns = []
        for column in options['columns']:
            if column['expression_label'] == 'debit':
                opening = deepcopy(column)
                opening.update({'expression_label': OPENING, 'name': _('Opening Balance')})
                columns.append(opening)
            if column['expression_label'] == 'balance':
                column = dict(column, name=_('Closing Balance'))
            columns.append(column)
        options['columns'] = columns

    # ------------------------------------------------------------------ values
    @staticmethod
    def _set_opening(values):
        values[OPENING] = (values.get('balance') or 0.0) - (values.get('debit') or 0.0) + (values.get('credit') or 0.0)

    def _get_report_line_partners(self, options, partner, partner_values, level_shift=0):
        for values in partner_values.values():
            self._set_opening(values)
        return super()._get_report_line_partners(options, partner, partner_values, level_shift=level_shift)

    def _get_report_line_total(self, options, totals_by_column_group):
        for values in totals_by_column_group.values():
            self._set_opening(values)
        return super()._get_report_line_total(options, totals_by_column_group)

    def _get_additional_column_aml_values(self):
        # journal item lines have no opening balance (empty cell)
        return SQL('%s NULL::numeric AS opening_balance,', super()._get_additional_column_aml_values())

    def _get_order_by_aml_values(self):
        # Within one entry list the debit lines first (Dr before Cr): an advance applied to a
        # bill otherwise shows its advance-side credit first and the running balance dips.
        return SQL('account_move_line.date, account_move_line.move_id, account_move_line.balance DESC, account_move_line.id')

    def _get_initial_balance_values(self, partner_ids, options):
        result = super()._get_initial_balance_values(partner_ids, options)
        for by_group in result.values():
            for group_key, values in by_group.items():
                # a partner with nothing before the period still gets a 0.00 opening line
                values = dict(values)
                values.setdefault('debit', 0.0)
                values.setdefault('credit', 0.0)
                values['balance'] = values.get('balance') or 0.0
                values[OPENING] = values['balance']
                by_group[group_key] = values
        return result

    # ------------------------------------------------------------------ lines
    def _report_expand_unfoldable_line_partner_ledger(self, line_dict_id, groupby, options, progress, offset,
                                                      unfold_all_batch_data=None):
        result = super()._report_expand_unfoldable_line_partner_ledger(
            line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=unfold_all_batch_data)
        if not self._show_opening_closing(options):
            return result
        report = self.env['account.report'].browse(options['report_id'])
        for line in result['lines']:
            if report._parse_line_id(line['id'])[-1][0] == 'initial':
                line['name'] = _('Opening Balance')
        if not result['has_more']:
            closing = result.get('progress') or progress or {}
            columns = []
            for column in options['columns']:
                if column['expression_label'] == 'balance':
                    columns.append(report._build_column_dict(closing.get(column['column_group_key'], 0.0), column,
                                                             options=options))
                else:
                    columns.append(report._build_column_dict(None, None))
            level = result['lines'][0]['level'] if result['lines'] else 3
            result['lines'].append({
                'id': report._get_generic_line_id(None, None, parent_line_id=line_dict_id, markup='closing'),
                'name': _('Closing Balance'),
                'level': level,
                'parent_id': line_dict_id,
                'columns': columns,
            })
        return result
