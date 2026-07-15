from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PlotMergerApplicationExt(models.Model):
    _inherit = 'plot.merger.application'

    waive_merger_application = fields.Selection(
        string='Waive Fee ?',
        selection=[('yes', 'Yes'),
                   ('no', 'No')],
        default="no", required=False, track_visility='always')
    merger_date = fields.Datetime(string='Merger Date', track_visility='always')
    merger_fee = fields.Float(string='Merger Fee', compute='_compute_merger_fee', store=True)
    invoice_create = fields.Boolean(string='Invoice Created ?', default=False, track_visility='always')
    appointment_date = fields.Date(string='Application Date')
    membership_merge_to_id = fields.Many2one('res.member', string='Merger Member To')
    merger_request = fields.Boolean(string='Merger Request', default=False)
    merger_fee_type = fields.Selection(
        string='Merger Fee Type',
        selection=[('net_off', 'Net Off'),
                   ('separate', 'Separate')],
        required=False, )
    total_adjusted_amount = fields.Float(compute='_total_adjusted_amount', store=True)

    # credit_note_id comodel is overridden to 'midland.invoice' in
    # midland_invoicing/models/plot_merger_application_ext.py (see file_merger_application.py
    # in real_estate for why it can't be declared with that comodel here).
    journal_entry_id = fields.Many2many('account.move', 'journal_entry_move_rel', 'journal_entry_id', 'move_id', string='Journal Entry')
    notes = fields.Text(string='Internal Notes')
    manual_adjusted = fields.Boolean(string='Manually Adjusted', default=False)
    length_of_files = fields.Float(string='Length of Files', compute='_compute_length_of_files', store=True)
    show_approved_status = fields.Boolean(string='Show Approved Status', default=False)
    approve_status = fields.Boolean(string='Approve Status', default=False)

    def action_approved(self):
        self.approve_status = True
        for rec in self:
            rec.merger_status = 'approve'

    @api.depends('target_merger_id.amount_adjusted')
    def _total_adjusted_amount(self):
        for rec in self:
            rec.total_adjusted_amount = 0.0
            if rec.target_merger_id:
                for data in rec.target_merger_id:
                    rec.total_adjusted_amount += data.amount_adjusted
            else:
                rec.total_adjusted_amount = 0.0

    @api.depends('target_merger_id')
    def _compute_length_of_files(self):
        for rec in self:
            length_of_file = len(rec.target_merger_id.file_id)
            rec.length_of_files = length_of_file

    @api.depends('source_merger_id.file_merger_fee')
    def _compute_merger_fee(self):
        for rec in self:
            rec.merger_fee = 0.0
            if rec.source_merger_id:
                for data in rec.source_merger_id:
                    rec.merger_fee += data.file_merger_fee
            else:
                rec.merger_fee = 0.0

    @api.constrains('total_adjusted_amount', 'net_adjusted')
    def _check_amounts(self):
        for record in self:
            if record.total_adjusted_amount > record.net_adjusted:
                raise ValidationError("The adjusted amount in Target lines cannot be greater than the Net Adjustment Amount.")

    def create_merger_fee_invoice(self):
        if self.waive_merger_application == 'yes':
            raise ValidationError('You Cannot Create Invoice if Waive Is Yes')
        else:
            merger_fee_product = self.env.ref('real_estate.file_transfer').with_company(self.company_id)
            if not merger_fee_product:
                raise ValidationError('Product "Merger Fee" not found.')
            merger_invoice = self.env['midland.invoice'].sudo().create({
                'move_type': 'out_invoice',
                'property_invoice_type': 'merger_fee',
                'company_id': self.company_id.id,
                'member_id': self.membership_id.id,
                'merger_application_id': self.id,
                'file_ids': self.target_merger_id[0].file_id.id if self.target_merger_id else False,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': merger_fee_product.id,
                        'name': merger_fee_product.name,
                        'account_id': merger_fee_product.property_account_income_id.id,
                        'price_unit': self.merger_fee
                    })
                ]
            })
            merger_invoice.action_post()
            if merger_invoice:
                self.merger_fee_invoice_id = merger_invoice.id
                self.invoice_create = True
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Merger Fee Invoice',
                    'view_mode': 'form',
                    'target': 'current',
                    'res_model': 'midland.invoice',
                    'res_id': self.merger_fee_invoice_id.id,
                    'domain': [('id', '=', self.merger_fee_invoice_id.id)]
                }

    def action_invoice(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Merger Fee Invoice',
            'view_mode': 'form',
            'target': 'current',
            'res_model': 'midland.invoice',
            'res_id': self.merger_fee_invoice_id.id,
            'domain': [('id', '=', self.merger_fee_invoice_id.id)]
        }

    def button_view_credit_notes(self):
        if self.credit_note_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Credit Note',
                'view_mode': 'list,form',
                'target': 'current',
                'res_model': 'midland.invoice',
                'domain': [('id', 'in', self.credit_note_id.ids)]
            }

    def journal_entry_created(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'view_mode': 'list,form',
            'target': 'current',
            'res_model': 'account.move',
            'domain': [('id', 'in', self.journal_entry_id.ids)]
        }

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


