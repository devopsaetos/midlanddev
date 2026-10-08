# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MaintenanceInquiryWizard(models.TransientModel):
    _name = 'maintenance.inquiry.wizard'
    _description = 'Maintenance Inquiry Wizard'

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('society_id.id','=',society_id)]")
    sector_id = fields.Many2one('sector')
    street_id = fields.Many2one('street', string='Street', domain="[('sector_id', '=', sector_id)]")
    # product_id = fields.Many2one('unit.category.type', 'Product')
    house_id = fields.Many2one('plot.inventory', string='House',
                               domain="[('sector_id', '=', sector_id), ('street_id', '=', street_id)]")
    category_id = fields.Many2one('plot.category', 'Category')
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    size_id = fields.Many2one('unit.size', 'Size')
    unit_class_id = fields.Many2one('unit.class', string="Type")
    file_id = fields.Many2one('file', string='File')
    partner_id = fields.Many2one('res.partner', string='Member')
    maintenance_inquiry_line_ids = fields.One2many('maintenance.inquiry.line', 'maintenance_inquiry_wizard_id',
                                                   string='Maintenance Inquiry Lines')
    # Canal Valley-I/II/III have no streets: hide the Street field there
    has_streets = fields.Boolean(compute='_compute_has_streets')

    @api.depends('society_id', 'sector_id')
    def _compute_has_streets(self):
        Street = self.env['street'].sudo()
        for rec in self:
            if rec.sector_id:
                domain = [('sector_id', '=', rec.sector_id.id)]
            elif rec.society_id:
                domain = [('sector_id.society_id', '=', rec.society_id.id)]
            else:
                domain = []
            rec.has_streets = bool(Street.search_count(domain, limit=1))

    @api.onchange('house_id')
    def onchange_house_id(self):
        for rec in self:
            file = rec.house_id._get_maintenance_file() if rec.house_id else self.env['file']
            if rec.house_id:
                rec.partner_id = file.membership_id.partner_id.id
                rec.category_id = file.category_id.id
                rec.unit_category_type_id = file.unit_category_type_id.id
                # imported files are often not linked to their plot: the size is on the plot
                rec.size_id = (file.size_id or rec.house_id.size_id).id
                rec.unit_class_id = file.unit_class_id.id
                rec.file_id = file.id

    def get_maintenance_inquiry(self):
        for rec in self:
            rec.maintenance_inquiry_line_ids.unlink()
            if rec.house_id and rec.file_id:
                set_date = '2023-11-01'
                # latest bill first, so the current dues are on top
                history = rec.file_id.maintenance_history_ids.filtered(lambda l: str(l.date) >= set_date)
                invoice_ids = history.invoice_id.ids
                bills = {}
                for bill in self.env['maintenance.bill'].sudo().search(
                        ['|', ('utility_invoice_id', 'in', invoice_ids), ('electricity_invoice_id', 'in', invoice_ids)]):
                    bills[bill.utility_invoice_id.id] = bill
                    bills[bill.electricity_invoice_id.id] = bill
                for line in history.sorted(lambda l: (l.date, l.id), reverse=True):
                    self.env['maintenance.inquiry.line'].sudo().create({
                        'date': line.date,
                        'amount': line.amount,
                        'installment_number': line.installment_number,
                        'invoice_created': line.invoice_created,
                        'invoice_id': line.invoice_id.id if line.invoice_id else None,
                        'payment_date': line.payment_date or self._invoice_payment_date(line.invoice_id),
                        'description': self._line_description(line, bills.get(line.invoice_id.id)),
                        'amount_paid': line.amount_paid,
                        'residual': line.residual,
                        'payment_status': line.payment_status,
                        'state': line.state,
                        'maintenance_inquiry_wizard_id': rec.id
                    })
        return {
            'name': _('Maintenance Inquiry'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.model
    def _line_description(self, history, bill):
        """e.g. 'Utility - Nov-2026 - MB/2026/00024'"""
        kind = dict(history._fields['charge_type']._description_selection(self.env)).get(history.charge_type)
        return ' - '.join(filter(None, [kind, history.date and history.date.strftime('%b-%Y'), bill.name if bill else '']))

    @api.model
    def _invoice_payment_date(self, invoice):
        """Date of the latest payment reconciled with the invoice. The history's own
        payment date only knows payments made through multi-invoice payments."""
        if not invoice or invoice.payment_state not in ('paid', 'in_payment', 'partial'):
            return False
        receivable = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))
        counterparts = (receivable.matched_credit_ids.credit_move_id
                        | receivable.matched_debit_ids.debit_move_id) - receivable
        return max(counterparts.mapped('date')) if counterparts else False

    def _report_company(self):
        """Society company of the printed file (its logo goes on the report)."""
        self.ensure_one()
        return (self.maintenance_inquiry_line_ids.invoice_id.company_id[:1]
                or self.society_id.company_id or self.env.company)

    def print_pdf(self):
        for rec in self:
            report = self.env.ref('maintenance_statement_inquiry.action_maintenance_inquiry_report').report_action(rec)
            return report

class MaintenanceInquiryLines(models.TransientModel):
    _name = 'maintenance.inquiry.line'
    _description = 'Maintenance Inquiry Lines'

    maintenance_inquiry_wizard_id = fields.Many2one('maintenance.inquiry.wizard')
    date = fields.Date(string="Date")
    amount = fields.Float(string="Amount")
    installment_number = fields.Integer(string="Sr. No")
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', string="Invoice#")
    description = fields.Char()
    state = fields.Char(string='Invoice Status')
    payment_date = fields.Date('Payment Date')
    amount_paid = fields.Float('Amount Paid')
    residual = fields.Float('Amount Due')
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'), ('cancel', 'Cancelled'),
        # every invoice payment state can come from the history (partly paid bills crashed the Search)
        ('partial', 'Partially Paid'), ('reversed', 'Reversed'), ('blocked', 'Blocked'),
        ('invoicing_legacy', 'Invoicing App Legacy')],
        string='Status')
