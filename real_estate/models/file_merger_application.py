# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import datetime
from dateutil.relativedelta import relativedelta


class PlotMergerApplication(models.Model):
    _name = "plot.merger.application"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'name'
    _description = "Plot Merger Application"

    name = fields.Char("Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    file_merger_request_id = fields.Many2one('file.merger.request', string="File Merger Request", track_visility='always')
    membership_id = fields.Many2one('res.member', string='Member No', track_visility='always')
    membership_merge_to_id = fields.Many2one('res.member', string='Merger Member To', track_visility='always')
    merger_date = fields.Datetime(string='Merger Date', track_visility='always')
    merger_fee = fields.Float(string='Merger Fee', track_visility='always')
    knockoff = fields.Boolean(default=False)
    credit_note_created = fields.Boolean(default=False)
    amount_adjust_done = fields.Boolean(default=False)
    adjust = fields.Boolean(default=False)
    amount_deduction = fields.Float(track_visility='always')
    total_receive_amount = fields.Float(compute='_amount_to_be_adjusted', store=True)
    total_adjusted_amount = fields.Float(compute='_total_adjusted_amount', store=True)
    net_adjusted = fields.Float()

    source_merger_id = fields.One2many('source.merger', "file_merger_application_id")
    target_merger_id = fields.One2many('target.merger', "plot_target_application_id")

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)
    merger_fee_type = fields.Selection(
        string='Merger Fee Type',
        selection=[('net_off', 'Net Off'),
                   ('separate', 'Separate')],
        required=False, track_visility='always')
    waive_merger_application = fields.Selection(
        string='Waive Fee ?',
        selection=[('yes', 'Yes'),
                   ('no', 'No')],
        default="no", required=False, track_visility='always')
    invoice_create = fields.Boolean(string='Invoice Created ?', default=False, track_visility='always')
    merger_fee_invoice_id = fields.Many2one('account.move', string='Account Move', track_visility='always')
    credit_note_id = fields.Many2many('account.move', string='Credit Note', track_visility='always')
    journal_entry_id = fields.Many2one('account.move', string='Journal Entry', track_visility='always')
    show_approved_status = fields.Boolean(string='Show Approved Status', default=False)
    merger_status = fields.Selection([
        ('submit', 'Submit'),
        ('process', 'Process'),
        ('approve', 'Approve'),
    ], default='submit', tracking=True)

    @api.onchange('merger_fee', 'total_receive_amount', 'merger_fee_type')
    def net_adjusted_amount(self):
        for rec in self:
            merger_fee = 0.0
            merger_fee = self.merger_fee
            if rec.merger_fee and rec.merger_fee < rec.total_receive_amount:
                if self.merger_fee_type == 'net_off':
                    rec.net_adjusted = rec.total_receive_amount - merger_fee
                if self.merger_fee_type == 'separate':
                    rec.net_adjusted = rec.total_receive_amount
            else:
                rec.net_adjusted = rec.total_receive_amount

    @api.depends('source_merger_id', 'merger_fee')
    def _amount_to_be_adjusted(self):
        for rec in self:
            rec.total_receive_amount = 0.0
            if rec.source_merger_id:
                for data in rec.source_merger_id:
                    rec.total_receive_amount += data.amount_received
            else:
                rec.total_receive_amount = 0.0

    @api.depends('target_merger_id')
    def _total_adjusted_amount(self):
        for rec in self:
            rec.total_adjusted_amount = 0.0
            if rec.target_merger_id:
                for data in rec.target_merger_id:
                    rec.total_adjusted_amount += data.amount_adjusted
            else:
                rec.total_adjusted_amount = 0.0

    @api.constrains('total_adjusted_amount', 'net_adjusted')
    def _check_amounts(self):
        for record in self:
            if record.total_adjusted_amount > record.net_adjusted:
                raise ValidationError("The adjusted amount in Target lines cannot be greater than the Net Adjustment Amount.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("plot.merger.application") or _('New')

        return super(PlotMergerApplication, self).create(vals_list)

    def create_credit_note(self):
        if self.waive_merger_application == 'no' and self.merger_fee_type == 'separate' and self.invoice_create == False or self.merger_fee_invoice_id.state == 'draft':
            raise ValidationError(_('Please Create And Pay the Merger Invoice First'))
        journal_entry_ids = []
        for line in self.source_merger_id:
            if line.file_id.manual_installment_plan_ids:
                installment_plan = line.file_id.manual_installment_plan_ids
            elif line.file_id.installment_plan_ids:
                installment_plan = line.file_id.installment_plan_ids
            else:
                raise ValidationError(_('File installment plan is not created %s' % line.file_id.tracking_id))
            invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted').mapped('invoice_id')
            if invoices:
                for invoice in invoices:
                    invoice.button_draft()
                    invoice.button_cancel()
                    reversed_entry = self.env['account.move'].sudo().search([('reversed_entry_id', '=', invoice.id)], order='id desc', limit=1)
                    if reversed_entry:
                        reversed_entry.date = self.merger_date
                        reversed_entry.action_post()
                    for line_id in invoice.line_ids.filtered(lambda l: 'Reverse entry' in l.name):
                        line_id.date = self.merger_date
            # self.env.cr.execute(f"""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN {tuple(installment_plan.mapped('id'))}""")
            installment_ids = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted').mapped('id')
            if installment_ids:
                self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(installment_ids),))
            line.file_id.state = 'merged'
            line.file_id.file_status = 'merged_and_cancel'
        if self.waive_merger_application == 'no' and self.merger_fee_type == 'net_off':
            journal = self.env.company.account_journal_id.id,
            advance_account = self.env['account.account'].search([('name', '=', 'Advance from Customers-NCP')], limit=1)
            move_vals = {
                'journal_id': journal,
                'partner_id': self.membership_id.partner_id.id,
                'date': self.merger_date.strftime('%Y-%m-%d'),
                # 'file_ids': line.file_id.id,
                'ref': f"{self.name} - Merged Files",
                'property_invoice_type': 'merger_fee',
                'state': 'draft',
                'line_ids': [
                    (0, 0, {
                        'name': 'Processing Fee',
                        'partner_id': self.membership_id.partner_id.id,
                        'account_id': self.env.ref('real_estate.file_transfer').property_account_income_id.id,
                        'credit': self.merger_fee,
                    }),
                    (0, 0, {
                        'account_id': advance_account.id,
                        'name': 'Advance from Customer',
                        'partner_id': self.membership_id.partner_id.id,
                        'debit': self.merger_fee,
                    }),
                ],
            }
            move = self.env['account.move'].create(move_vals)
            # if move:
            #     move.file_ids = line.file_id.id
            move.post()
            journal_entry_ids.append(move.id)
        self.journal_entry_id = [(6, 0, journal_entry_ids)]
        self.credit_note_created = True

    def amount_adjust(self):
        length_of_file = len(self.target_merger_id.file_id)
        credit_note_ids = []
        for line in self.target_merger_id:
            if line.amount_adjusted:
                remaining_amount = line.amount_adjusted
                if line.file_id:
                    installment_plan = line.file_id.manual_installment_plan_ids or line.file_id.installment_plan_ids
                    if not installment_plan:
                        raise ValidationError(_('File installment plan is not created for %s' % line.file_id.tracking_id))
                    invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted')
                    open_invoices_due_amount = sum(inv.residual for inv in invoices)
                    remaining_amount -= open_invoices_due_amount
                    print(remaining_amount, 'remaining amount')
                    if remaining_amount > 0:
                        invoices_to_create = installment_plan.filtered(lambda l: not l.invoice_created)
                        invoices_to_create_qty = len(invoices_to_create)
                        not_posted_invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state != 'posted')
                        for installment in invoices_to_create:
                            if len(not_posted_invoices) >= 1:
                                raise ValidationError(_("In %s installment plan, invoice are present which is not posted yet please post them first" % line.file_id.name))
                            # Check if Adjusting Amount is more than Installment Invoices Due Amount and Installment Lines still have some Invoices to be genrated
                            if remaining_amount > 0 and invoices_to_create_qty >= 1:
                                date = invoices[-1].date + relativedelta(months=+1) if invoices else (installment_plan.filtered(lambda l: l.payment_status == 'paid')[-1].date +
                                                                                                      relativedelta(months=+1))
                                # tax_ids = line.file_id.installment_tax_ids.ids if line.file_id.installment_tax_ids else self.env.company.installment_tax_ids.ids
                                payment_terms = self.env.company.payment_terms_final_id if installment.installment_type == 'final' else self.env.company.payment_terms_installment_id
                                if installment.installment_type != 'down' and installment.date <= date and not installment.invoice_created:
                                    try:
                                        prod = []
                                        if self.env.company.ownership_percentage and line.file_id.membership_id.company_type == 'aop':
                                            for member in line.file_id.membership_id.cnic_line_ids:
                                                if installment.installment_type == 'final':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.final_product').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.final_product').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100,
                                                        # 'tax_ids': tax_ids,
                                                    }))
                                                elif installment.installment_type == 'installment':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.installment_product').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.installment_product').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100,
                                                        #                                                         'tax_ids': tax_ids,
                                                    }))
                                                elif installment.installment_type == 'balloon':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.balloon_payment').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.balloon_payment').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100
                                                    }))
                                                elif installment.installment_type == 'possession_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                                        'name': self.env.ref('real_estate.possession_amount_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.possession_amount_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                                elif installment.installment_type == 'confirmation_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                                        'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.confirmation_amount_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                                elif installment.installment_type == 'balloting_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.balloting_product').id,
                                                        'name': self.env.ref('real_estate.balloting_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.balloting_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                        else:
                                            if installment.installment_type == 'final':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.final_product').id,
                                                    'name': self.env.ref('real_estate.final_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.final_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                    #                                                     'tax_ids': tax_ids,
                                                })]
                                            elif installment.installment_type == 'installment':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.installment_product').id,
                                                    'name': self.env.ref('real_estate.installment_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.installment_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                    #                                                     'tax_ids': tax_ids,
                                                })]
                                            elif installment.installment_type == 'balloon':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.balloon_payment').id,
                                                    'name': self.env.ref('real_estate.balloon_payment').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.balloon_payment').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                            elif installment.installment_type == 'possession_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                                    'name': self.env.ref('real_estate.possession_amount_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.possession_amount_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                            elif installment.installment_type == 'confirmation_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                                    'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.confirmation_amount_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                            elif installment.installment_type == 'balloting_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.balloting_product').id,
                                                    'name': self.env.ref('real_estate.balloting_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.balloting_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                        new_invoice = self.env['account.move'].create({
                                            'partner_id': line.file_id.membership_id.partner_id.id,
                                            'type': 'out_invoice',
                                            'journal_id': self.env.company.account_journal_id.id,
                                            # 'property_invoice_type': 'installment',
                                            'property_invoice_type': installment.installment_type if installment.installment_type else 'installment',
                                            'user_id': line.file_id.user_id.id,
                                            'date': installment.date,
                                            'invoice_date': installment.date,
                                            'invoice_payment_term_id': payment_terms.id,
                                        })
                                        new_invoice.file_ids = line.file_id.id
                                        new_invoice.invoice_line_ids = prod
                                        new_invoice.action_post()
                                        installment.invoice_id = new_invoice.id
                                        installment.invoice_created = True
                                        remaining_amount -= new_invoice.amount_residual
                                        invoices_to_create_qty -= 1
                                        date += relativedelta(months=+1)
                                    except Exception as e:
                                        raise ValueError('There is some error: %s in auto invoice creation for installment' % e)
                                    invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted')
                if self.membership_id and not self.membership_merge_to_id:
                    print('Membership 1')
                    credit_note_vals = {
                        'partner_id': self.membership_id.partner_id.id,
                        'company_id': self.env.company.id,
                        'invoice_date': self.merger_date,
                        'file_ids': line.file_id.id,
                        'journal_id': self.env.company.account_journal_id.id,
                        'ref': f"{self.name} - {line.file_id.name}",
                        'type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                            'name': 'Adjustment Amount From Source File',
                            'quantity': 1,
                            'price_unit': line.amount_adjusted,
                        })],
                    }
                    credit_note = self.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = line.file_id.id
                    credit_note.action_post()
                    credit_note_ids.append(credit_note.id)
                if self.membership_id and self.membership_merge_to_id:
                    print('Membership 2')
                    credit_note_vals = {
                        'partner_id': self.membership_merge_to_id.partner_id.id,
                        'company_id': self.env.company.id,
                        'invoice_date': self.merger_date,
                        'file_ids': line.file_id.id,
                        'journal_id': self.env.company.account_journal_id.id,
                        'ref': f"{self.name} - {line.file_id.name}",
                        'type': 'out_refund',
                        'invoice_line_ids': [(0, 0, {
                            'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                            'name': 'Adjustment Amount From Source File',
                            'quantity': 1,
                            'price_unit': line.amount_adjusted,
                        })],
                    }
                    credit_note = self.env['account.move'].create(credit_note_vals)
                    credit_note.file_ids = line.file_id.id
                    credit_note.action_post()
                    credit_note_ids.append(credit_note.id)
                line.file_id.merger_ref = self.name
                self.credit_note_id = [(6, 0, credit_note_ids)]
                line.file_id.history_ids.create({
                    'ref_number': self.name,
                    'merged_amount': line.amount_adjusted,
                    'file_id': line.file_id.id,
                })
            else:
                print(length_of_file)
                adjusting_amount = (self.net_adjusted / length_of_file)
                if line.file_id.manual_installment_plan_ids:
                    installment_plan = line.file_id.manual_installment_plan_ids
                elif line.file_id.installment_plan_ids:
                    installment_plan = line.file_id.installment_plan_ids
                else:
                    raise ValidationError(_('File installment plan is not created %s' % line.file_id.tracking_id))
                invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted')
                # Posted Invoices Amount
                open_invoices_due_amount = sum(inv.residual for inv in invoices)
                balance = adjusting_amount - open_invoices_due_amount
                # remaining_amount = 0
                invoices_to_create = installment_plan.filtered(lambda l: l.invoice_created == False)
                invoices_to_create_qty = len(invoices_to_create)
                not_posted_invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state != 'posted')
                if len(not_posted_invoices) >= 1:
                    raise ValidationError(
                        _("In %s installment plan, invoice are present which is not posted yet please post them first" %
                          line.file_id.name))
                # Check if Adjusting Amount is more than Installment Invoices Due Amount and Installment Lines still have some Invoices to be genrated
                if balance > 0 and invoices_to_create_qty >= 1:
                    # date = invoices[-1].date + relativedelta(months=+1)
                    date = invoices[-1].date + relativedelta(months=+1) if invoices else installment_plan.filtered(lambda l: l.payment_status == 'paid')[-1].date + relativedelta(
                        months=+1)
                    tax_ids = line.file_id.installment_tax_ids.ids if line.file_id.installment_tax_ids else self.env.company.installment_tax_ids.ids
                    if installment_plan:
                        for installment in invoices_to_create:
                            if balance > 0 and invoices_to_create_qty >= 1:
                                payment_terms = self.env.company.payment_terms_final_id if installment.installment_type == 'final' else self.env.company.payment_terms_installment_id
                                if installment.installment_type != 'down' and installment.date <= date and not installment.invoice_created:
                                    try:
                                        prod = []
                                        if self.env.company.ownership_percentage and line.file_id.membership_id.company_type == 'aop':
                                            for member in line.file_id.membership_id.cnic_line_ids:
                                                if installment.installment_type == 'final':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.final_product').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.final_product').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100,
                                                        #                                                         'tax_ids': tax_ids,
                                                    }))
                                                elif installment.installment_type == 'installment':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.installment_product').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.installment_product').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100,
                                                        #                                                         'tax_ids': tax_ids,
                                                    }))
                                                elif installment.installment_type == 'balloon':
                                                    prod.append((0, 0, {
                                                        'product_id': self.env.ref('real_estate.balloon_payment').id,
                                                        'name': member.member_name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.balloon_payment').property_account_income_id.id,
                                                        'price_unit': (installment.amount * member.ownership) / 100
                                                    }))
                                                elif installment.installment_type == 'possession_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                                        'name': self.env.ref('real_estate.possession_amount_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.possession_amount_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                                elif installment.installment_type == 'confirmation_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                                        'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.confirmation_amount_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                                elif installment.installment_type == 'balloting_amount':
                                                    prod = [(0, 0, {
                                                        'product_id': self.env.ref('real_estate.balloting_product').id,
                                                        'name': self.env.ref('real_estate.balloting_product').name,
                                                        'account_id': self.env.ref(
                                                            'real_estate.balloting_product').property_account_income_id.id,
                                                        'price_unit': installment.amount
                                                    })]
                                        else:
                                            if installment.installment_type == 'final':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.final_product').id,
                                                    'name': self.env.ref('real_estate.final_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.final_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                    #                                                     'tax_ids': tax_ids,
                                                })]
                                            elif installment.installment_type == 'installment':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.installment_product').id,
                                                    'name': self.env.ref('real_estate.installment_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.installment_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                    #                                                     'tax_ids': tax_ids,
                                                })]
                                            elif installment.installment_type == 'balloon':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.balloon_payment').id,
                                                    'name': self.env.ref('real_estate.balloon_payment').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.balloon_payment').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount,
                                                })]
                                            elif installment.installment_type == 'possession_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.possession_amount_product').id,
                                                    'name': self.env.ref('real_estate.possession_amount_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.possession_amount_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                            elif installment.installment_type == 'confirmation_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.confirmation_amount_product').id,
                                                    'name': self.env.ref('real_estate.confirmation_amount_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.confirmation_amount_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]
                                            elif installment.installment_type == 'balloting_amount':
                                                prod = [(0, 0, {
                                                    'product_id': self.env.ref('real_estate.balloting_product').id,
                                                    'name': self.env.ref('real_estate.balloting_product').name,
                                                    'account_id': self.env.ref(
                                                        'real_estate.balloting_product').property_account_income_id.id,
                                                    'price_unit': installment.amount,
                                                    # 'price_unit': installment.amount
                                                })]

                                        new_invoice = self.env['account.move'].create({
                                            'partner_id': line.file_id.membership_id.partner_id.id,
                                            'type': 'out_invoice',
                                            'journal_id': self.env.company.account_journal_id.id,
                                            # 'property_invoice_type': 'installment',
                                            'property_invoice_type': installment.installment_type if installment.installment_type else 'installment',
                                            'user_id': line.file_id.user_id.id,
                                            'date': installment.date,
                                            'invoice_date': installment.date,
                                            'invoice_payment_term_id': payment_terms.id,
                                        })
                                        new_invoice.file_ids = line.file_id.id
                                        new_invoice.invoice_line_ids = prod
                                        new_invoice.action_post()
                                        installment.invoice_id = new_invoice.id
                                        installment.invoice_created = True
                                        # remaining_amount += new_invoice.amount_residual
                                        balance -= new_invoice.amount_residual
                                        invoices_to_create_qty -= 1
                                        date += relativedelta(months=+1)
                                    except Exception as e:
                                        raise ValueError('There is some error: %s in auto invoice creation for installment' % e)
                invoices = installment_plan.filtered(lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state == 'posted')
                if len(not_posted_invoices) >= 1:
                    raise ValidationError(
                        _("In %s installment plan, invoice are present which is not posted yet please post them first" %
                          line.file_id.name))
                line.file_id.merger_ref = self.name
                # ***************************************************** Code For Credit Note ***********************************************************************
        if self.total_adjusted_amount <= 0.0:
            credit_note_ids = []
            if self.membership_id and not self.membership_merge_to_id and self.waive_merger_application == 'no':
                print('1111')
                if self.waive_merger_application == 'no':
                    if self.merger_fee_type == 'net_off':
                        print('self member net off')
                        credit_note_vals = {
                            'partner_id': self.membership_id.partner_id.id,
                            'company_id': self.env.company.id,
                            'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                            # 'file_ids': line.file_id.id,
                            'journal_id': self.env.company.account_journal_id.id,
                            'ref': f"{self.name} - Merged Files",
                            'type': 'out_refund',
                            'invoice_line_ids': [(0, 0, {
                                'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                                'name': 'Adjustment Amount From Source File',
                                'quantity': 1,
                                'price_unit': self.net_adjusted,
                            })],
                        }
                        credit_note = self.env['account.move'].create(credit_note_vals)
                        credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                        credit_note.action_post()
                        credit_note_ids.append(credit_note.id)
                    if self.merger_fee_type == 'separate':
                        print('self member separate')
                        credit_note_vals = {
                            'partner_id': self.membership_id.partner_id.id,
                            'company_id': self.env.company.id,
                            'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                            'journal_id': self.env.company.account_journal_id.id,
                            # 'file_ids': line.file_id.id,
                            'ref': f"{self.name} - Merged Files",
                            'type': 'out_refund',
                            'invoice_line_ids': [(0, 0, {
                                'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                                # 'account_id': self.membership_id.property_account_receivable_id.id,
                                'name': 'Adjustment Amount From Source File',
                                'quantity': 1,
                                'price_unit': self.total_receive_amount,
                            })],
                        }
                        credit_note = self.env['account.move'].create(credit_note_vals)
                        credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                        credit_note.action_post()
                        credit_note_ids.append(credit_note.id)
            if self.membership_id and self.membership_merge_to_id and self.waive_merger_application == 'no':
                print('22222222222')
                if self.waive_merger_application == 'no':
                    if self.merger_fee_type == 'net_off':
                        credit_note_vals = {
                            'partner_id': self.membership_merge_to_id.partner_id.id,
                            'company_id': self.env.company.id,
                            'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                            'journal_id': self.env.company.account_journal_id.id,
                            'ref': f"{self.name} - Merged Files",
                            'type': 'out_refund',
                            'invoice_line_ids': [(0, 0, {
                                'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                                'name': 'Adjustment Amount From Source File',
                                'quantity': 1,
                                'price_unit': self.net_adjusted,
                            })],
                        }
                        credit_note = self.env['account.move'].create(credit_note_vals)
                        credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                        credit_note.action_post()
                        credit_note_ids.append(credit_note.id)

                    if self.merger_fee_type == 'separate':
                        print('separate')
                        credit_note_vals = {
                            'partner_id': self.membership_merge_to_id.partner_id.id,
                            'company_id': self.env.company.id,
                            'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                            'journal_id': self.env.company.account_journal_id.id,
                            'ref': f"{self.name} - Merged Files",
                            'type': 'out_refund',
                            'invoice_line_ids': [(0, 0, {
                                'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                                # 'account_id': self.membership_id.property_account_receivable_id.id,
                                'name': 'Adjustment Amount From Source File',
                                'quantity': 1,
                                'price_unit': self.total_receive_amount,
                            })],
                        }
                        credit_note = self.env['account.move'].create(credit_note_vals)
                        credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                        credit_note.action_post()
                        credit_note_ids.append(credit_note.id)
            if self.membership_id and not self.membership_merge_to_id and self.waive_merger_application == 'yes':
                credit_note_vals = {
                    'partner_id': self.membership_id.partner_id.id,
                    'company_id': self.env.company.id,
                    'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                    # 'file_ids': line.file_id.id,
                    'journal_id': self.env.company.account_journal_id.id,
                    'ref': f"{self.name} - Merged Files",
                    'type': 'out_refund',
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                        'name': 'Adjustment Amount From Source File',
                        'quantity': 1,
                        'price_unit': self.net_adjusted,
                    })],
                }
                credit_note = self.env['account.move'].create(credit_note_vals)
                credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                credit_note.action_post()
                credit_note_ids.append(credit_note.id)
            if self.membership_id and self.membership_merge_to_id and self.waive_merger_application == 'yes':
                credit_note_vals = {
                    'partner_id': self.membership_merge_to_id.partner_id.id,
                    'company_id': self.env.company.id,
                    'invoice_date': self.merger_date.strftime('%Y-%m-%d'),
                    'journal_id': self.env.company.account_journal_id.id,
                    'ref': f"{self.name} - Merged Files",
                    'type': 'out_refund',
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.env.ref('file_financials.product_merger_adjustment').id,
                        'name': 'Adjustment Amount From Source File',
                        'quantity': 1,
                        'price_unit': self.net_adjusted,
                    })],
                }
                credit_note = self.env['account.move'].create(credit_note_vals)
                credit_note.file_ids = [(6, 0, [line.file_id.id for line in self.target_merger_id])]
                credit_note.action_post()
                credit_note_ids.append(credit_note.id)
            self.credit_note_id = [(6, 0, credit_note_ids)]
        self.amount_adjust_done = True
        self.show_approved_status = True

    def credit_created_note(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entries',
            'view_mode': 'list,form',
            'target': 'current',
            'res_model': 'account.move',
            'domain': [('id', 'in', self.credit_note_id.ids)]
        }

    def journal_entry_created(self):
        if self.journal_entry_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Journal Entry',
                'view_mode': 'list,form',
                'target': 'current',
                'res_model': 'account.move',
                'domain': [('id', 'in', self.journal_entry_id.ids)]
            }


