# -*- coding: utf-8 -*-

import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


BILL_TYPES = [
    ('utility', 'Utility / Maintenance'),
    ('electricity', 'Electricity'),
    ('combined', 'Utility + Electricity (old)'),
]


class MaintenanceBill(models.Model):
    """One printed monthly bill of a file: utility charge + electricity from meter readings
    + arrears. Posting it creates the invoices (and Maintenance History rows) that the
    existing maintenance payment screens already know how to collect."""
    _name = 'maintenance.bill'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Maintenance Monthly Bill'
    _order = 'bill_month desc, society_id, unit_number, id'

    name = fields.Char(default=lambda self: _('New'), readonly=True, copy=False, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    # Utility and electricity are billed separately: one bill (and one invoice, one PDF) per
    # charge. 'combined' only for bills posted before that (one bill with both charges).
    bill_type = fields.Selection(BILL_TYPES, string='Bill Type', required=True, index=True, tracking=True,
                                 default=lambda self: self.env.context.get('default_bill_type') or 'utility')
    file_id = fields.Many2one('file', required=True, index=True, tracking=True)
    partner_id = fields.Many2one('res.partner', related='file_id.membership_id.partner_id', store=True)
    member_name = fields.Char(related='file_id.membership_id.name', string='Member')
    unit_number = fields.Char(related='file_id.unit_number', store=True, string='Plot / House')
    society_id = fields.Many2one('society', related='file_id.society_id', store=True)
    phase_id = fields.Many2one('society', related='file_id.phase_id', store=True)
    journal_id = fields.Many2one('account.journal', required=True, domain="[('type', '=', 'sale')]")
    company_id = fields.Many2one('res.company', related='journal_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    bill_month = fields.Date(required=True, tracking=True, help='First day of the billed month.')
    issue_date = fields.Date(default=fields.Date.context_today)
    due_date = fields.Date(required=True)

    maintenance_charges_type_id = fields.Many2one('maintenance.charges.type', string='Charge Type', tracking=True,
                                                  help='Maintenance Charges type of the house (by size), e.g. 5 Marla.')
    utility_product_id = fields.Many2one('product.product')
    utility_amount = fields.Monetary(string='Utility Charges', tracking=True)

    electricity_product_id = fields.Many2one('product.product')
    meter_no = fields.Char()
    previous_reading = fields.Float(digits=(16, 0))
    current_reading = fields.Float(digits=(16, 0), tracking=True)
    units = fields.Float(compute='_compute_amounts', store=True, digits=(16, 0))
    unit_rate = fields.Float(string='Rate / Unit', digits=(16, 2))
    electricity_amount = fields.Monetary(compute='_compute_amounts', store=True, string='Electricity Charges')

    # Arrears are a snapshot taken when the bill is generated (or recomputed while draft).
    arrears_utility = fields.Monetary(string='Utility Arrears')
    arrears_electricity = fields.Monetary(string='Electricity Arrears')
    arrears = fields.Monetary(compute='_compute_amounts', store=True)
    current_amount = fields.Monetary(compute='_compute_amounts', store=True, string='Current Month')
    due_amount = fields.Monetary(compute='_compute_amounts', store=True, string='Due Amount')
    surcharge_percent = fields.Float(default=10.0, string='Late Surcharge %')
    surcharge = fields.Monetary(compute='_compute_amounts', store=True, string='Surcharge on Late Payment')
    payable_after_due = fields.Monetary(compute='_compute_amounts', store=True, string='Payable After Due Date')

    bank_note = fields.Char(string='Bank Account Line')
    payment_note = fields.Text()

    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False,
                                 help='The invoice of this bill (utility and electricity lines).')
    # Bills posted before one-invoice-per-bill have a separate invoice per charge; newer bills
    # point both fields at invoice_id.
    utility_invoice_id = fields.Many2one('account.move', readonly=True, copy=False)
    electricity_invoice_id = fields.Many2one('account.move', readonly=True, copy=False)

    # what the member has paid on this month's invoices (arrears are paid on their own invoices)
    paid_amount = fields.Monetary(compute='_compute_payment', store=True, string='Paid')
    payment_state = fields.Selection([
        ('none', 'Not Posted'),
        ('not_paid', 'Not Paid'),
        ('partial', 'Partly Paid'),
        ('paid', 'Paid'),
    ], compute='_compute_payment', store=True, string='Payment')

    @api.depends('state', 'invoice_id.amount_residual', 'invoice_id.amount_total',
                 'utility_invoice_id.amount_residual', 'electricity_invoice_id.amount_residual',
                 'utility_invoice_id.amount_total', 'electricity_invoice_id.amount_total')
    def _compute_payment(self):
        for rec in self:
            invoices = rec._invoices()
            total = sum(invoices.mapped('amount_total'))
            due = sum(invoices.mapped('amount_residual'))
            rec.paid_amount = total - due
            if rec.state != 'posted' or not invoices:
                rec.payment_state = 'none'
            elif not due:
                rec.payment_state = 'paid'
            elif due < total:
                rec.payment_state = 'partial'
            else:
                rec.payment_state = 'not_paid'

    @api.onchange('maintenance_charges_type_id')
    def _onchange_maintenance_charges_type(self):
        """Choosing another charge type on a draft bill takes its product and amount."""
        lines = self.maintenance_charges_type_id.maintenance_charges_type_line_ids
        charge = lines.filtered(lambda l: l.product_id == self.utility_product_id)[:1] or lines[:1]
        if charge:
            self.utility_product_id = charge.product_id
            self.utility_amount = charge.amount

    def _has_utility(self):
        return self.bill_type in ('utility', 'combined')

    def _has_electricity(self):
        return self.bill_type in ('electricity', 'combined')

    @api.depends('bill_type', 'previous_reading', 'current_reading', 'unit_rate', 'utility_amount',
                 'arrears_utility', 'arrears_electricity', 'surcharge_percent')
    def _compute_amounts(self):
        for rec in self:
            electricity = rec._has_electricity()
            rec.units = max(rec.current_reading - rec.previous_reading, 0.0) if electricity and rec.current_reading else 0.0
            rec.electricity_amount = round(rec.units * rec.unit_rate)
            utility_amount = rec.utility_amount if rec._has_utility() else 0.0
            rec.arrears = (rec.arrears_utility if rec._has_utility() else 0.0) + \
                (rec.arrears_electricity if electricity else 0.0)
            rec.current_amount = utility_amount + rec.electricity_amount
            rec.due_amount = rec.current_amount + rec.arrears
            rec.surcharge = round(rec.due_amount * rec.surcharge_percent / 100.0)
            rec.payable_after_due = rec.due_amount + rec.surcharge

    @api.constrains('previous_reading', 'current_reading')
    def _check_readings(self):
        for rec in self:
            if rec.current_reading and rec.current_reading < rec.previous_reading:
                raise ValidationError(_('%(unit)s: current reading (%(cur)s) is lower than previous reading (%(prev)s).',
                                        unit=rec.unit_number, cur=rec.current_reading, prev=rec.previous_reading))

    @api.constrains('file_id', 'bill_month', 'state', 'bill_type')
    def _check_one_bill_per_month(self):
        """One utility bill and one electricity bill per house and month (an old combined
        bill counts as both)."""
        overlapping = {'utility': ['utility', 'combined'], 'electricity': ['electricity', 'combined'],
                       'combined': ['utility', 'electricity', 'combined']}
        for rec in self.filtered(lambda r: r.state != 'cancel'):
            dup = self.search_count([('id', '!=', rec.id), ('file_id', '=', rec.file_id.id),
                                     ('bill_month', '=', rec.bill_month), ('state', '!=', 'cancel'),
                                     ('bill_type', 'in', overlapping[rec.bill_type])])
            if dup:
                raise ValidationError(_('%(unit)s already has a %(type)s bill for %(month)s.',
                                        unit=rec.unit_number, month=rec.bill_month.strftime('%b %Y'),
                                        type=dict(BILL_TYPES)[rec.bill_type]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('bill_month'):
                vals['bill_month'] = fields.Date.to_date(vals['bill_month']).replace(day=1)
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('maintenance.bill') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda r: r.state == 'posted'):
            raise UserError(_('Posted bills cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------ arrears
    def _arrears_for(self, charge_type):
        """Outstanding amount before this bill's month for one charge type."""
        self.ensure_one()
        return self.file_id._maintenance_arrears(charge_type, self.bill_month)

    def action_recompute_arrears(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Arrears can only be recomputed on draft bills.'))
            rec.write({
                'arrears_utility': rec._arrears_for('utility') if rec._has_utility() else 0.0,
                'arrears_electricity': rec._arrears_for('electricity') if rec._has_electricity() else 0.0,
            })

    # ------------------------------------------------------------------ posting
    def _invoice_lines(self):
        """[(charge type, line values)] of this bill's invoice: one line per charge."""
        self.ensure_one()
        month = self.bill_month.strftime('%b %Y')
        lines = []
        if self._has_utility() and self.utility_amount > 0:
            if not self.utility_product_id:
                raise UserError(_('%s: set the Utility product first.') % self.name)
            lines.append(('utility', {
                'product_id': self.utility_product_id.id,
                'name': _('%(charge)s %(month)s', charge=self.maintenance_charges_type_id.name, month=month)
                if self.maintenance_charges_type_id else _('Utility / Maintenance Charges %s') % month,
                'quantity': 1,
                'price_unit': self.utility_amount,
                'tax_ids': [(6, 0, [])],
            }))
        if self._has_electricity() and self.electricity_amount > 0:
            if not self.electricity_product_id:
                raise UserError(_('%s: set the Electricity product first.') % self.name)
            lines.append(('electricity', {
                'product_id': self.electricity_product_id.id,
                'name': _('Electricity %(month)s: %(units)s units (%(prev)s to %(cur)s) @ %(rate)s',
                          month=month, units=int(self.units), prev=int(self.previous_reading),
                          cur=int(self.current_reading), rate=self.unit_rate),
                # the bill rounds the electricity charge: invoice exactly what the bill shows
                'quantity': 1,
                'price_unit': self.electricity_amount,
                'tax_ids': [(6, 0, [])],
            }))
        return lines

    def _make_invoice(self, lines):
        """One invoice for the whole bill (utility and electricity lines)."""
        self.ensure_one()
        kinds = [kind for kind, _vals in lines]
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'journal_id': self.journal_id.id,
            'invoice_date': self.bill_month,
            'invoice_date_due': self.due_date,
            # a bill with utility is a maintenance invoice (the payment screens list those);
            # electricity alone stays a society-charges invoice as before
            'property_invoice_type': 'maintenance_charges' if 'utility' in kinds else 'society_charges',
            'ref': self.name,
            'invoice_line_ids': [(0, 0, vals) for _kind, vals in lines],
        })
        # Set after create, like the maintenance cron: real_estate's account.move.create()
        # strips file_ids from the values and logs a file payment-history row instead.
        move.file_ids = self.file_id
        move.action_post()
        return move

    def _add_history(self, invoice, charge_type, amount):
        last = self.file_id.maintenance_history_ids.sorted(lambda h: h.installment_number)[-1:]
        self.env['maintenance.charges.history'].create({
            'file_id': self.file_id.id,
            'date': self.bill_month,
            'charge_type': charge_type,
            'installment_number': (last.installment_number or 0) + 1,
            'amount': amount,
            'invoice_created': True,
            'invoice_id': invoice.id,
        })

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.partner_id:
                raise UserError(_('%s: the file has no member / accounting partner.') % rec.unit_number)
            if rec.journal_id.type != 'sale':
                raise UserError(_('%(bill)s: pick a Sales journal, not "%(journal)s" (%(type)s).',
                                  bill=rec.name, journal=rec.journal_id.name, type=rec.journal_id.type))
            if rec._has_electricity() and rec.bill_type == 'electricity':
                if not rec.current_reading:
                    raise UserError(_('%(bill)s (%(unit)s): enter the Current Reading before posting.',
                                      bill=rec.name, unit=rec.unit_number))
                if rec.unit_rate <= 0:
                    raise UserError(_('%(bill)s (%(unit)s): set the Rate / Unit before posting.',
                                      bill=rec.name, unit=rec.unit_number))
            if rec.bill_type == 'utility' and rec.utility_amount <= 0:
                raise UserError(_('%(bill)s (%(unit)s): Utility Charges are 0. Enter the amount, or cancel the bill '
                                  'if the house pays nothing this month.', bill=rec.name, unit=rec.unit_number))
            lines = rec._invoice_lines()
            vals = {'state': 'posted'}
            if lines:
                invoice = rec._make_invoice(lines)
                # one history row per charge, all on the same invoice: the reports and the
                # arrears split the invoice per charge from these rows
                for kind, line in lines:
                    rec._add_history(invoice, kind, line['price_unit'] * line['quantity'])
                vals['invoice_id'] = invoice.id
                # kept for the screens/reports that look a bill up by its old invoice fields
                if any(kind == 'utility' for kind, _line in lines):
                    vals['utility_invoice_id'] = invoice.id
                if any(kind == 'electricity' for kind, _line in lines):
                    vals['electricity_invoice_id'] = invoice.id
            rec.write(vals)
        return True

    def _invoices(self):
        self.ensure_one()
        return self.invoice_id | self.utility_invoice_id | self.electricity_invoice_id

    def action_cancel(self):
        if self.filtered(lambda r: r.state == 'posted'):
            raise UserError(_('Posted bills cannot be cancelled here: cancel or reverse their invoices in Accounting first.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})

    def action_receive_payment(self):
        """Open Maintenance Charges Payment with this bill's unpaid invoices filled in."""
        self.ensure_one()
        invoices = self._invoices().filtered(lambda m: m.amount_residual > 0)
        if self.state != 'posted':
            raise UserError(_('Post the bill first.'))
        if not invoices:
            raise UserError(_('This bill is already paid.'))
        plot = self.file_id.inventory_id or self.env['plot.inventory'].search(
            [('name', '=', self.unit_number), ('society_id', '=', self.society_id.id)], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receive Payment'),
            'res_model': 'maintenance.charges.payment',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_inventory_id': plot.id,
                'default_file_id': self.file_id.id,
                'default_unit_class_id': plot.unit_class_id.id or self.file_id.unit_class_id.id,
                'default_invoice_ids': [(6, 0, invoices.ids)],
                'default_remarks': _('Monthly bill %s') % self.name,
            },
        }

    def action_print(self):
        return self.env.ref('maintenance_monthly_bill.action_report_maintenance_bill').report_action(self)

    # ------------------------------------------------------------------ report helpers
    def _qr_data_uri(self):
        """QR of the bill number, embedded in the PDF (wkhtmltopdf cannot always fetch
        /report/barcode from the server, e.g. on staging)."""
        self.ensure_one()
        try:
            png = self.env['ir.actions.report'].barcode('QR', self.name or '', width=140, height=140)
        except Exception:  # barcode backend missing: print the bill without the QR
            return False
        return 'data:image/png;base64,%s' % base64.b64encode(png).decode()

    def _bill_lines(self):
        """Rows printed in the bill table: (description, amount)."""
        self.ensure_one()
        # Always the same rows for a bill type, so every printed bill has the same layout.
        lines = []
        if self._has_utility():
            lines.append((_('Utility Charges (%s)', self.maintenance_charges_type_id.name)
                          if self.maintenance_charges_type_id else _('Utility Charges'), self.utility_amount))
        if self._has_electricity():
            lines.append((_('Electricity (%(units)s units @ %(rate)s)', units=int(self.units), rate=self.unit_rate),
                          self.electricity_amount))
        return lines

    def _arrears_lines(self):
        """Arrears rows printed below the charges: (description, amount)."""
        self.ensure_one()
        lines = []
        if self._has_utility():
            lines.append((_('Arrears (Utility)'), self.arrears_utility))
        if self._has_electricity():
            lines.append((_('Arrears (Electricity)'), self.arrears_electricity))
        return lines

    def _bill_title(self):
        self.ensure_one()
        return {'utility': _('Utility Bill'), 'electricity': _('Electricity Bill')}.get(self.bill_type, _('Monthly Bill'))
