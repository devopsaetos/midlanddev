# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import datetime
from dateutil.relativedelta import relativedelta

# Maps installment_type -> product.realestate XML ref, mirrored from
# midland_invoicing/models/file_ext.py's _INSTALLMENT_PRODUCT (real_estate can't import
# that module - it's a dependent, not a dependency - so the mapping is duplicated here).
_MERGER_INSTALLMENT_PRODUCT = {
    'down': 'real_estate.downpayment_product',
    'installment': 'real_estate.installment_product',
    'balloon': 'real_estate.balloon_payment',
    'final': 'real_estate.final_product',
    'possession_amount': 'real_estate.possession_amount_product',
    'balloting_amount': 'real_estate.balloting_product',
    'confirmation_amount': 'real_estate.confirmation_amount_product',
}


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
    # Comodel is overridden to 'midland.invoice' in midland_invoicing/models/plot_merger_application_ext.py.
    # Can't declare that comodel here directly: real_estate is a dependency of midland_invoicing
    # (via file_financials), so declaring a field of comodel 'midland.invoice' in this module would
    # be a circular dependency — midland.invoice wouldn't exist yet when this module's models load.
    merger_fee_invoice_id = fields.Many2one('account.move', string='Merger Fee Invoice', track_visility='always')
    credit_note_id = fields.Many2many('account.move', 'plot_merger_credit_note_account_move_rel', string='Credit Note', track_visility='always')
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

    @api.depends('source_merger_id.amount_received', 'merger_fee')
    def _amount_to_be_adjusted(self):
        for rec in self:
            rec.total_receive_amount = 0.0
            if rec.source_merger_id:
                for data in rec.source_merger_id:
                    rec.total_receive_amount += data.amount_received
            else:
                rec.total_receive_amount = 0.0

    @api.depends('target_merger_id.amount_adjusted')
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

    def _settle_target_installments(self, file_id, amount):
        """Pay off as much of `amount` as possible against the target file's own due
        midland.invoice installments (existing due ones first, then newly generated
        ones for not-yet-invoiced installments), via a genuine midland.payment - the
        same mechanism a normal customer payment uses, so the installment lines
        actually flip to Paid/Partial instead of the money sitting in a credit note.
        Returns whatever amount could not be applied to any installment (the leftover
        that should still become a credit note)."""
        self.ensure_one()
        remaining = amount
        payment_lines = []

        due_invoices = file_id.midland_invoice_ids.filtered(
            lambda inv: inv.state == 'posted' and inv.payment_state != 'paid'
        ).sorted('invoice_date')
        for inv in due_invoices:
            if remaining <= 0:
                break
            pay_amount = min(remaining, inv.amount_residual)
            if pay_amount > 0:
                payment_lines.append((0, 0, {'invoice_id': inv.id, 'payment_amount': pay_amount}))
                remaining -= pay_amount

        if remaining > 0:
            installment_plan = file_id.manual_installment_plan_ids or file_id.installment_plan_ids
            not_posted_invoices = installment_plan.filtered(
                lambda l: l.invoice_created and l.payment_status == 'not_paid' and l.invoice_id.state != 'posted')
            if not_posted_invoices:
                raise ValidationError(_("In %s installment plan, invoice are present which is not posted yet please post them first" % file_id.name))
            invoices_to_create = installment_plan.filtered(
                lambda l: not l.invoice_created and l.installment_type != 'down').sorted('date')
            for installment in invoices_to_create:
                if remaining <= 0:
                    break
                xml_ref = _MERGER_INSTALLMENT_PRODUCT.get(installment.installment_type, 'real_estate.installment_product')
                product = file_id._resolve_product(xml_ref)
                new_invoice = self.env['midland.invoice'].create({
                    'member_id': file_id.membership_id.id,
                    'partner_id': file_id.membership_id.partner_id.id,
                    'invoice_date': installment.date,
                    'property_invoice_type': installment.installment_type or 'installment',
                    'installment_id': installment.id,
                    'file_ids': file_id.id,
                    'currency_id': file_id.currency_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': product.id if product else False,
                        'name': product.name if product else (installment.installment_name or 'Installment'),
                        'account_id': file_id._resolve_income_account(product).id,
                        'quantity': 1.0,
                        'price_unit': installment.amount,
                    })],
                })
                new_invoice.action_post()
                pay_amount = min(remaining, new_invoice.amount_residual)
                if pay_amount > 0:
                    payment_lines.append((0, 0, {'invoice_id': new_invoice.id, 'payment_amount': pay_amount}))
                    remaining -= pay_amount

        if payment_lines:
            payment = self.env['midland.payment'].create({
                'member_id': file_id.membership_id.id,
                'partner_id': file_id.membership_id.partner_id.id,
                'file_id': file_id.id,
                'payment_amount': amount - max(remaining, 0.0),
                'currency_id': file_id.currency_id.id,
                'journal_id': self.env.company.account_journal_id.id,
                'remarks': f"{self.name} - Merger Adjustment",
                'invoice_line_ids': payment_lines,
            })
            payment.action_confirm()

        return max(remaining, 0.0)

    def _create_merger_credit_note(self, member, amount, file_id=False):
        self.ensure_one()
        adjustment_product = self.env.ref('file_financials.product_merger_adjustment').with_company(self.company_id)
        ref = f"{self.name} - {file_id.name}" if file_id else f"{self.name} - Merged Files"
        invoice = self.env['midland.invoice'].create({
            'member_id': member.id,
            'company_id': self.company_id.id,
            'invoice_date': self.merger_date.strftime('%Y-%m-%d') if self.merger_date else fields.Date.today(),
            'file_ids': file_id.id if file_id else False,
            'ref': ref,
            'move_type': 'out_refund',
            'property_invoice_type': 'merger_adjustment',
            'merger_application_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.env.ref('file_financials.product_merger_adjustment_realestate').id,
                'name': 'Adjustment Amount From Source File',
                'quantity': 1,
                'price_unit': amount,
                'account_id': adjustment_product.property_account_income_id.id,
            })],
        })
        invoice.action_post()
        return invoice

    def create_credit_note(self):
        if not self.merger_date:
            raise ValidationError(_('Please set the Merger Date first.'))
        if self.waive_merger_application == 'no' and self.merger_fee_type not in ('net_off', 'separate'):
            raise ValidationError(_('Please select a Merger Fee Type (Net Off or Separate) first.'))
        if (self.waive_merger_application == 'no' and self.merger_fee_type == 'separate'
                and (self.invoice_create == False or self.merger_fee_invoice_id.state == 'draft')):
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
            # Cancel every installment line of the source file (paid or not) - the paid amount is
            # being carried over to the target file, so none of it should still read as active/paid here.
            installment_ids = installment_plan.mapped('id')
            if installment_ids:
                self.env.cr.execute("""UPDATE installment_plan SET payment_status = 'cancel' WHERE id IN %s""", (tuple(installment_ids),))
            line.file_id.state = 'merged'
            line.file_id.file_status = 'merged_and_cancel'
            if line.file_id.inventory_id:
                line.file_id.inventory_id.state = 'avalible_for_sale'
        if self.waive_merger_application == 'no' and self.merger_fee_type == 'net_off':
            if self.merger_fee <= 0:
                raise ValidationError(_(
                    'Merger Fee must be greater than zero to net it off. Please set the '
                    '"Merger Fee" amount on the Source Detail line(s) first.'))
            if not self.company_id.account_journal_id:
                raise ValidationError(_(
                    'Please set the "Journal" field under Real Estate Settings '
                    '(Accounting configuration) for company %s first.') % self.company_id.name)
            advance_account = self.company_id.merger_advance_account_id
            if not advance_account:
                raise ValidationError(_(
                    'Please set the "Merger Advance Account" field under Real Estate Settings '
                    '(Accounting configuration) for company %s first.') % self.company_id.name)
            journal = self.company_id.account_journal_id.id
            move_vals = {
                'journal_id': journal,
                'company_id': self.company_id.id,
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
                        'account_id': self.env.ref('real_estate.file_transfer').with_company(self.company_id).property_account_income_id.id,
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
            move.action_post()
            journal_entry_ids.append(move.id)
        self.journal_entry_id = [(6, 0, journal_entry_ids)]
        self.credit_note_created = True

    def amount_adjust(self):
        if not self.merger_date:
            raise ValidationError(_('Please set the Merger Date first.'))
        if self.waive_merger_application == 'no' and self.merger_fee_type not in ('net_off', 'separate'):
            raise ValidationError(_('Please select a Merger Fee Type (Net Off or Separate) first.'))
        length_of_file = len(self.target_merger_id.file_id)
        credit_note_ids = []
        leftover_total = 0.0
        for line in self.target_merger_id:
            if not line.file_id:
                continue
            if not (line.file_id.manual_installment_plan_ids or line.file_id.installment_plan_ids):
                raise ValidationError(_('File installment plan is not created for %s' % line.file_id.tracking_id))
            if line.amount_adjusted:
                leftover = self._settle_target_installments(line.file_id, line.amount_adjusted)
                if leftover > 0:
                    if self.membership_id and not self.membership_merge_to_id:
                        credit_note_ids.append(
                            self._create_merger_credit_note(self.membership_id, leftover, line.file_id).id)
                    if self.membership_id and self.membership_merge_to_id:
                        credit_note_ids.append(
                            self._create_merger_credit_note(self.membership_merge_to_id, leftover, line.file_id).id)
                line.file_id.merger_ref = self.name
                self.credit_note_id = [(6, 0, credit_note_ids)]
                line.file_id.history_ids.create({
                    'ref_number': self.name,
                    'merged_amount': line.amount_adjusted,
                    'file_id': line.file_id.id,
                })
            else:
                adjusting_amount = (self.net_adjusted / length_of_file)
                leftover_total += self._settle_target_installments(line.file_id, adjusting_amount)
                line.file_id.merger_ref = self.name
                # ***************************************************** Code For Credit Note ***********************************************************************
        if self.total_adjusted_amount <= 0.0 and leftover_total > 0:
            credit_note_ids = []
            lump_sum_file = self.target_merger_id[0].file_id if self.target_merger_id else False
            if self.membership_id and not self.membership_merge_to_id:
                credit_note_ids.append(
                    self._create_merger_credit_note(self.membership_id, leftover_total, lump_sum_file).id)
            if self.membership_id and self.membership_merge_to_id:
                credit_note_ids.append(
                    self._create_merger_credit_note(self.membership_merge_to_id, leftover_total, lump_sum_file).id)
            self.credit_note_id = [(6, 0, credit_note_ids)]
        self.amount_adjust_done = True
        self.show_approved_status = True

    def credit_created_note(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entries',
            'view_mode': 'list,form',
            'target': 'current',
            'res_model': 'midland.invoice',
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