class SourceMerger(models.Model):
    _name = 'source.merger'
    _description = "Source Merger"

    file_id = fields.Many2one('file', required=True, domain="[('state', '!=', 'cancel')]")
    tracking_id = fields.Char(related='file_id.tracking_id')
    category_id = fields.Many2one('plot.category', string='Category', related='file_id.category_id')
    size_id = fields.Many2one('unit.size', 'Size', related='file_id.size_id')
    inventory_id = fields.Many2one('plot.inventory', 'Plot No', related='file_id.inventory_id')
    ttl_invoiced_amount = fields.Float(compute="_compute_file_detail", store=True, string='Invoiced Amount')
    amount_received = fields.Float('Received', compute="_compute_file_detail", store=True)
    amount_remaining = fields.Float('Remaining', compute="_compute_file_detail", store=True)
    file_merger_application_id = fields.Many2one('plot.merger.application', ondelete='cascade')

    @api.depends('file_id')
    def _compute_file_detail(self):
        for line in self:
            if line.file_id:
                # assignment of active installment plan line
                if line.file_id.manual_installment_plan_ids:
                    installment_plan = line.file_id.manual_installment_plan_ids
                elif line.file_id.installment_plan_ids:
                    installment_plan = line.file_id.installment_plan_ids
                else:
                    raise ValidationError(_('File installment plan is not created %s' % line.file_id.tracking_id))
                invoices = installment_plan.filtered(lambda l: l.invoice_created)
                line.ttl_invoiced_amount = sum(inv.amount for inv in invoices)
                line.amount_received = sum(inv.amount_paid for inv in invoices)
                line.amount_remaining = sum(inv.residual for inv in invoices)
            else:
                self.ttl_invoiced_amount = 0.0
                self.amount_received = 0.0
                self.amount_remaining = 0.0

    # @api.onchange('file_id', 'file_merger_application.membership_id', 'file_merger_application_id.membership_merge_to_id')
    # def _check_domain(self):
    #     domain = [('file_status', 'not in', ['cancel', 'merged_and_cancel'])]
    #     if self.file_merger_application_id.membership_id and not self.file_merger_application_id.membership_merge_to_id:
    #         domain = [
    #             ('membership_id', '=', self.file_merger_application_id.membership_id.id),
    #             ('id', 'not in', [rec.id for rec in self.file_merger_application_id.source_merger_id.mapped('file_id')]),
    #             ('id', 'not in', [rec.id for rec in self.file_merger_application_id.target_merger_id.mapped('file_id')]),
    #         ]
    #     elif self.file_merger_application_id.membership_id and self.file_merger_application_id.membership_merge_to_id:
    #         domain = [
    #             '|',
    #             ('membership_id', '=', self.file_merger_application_id.membership_id.id),
    #             ('membership_id', '=', self.file_merger_application_id.membership_merge_to_id.id),
    #             ('id', 'not in', [rec.id for rec in self.file_merger_application_id.source_merger_id.mapped('file_id')]),
    #             ('id', 'not in', [rec.id for rec in self.file_merger_application_id.target_merger_id.mapped('file_id')]),
    #         ]
    #     return {'domain': {'file_id': domain}}

    @api.onchange('file_id', 'file_merger_application.membership_id', 'file_merger_application_id.membership_merge_to_id')
    def _check_domain(self):
        # Always exclude files with statuses 'cancel' and 'merged_and_cancel'
        domain = [('file_status', 'not in', ['cancel', 'merged_and_cancel'])]

        if self.file_merger_application_id.membership_id and not self.file_merger_application_id.membership_merge_to_id:
            domain += [
                ('membership_id', '=', self.file_merger_application_id.membership_id.id),
                ('id', 'not in', [rec.id for rec in self.file_merger_application_id.source_merger_id.mapped('file_id')]),
                ('id', 'not in', [rec.id for rec in self.file_merger_application_id.target_merger_id.mapped('file_id')]),
            ]
        elif self.file_merger_application_id.membership_id and self.file_merger_application_id.membership_merge_to_id:
            domain += [
                '|',
                ('membership_id', '=', self.file_merger_application_id.membership_id.id),
                ('membership_id', '=', self.file_merger_application_id.membership_merge_to_id.id),
                ('id', 'not in', [rec.id for rec in self.file_merger_application_id.source_merger_id.mapped('file_id')]),
                ('id', 'not in', [rec.id for rec in self.file_merger_application_id.target_merger_id.mapped('file_id')]),
            ]

        return {'domain': {'file_id': domain}}