class SourceMergerExt(models.Model):
    _inherit = 'source.merger'

    type = fields.Selection(
        string='Type',
        selection=[('refund', 'Refund'),
                   ('merge', 'Merge'), ('rebate', 'Rebate')],
        required=False, default='merge')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product', related='file_id.unit_category_type_id')
    select_file = fields.Boolean(string='Select')

    total_sale_amount = fields.Float(string='Sale Amount', related='file_id.ttl_sale_amount')

    file_merger_fee = fields.Float(string='Merger Fee')
    balance_amount = fields.Float(string='Balance Amount', compute='_compute_balance_amount')

    @api.depends('amount_received', 'file_merger_fee')
    def _compute_balance_amount(self):
        for rec in self:
            rec.balance_amount = rec.amount_received - rec.file_merger_fee

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
                # invoices = installment_plan.filtered(lambda l: l.invoice_created)
                invoices = installment_plan.filtered(lambda l: l.payment_status == 'paid')
                total_invoices = installment_plan.filtered(lambda l: l.payment_status == 'paid' or l.invoice_created)
                total_remaining = installment_plan.filtered(lambda l: l.payment_status == 'not_paid')

                line.ttl_invoiced_amount = sum(inv.amount for inv in total_invoices)
                line.amount_received = sum(inv.amount_paid for inv in invoices)
                line.amount_remaining = sum(inv.residual for inv in total_remaining)
            else:
                self.ttl_invoiced_amount = 0.0
                self.amount_received = 0.0
                self.amount_remaining = 0.0

    @api.onchange('file_id', 'file_merger_application.membership_id', 'file_merger_application_id.membership_merge_to_id')
    def _check_domain(self):
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


# Code For Credit Note
class TargetMergerExt(models.Model):
    _inherit = 'target.merger'

    unit_category_type_id = fields.Many2one('unit.category.type', string='Product',
                                            related='file_id.unit_category_type_id')
    select_file = fields.Boolean(string='Select')
    total_sale_amount = fields.Float(string='Sale Amount', related='file_id.ttl_sale_amount', store=True)
    amount_adjusted = fields.Float(string='Adjustment Amount', compute='_compute_amount_adjusted', inverse='_inverse_amount_adjusted', store=True)

    @api.depends('file_id', 'plot_target_application_id.target_merger_id', 'plot_target_application_id.net_adjusted', 'plot_target_application_id.manual_adjusted')
    def _compute_amount_adjusted(self):
        for record in self:
            if not record.plot_target_application_id.manual_adjusted:
                if record.file_id:
                    record.amount_adjusted = record.plot_target_application_id.net_adjusted / record.plot_target_application_id.length_of_files

    def _inverse_amount_adjusted(self):
        for record in self:
            if record.plot_target_application_id.manual_adjusted:
                pass

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
                # invoices = installment_plan.filtered(lambda l: l.invoice_created)
                # line.ttl_invoiced_amount = sum(inv.amount for inv in invoices)
                # line.amount_received = sum(inv.amount_paid for inv in invoices)
                # line.amount_remaining = sum(inv.residual for inv in invoices)
                invoices = installment_plan.filtered(lambda l: l.payment_status == 'paid')
                total_invoices = installment_plan.filtered(lambda l: l.payment_status == 'paid' or l.invoice_created)
                total_remaining = installment_plan.filtered(lambda l: l.payment_status == 'not_paid')
                line.ttl_invoiced_amount = sum(inv.amount for inv in total_invoices)
                line.amount_received = sum(inv.amount_paid for inv in invoices)
                line.amount_remaining = sum(inv.residual for inv in total_remaining)
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
