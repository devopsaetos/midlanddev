# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

DEFAULT_BANK = 'ALLIED BANK LIMITED A/C: 0010046647830014 BRANCH CODE: 0988 (MIDLAND DEVELOPERS PVT LTD)'
DEFAULT_NOTE = ('In case of online payment please use the above bank account and share the '
                'payment screenshot on WhatsApp, or submit the receipt at the society office.')


class MaintenanceBillGenerate(models.TransientModel):
    _name = 'maintenance.bill.generate'
    _description = 'Generate Maintenance Monthly Bills'

    bill_type = fields.Selection([('utility', 'Utility / Maintenance'), ('electricity', 'Electricity')],
                                 required=True, default=lambda self: self.env.context.get('default_bill_type') or 'utility')
    society_id = fields.Many2one('society', required=True, domain="[('is_society', '=', True)]")
    phase_id = fields.Many2one('society', domain="[('is_society', '!=', True), ('society_id', '=', society_id)]")
    unit_numbers = fields.Char(string='Only These Houses',
                               help='Plot / house numbers separated by commas, e.g. CV2-R-42, CV2-R-43. '
                                    'Leave empty to bill every file of the society/phase that has a member.')
    file_ids = fields.Many2many('file', string='Only These Houses',
                                domain="[('society_id', '=', society_id), ('phase_id', '=?', phase_id), ('membership_id', '!=', False)]",
                                help='Pick houses of the selected society / phase. Leave empty to bill every house that has a member.')
    bill_month = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    due_date = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1) + relativedelta(days=9))
    journal_id = fields.Many2one('account.journal', required=True, domain="[('type', '=', 'sale')]")

    utility_product_id = fields.Many2one('product.product',
                                         default=lambda self: self._default_product('Maintenance Charges'))
    default_utility_amount = fields.Float(
        string='Utility Charges', help='Used when no Maintenance Charges rule matches the file.')
    electricity_product_id = fields.Many2one('product.product',
                                             default=lambda self: self._default_product('Electricity'))
    unit_rate = fields.Float(string='Electricity Rate / Unit', digits=(16, 2))
    surcharge_percent = fields.Float(string='Late Surcharge %', default=10.0)
    bank_note = fields.Char(default=DEFAULT_BANK)
    payment_note = fields.Text(default=DEFAULT_NOTE)

    def _default_product(self, name):
        if name == 'Maintenance Charges':
            product = self.env['maintenance.charges']._get_maintenance_charges_product_id()
            if product:
                return product
        return self.env['product.product'].search([('name', '=', name), ('type', '=', 'service')], limit=1)

    @api.onchange('society_id')
    def _onchange_society(self):
        """Default to the sales journal of the company named like the society (CV-I -> Canal Valley-I)."""
        if self.society_id:
            company = self.env['res.company'].search([('name', '=', self.society_id.name)], limit=1) \
                or self.society_id.company_id
            self.journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
            self.phase_id = False
            self.file_ids = False
            if not self.journal_id:
                return {'warning': {
                    'title': _('Company not selected'),
                    'message': _('No sales journal found for %s. Tick that company in the company '
                                 'switcher (top right), then choose the society again.') % company.name,
                }}

    @api.onchange('phase_id')
    def _onchange_phase(self):
        # keep only houses that belong to the newly chosen phase
        if self.phase_id:
            self.file_ids = self.file_ids.filtered(lambda f: f.phase_id == self.phase_id)

    def _utility_amount_for(self, file_rec):
        """Same matching as the existing maintenance cron: rule line by category, unit class
        and marla range, then the type line for the utility product."""
        lines = self.env['maintenance.charges.line'].search([
            ('maintenance_charges_id.society_id', '=', file_rec.society_id.id),
            ('maintenance_charges_id.phase_id', '=', file_rec.phase_id.id),
            ('maintenance_charges_id.date_from', '<=', self.bill_month),
            ('maintenance_charges_id.date_to', '>=', self.bill_month),
            ('category_id', '=', file_rec.category_id.id),
        ])
        marla = round(file_rec.unit_category_type_id.area_marla or 0)
        for line in lines:
            if line.from_no <= marla <= line.to_no:
                rule = line.maintenance_charges_type_id.maintenance_charges_type_line_ids.filtered(
                    lambda l: l.product_id == self.utility_product_id)[:1]
                if rule:
                    return self._apply_exemption(file_rec, rule.amount)
        return self._apply_exemption(file_rec, self.default_utility_amount)

    def _apply_exemption(self, file_rec, amount):
        """Approved Maintenance Exemption of the file that covers the billed month."""
        if 'maintenance.exemption.history' not in self.env:
            return amount
        month_end = self.bill_month.replace(day=1) + relativedelta(months=1, days=-1)
        exemption = self.env['maintenance.exemption.history'].search([
            ('file_id', '=', file_rec.id), ('exemption_state', '=', 'active'),
            ('product_id', '=', self.utility_product_id.id),
            ('from_date', '<=', month_end), ('to_date', '>=', self.bill_month.replace(day=1)),
        ], limit=1)
        if not exemption:
            return amount
        if exemption.exemption_nature == 'full':
            return 0.0
        if exemption.exemption_type == 'percentage' and exemption.exemption_percent:
            return round(amount * (100 - exemption.exemption_percent) / 100.0, 2)
        if exemption.exemption_type == 'fixed_amount' and exemption.exemption_amount:
            return max(amount - exemption.exemption_amount, 0.0)
        return amount

    def action_generate(self):
        self.ensure_one()
        month = self.bill_month.replace(day=1)
        if self.file_ids:
            files = self.file_ids
        elif self.unit_numbers:
            wanted = [u.strip().upper() for u in self.unit_numbers.replace('\n', ',').split(',') if u.strip()]
            files = self.env['file'].search([('society_id', '=', self.society_id.id),
                                             ('unit_number', 'in', wanted), ('membership_id', '!=', False)])
            missing = set(wanted) - {(u or '').upper() for u in files.mapped('unit_number')}
            if missing:
                raise UserError(_('No file with a member found in %(society)s for: %(units)s',
                                  society=self.society_id.name, units=', '.join(sorted(missing))))
        else:
            domain = [('society_id', '=', self.society_id.id), ('membership_id', '!=', False)]
            if self.phase_id:
                domain.append(('phase_id', '=', self.phase_id.id))
            files = self.env['file'].search(domain)
        if not files:
            raise UserError(_('No files with a member found for this selection.'))

        if self.bill_type == 'utility' and not self.utility_product_id:
            raise UserError(_('Set the Utility product first.'))
        if self.bill_type == 'electricity' and not self.electricity_product_id:
            raise UserError(_('Set the Electricity product first.'))
        Bill = self.env['maintenance.bill']
        # a house gets one bill of this type per month (an old combined bill counts as both)
        existing = Bill.search([('file_id', 'in', files.ids), ('bill_month', '=', month), ('state', '!=', 'cancel'),
                                ('bill_type', 'in', (self.bill_type, 'combined'))])
        vals_list = []
        for file_rec in files - existing.mapped('file_id'):
            vals = {
                'bill_type': self.bill_type,
                'file_id': file_rec.id,
                'journal_id': self.journal_id.id,
                'bill_month': month,
                'due_date': self.due_date,
                'surcharge_percent': self.surcharge_percent,
                'bank_note': self.bank_note,
                'payment_note': self.payment_note,
            }
            if self.bill_type == 'utility':
                vals.update({
                    'utility_product_id': self.utility_product_id.id,
                    'utility_amount': self._utility_amount_for(file_rec),
                })
            else:
                # the meter continues from the last electricity reading of this house
                last = Bill.search([('file_id', '=', file_rec.id), ('bill_month', '<', month), ('state', '!=', 'cancel'),
                                    ('bill_type', 'in', ('electricity', 'combined'))], order='bill_month desc', limit=1)
                vals.update({
                    'electricity_product_id': self.electricity_product_id.id,
                    'meter_no': last.meter_no or file_rec.meter_no,
                    'previous_reading': last.current_reading if last else file_rec.opening_meter_reading,
                    'unit_rate': self.unit_rate,
                })
            vals_list.append(vals)
        bills = Bill.create(vals_list)
        bills.action_recompute_arrears()

        kind = dict(self._fields['bill_type']._description_selection(self.env))[self.bill_type]
        return {
            'type': 'ir.actions.act_window',
            'name': _('%(kind)s Bills %(month)s (%(new)s new, %(skip)s already existed)', kind=kind,
                      month=month.strftime('%b %Y'), new=len(bills), skip=len(existing)),
            'res_model': 'maintenance.bill',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (bills | existing).ids)],
            'views': [(self.env.ref('maintenance_monthly_bill.maintenance_bill_list_%s' % self.bill_type).id, 'list'),
                      (False, 'form')],
            'context': {'search_default_group_state': 0, 'default_bill_type': self.bill_type},
        }