class TargetMerger(models.Model):
    _name = 'target.merger'
    _description = "Target Merger"

    file_id = fields.Many2one('file', required=True)
    tracking_id = fields.Char(related='file_id.tracking_id')
    ajustment_priority = fields.Selection([
        ('installment', 'INSTALLMENT'),
        ('balloting', 'BALLOTING'),
        ('preference', 'PREFERENCE'),
        ('file', 'FILE')
    ], required=False)
    category_id = fields.Many2one('plot.category', string='Category', related='file_id.category_id')
    size_id = fields.Many2one('unit.size', 'Size', related='file_id.size_id')
    inventory_id = fields.Many2one('plot.inventory', 'Plot No.', related='file_id.inventory_id')
    ttl_invoiced_amount = fields.Float(compute="_compute_file_detail")
    amount_received = fields.Float('Received', compute="_compute_file_detail")
    amount_remaining = fields.Float('Remaining', compute="_compute_file_detail")
    # value = fields.Float("Value")
    plot_target_application_id = fields.Many2one('plot.merger.application', ondelete='cascade')
    amount_adjusted = fields.Float(string='Adjustment Amount')

    @api.depends('file_id')
    def _compute_file_detail(self):
        for line in self:
            if line.file_id:
                # assignment of active installment plan line
                if line.file_id.manual_installment_plan_ids:
                    installment_plan = line.file_id.manual_installment_plan_ids
                elif line.file_id.installment_plan_ids:
                    installment_plan = line.file_id.installment_plan_ids
                else:
                    raise ValidationError(_('File installment plan is not created %s' % line.file_id.tracking_id))
                invoices = installment_plan.filtered(lambda l: l.invoice_created)
                line.ttl_invoiced_amount = sum(inv.amount for inv in invoices)
                line.amount_received = sum(inv.amount_paid for inv in invoices)
                line.amount_remaining = sum(inv.residual for inv in invoices)
            else:
                self.ttl_invoiced_amount = 0.0
                self.amount_received = 0.0
                self.amount_remaining = 0.0

    @api.onchange('file_id', 'plot_target_application_id.membership_id', 'plot_target_application_id.membership_merge_to_id')
    def _check_domain(self):
        domain = [('file_status', 'not in', ['cancel', 'merged_and_cancel'])]
        if self.plot_target_application_id.membership_id and not self.plot_target_application_id.membership_merge_to_id:
            domain += [
                ('membership_id', '=', self.plot_target_application_id.membership_id.id),
                ('id', 'not in', [rec.id for rec in self.plot_target_application_id.source_merger_id.mapped('file_id')]),
                ('id', 'not in', [rec.id for rec in self.plot_target_application_id.target_merger_id.mapped('file_id')]),
            ]
        elif self.plot_target_application_id.membership_id and self.plot_target_application_id.membership_merge_to_id:
            domain += [
                '|',
                ('membership_id', '=', self.plot_target_application_id.membership_id.id),
                ('membership_id', '=', self.plot_target_application_id.membership_merge_to_id.id),
                ('id', 'not in', [rec.id for rec in self.plot_target_application_id.source_merger_id.mapped('file_id')]),
                ('id', 'not in', [rec.id for rec in self.plot_target_application_id.target_merger_id.mapped('file_id')]),
            ]
        return {'domain': {'file_id': domain}}

    # @api.constrains('amount_adjusted', 'amount_remaining')
    # def _check_amounts(self):
    #     for record in self:
    #         if record.amount_adjusted > record.amount_remaining:
    #             raise ValidationError("The adjusted amount cannot be greater than the remaining amount.")
