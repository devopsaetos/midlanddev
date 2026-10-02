# -*- coding: utf-8 -*-

import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


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

    utility_invoice_id = fields.Many2one('account.move', readonly=True, copy=False)
    electricity_invoice_id = fields.Many2one('account.move', readonly=True, copy=False)

    @api.depends('previous_reading', 'current_reading', 'unit_rate', 'utility_amount',
                 'arrears_utility', 'arrears_electricity', 'surcharge_percent')
    def _compute_amounts(self):
        for rec in self:
            rec.units = max(rec.current_reading - rec.previous_reading, 0.0) if rec.current_reading else 0.0
            rec.electricity_amount = round(rec.units * rec.unit_rate)
            rec.arrears = rec.arrears_utility + rec.arrears_electricity
            rec.current_amount = rec.utility_amount + rec.electricity_amount
            rec.due_amount = rec.current_amount + rec.arrears
            rec.surcharge = round(rec.due_amount * rec.surcharge_percent / 100.0)
            rec.payable_after_due = rec.due_amount + rec.surcharge

    @api.constrains('previous_reading', 'current_reading')
    def _check_readings(self):
        for rec in self:
            if rec.current_reading and rec.current_reading < rec.previous_reading:
                raise ValidationError(_('%(unit)s: current reading (%(cur)s) is lower than previous reading (%(prev)s).',
                                        unit=rec.unit_number, cur=rec.current_reading, prev=rec.previous_reading))

    @api.constrains('file_id', 'bill_month', 'state')
    def _check_one_bill_per_month(self):
        for rec in self.filtered(lambda r: r.state != 'cancel'):
            dup = self.search_count([('id', '!=', rec.id), ('file_id', '=', rec.file_id.id),
                                     ('bill_month', '=', rec.bill_month), ('state', '!=', 'cancel')])
            if dup:
                raise ValidationError(_('%(unit)s already has a bill for %(month)s.',
                                        unit=rec.unit_number, month=rec.bill_month.strftime('%b %Y')))

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
        """Outstanding amount before this bill's month for one charge type.

        Imported Excel history stores a running balance (each row already includes the
        arrears before it), so only the latest imported row's residual counts. Rows that
        come from real invoices count with the invoice's live residual."""
        self.ensure_one()
        history = self.file_id.maintenance_history_ids.filtered(
            lambda h: h.charge_type == charge_type and h.date and h.date < self.bill_month)
        imported = history.filtered(lambda h: not h.invoice_id).sorted(lambda h: (h.date, h.id))
        opening = imported[-1].residual if imported else 0.0
        invoices = history.mapped('invoice_id').filtered(lambda m: m.state == 'posted')
        return opening + sum(invoices.mapped('amount_residual'))

    def action_recompute_arrears(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Arrears can only be recomputed on draft bills.'))
            rec.write({
                'arrears_utility': rec._arrears_for('utility'),
                'arrears_electricity': rec._arrears_for('electricity'),
            })

    # ------------------------------------------------------------------ posting
    def _make_invoice(self, product, invoice_type, line_name, quantity, price_unit):
        self.ensure_one()
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'journal_id': self.journal_id.id,
            'invoice_date': self.bill_month,
            'invoice_date_due': self.due_date,
            'property_invoice_type': invoice_type,
            'ref': self.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': line_name,
                'quantity': quantity,
                'price_unit': price_unit,
                'tax_ids': [(6, 0, [])],
            })],
        })
        # Set after create, like the maintenance cron: real_estate's account.move.create()
        # strips file_ids from the values and logs a file payment-history row instead.
        move.file_ids = self.file_id
        move.action_post()
        return move

    def _add_history(self, invoice, charge_type):
        last = self.file_id.maintenance_history_ids.sorted(lambda h: h.installment_number)[-1:]
        self.env['maintenance.charges.history'].create({
            'file_id': self.file_id.id,
            'date': self.bill_month,
            'charge_type': charge_type,
            'installment_number': (last.installment_number or 0) + 1,
            'amount': invoice.amount_total,
            'invoice_created': True,
            'invoice_id': invoice.id,
        })

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.partner_id:
                raise UserError(_('%s: the file has no member / accounting partner.') % rec.unit_number)
            month = rec.bill_month.strftime('%b %Y')
            vals = {'state': 'posted'}
            if rec.utility_amount > 0:
                if not rec.utility_product_id:
                    raise UserError(_('%s: set the Utility product first.') % rec.name)
                inv = rec._make_invoice(rec.utility_product_id, 'maintenance_charges',
                                       _('Utility / Maintenance Charges %s') % month, 1, rec.utility_amount)
                rec._add_history(inv, 'utility')
                vals['utility_invoice_id'] = inv.id
            if rec.electricity_amount > 0:
                if not rec.electricity_product_id:
                    raise UserError(_('%s: set the Electricity product first.') % rec.name)
                inv = rec._make_invoice(
                    rec.electricity_product_id, 'society_charges',
                    _('Electricity %(month)s: %(units)s units (%(prev)s to %(cur)s) @ %(rate)s',
                      month=month, units=int(rec.units), prev=int(rec.previous_reading),
                      cur=int(rec.current_reading), rate=rec.unit_rate),
                    rec.units, rec.unit_rate)
                rec._add_history(inv, 'electricity')
                vals['electricity_invoice_id'] = inv.id
            rec.write(vals)
        return True

    def action_cancel(self):
        if self.filtered(lambda r: r.state == 'posted'):
            raise UserError(_('Posted bills cannot be cancelled here: cancel or reverse their invoices in Accounting first.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})

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
        # Always the same rows, so every printed bill has the same layout.
        return [
            (_('Utility Charges'), self.utility_amount),
            (_('Electricity (%(units)s units @ %(rate)s)', units=int(self.units), rate=self.unit_rate),
             self.electricity_amount),
        ]
