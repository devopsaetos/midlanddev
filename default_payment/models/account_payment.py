# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import qrcode
import base64
from io import BytesIO
import secrets
from hashids import Hashids
from odoo import tools


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Was previously named _compute_name, which collides with account.payment's own
    # _compute_name (name = fields.Char(string="Number", compute='_compute_name', ...) on the
    # base model) — silently replacing the real payment-numbering logic system-wide, leaving
    # every posted payment's "Number" blank. Renamed; this is only ever a domain helper.
    @tools.ormcache('self.env.context.get("default_partner_type")', 'self.env.company.id')
    def _get_partner_id_domain(self):
        domain = False
        default_partner_type = self.env.context.get('default_partner_type')
        if default_partner_type == 'supplier':
            domain = [('supplier_rank', '>', 0)]
        elif default_partner_type == 'customer':
            domain = [('customer_rank', '>', 0)]
        if domain:
            return domain + ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]
        return []

    partner_id = fields.Many2one('res.partner', string='Partner', tracking=True,
                                 domain=lambda l: l._get_partner_id_domain())

    # invoice_ids already exists on account.payment in Odoo 19 with relation='account_move__account_payment'
    # We override it here to keep readonly=False and add our domain, keeping the same relation table
    invoice_ids = fields.Many2many(
        'account.move',
        'account_move__account_payment',
        'payment_id',
        'invoice_id',
        string="Invoice", copy=False, readonly=False,
        domain="[('partner_id','=', partner_id)]",
        help="""Technical field containing the invoice for which the payment has been generated.
                This does not especially correspond to the invoices reconciled with the payment,
                as it can have been generated first, and reconciled later""")

    multi_invoice_ids = fields.Many2many('multi.invoice.payment', string="Invoices", copy=False, readonly=False, help="""Technical field containing the invoices
    for which the payment has been generated.
                                               This does not especially correspond to the invoices reconciled with the payment,
                                               as it can have been generated first, and reconciled later""")

    payment_category = fields.Selection([
        ('multi_inv_payment', 'Mutli Invoice Payment'),
        ('inv_payment', 'Direct Invoice Payment'),
        ('advance_payment', 'Advance Payment')
    ], default='inv_payment')

    cheque_name = fields.Char('Cheque Name')
    cheque_no = fields.Char('Cheque No.')
    bank_ref = fields.Char('Bank Reference')
    mode_of_payments = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('payorder', 'Pay Order'),
        ('online', 'Online'),
    ], default="cash")
    cheque_status = fields.Selection([('waiting_for_clearance', "Waiting for Clearance"),
                                      ('cleared', "Cleared")])
    legacy_ref = fields.Char()
    base_payment_id = fields.Many2one('account.payment')

    # Advance Payment
    is_advance_payment = fields.Boolean('Advance Payment?', compute='_compute_is_advance', store=True)
    advance_payment_account_id = fields.Many2one('account.account', 'Advance Payment Account')
    amount_residual = fields.Monetary(
        string='Remaining Amount',
        compute='_compute_residual',
        readonly=True,
        store=True,
        help="Remaining amount to apply.")

    amount_to_adjust = fields.Float("Amount to adjust")
    projected_residual = fields.Monetary(
        string='Remaining After Adjustment',
        compute='_compute_projected_residual',
        currency_field='currency_id')
    discount_amount = fields.Monetary("Discount Amount")
    inv_line_add = fields.Boolean()
    qr_code = fields.Binary("QR Code", compute='generate_qr_code', attachment=True, store=True)
    internal_notes = fields.Text('Internal Notes')

    qr_hashid = fields.Char(string="Hash", readonly=True, copy=False)
    hash_salt = fields.Char(string="salt", readonly=True, copy=False)

    @api.depends('name')
    def generate_qr_code(self):
        for rec in self:
            params = ""
            hashed_id = ""
            salt = ""
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            base_url = self.env["ir.config_parameter"].get_param("web.base.url")

            if isinstance(rec.id, int):  # Skip if not a saved record
                salt = secrets.token_urlsafe(16)
                hashids = Hashids(salt=salt, min_length=15)

                hashed_id = hashids.encode(rec.id)
                params = f'/payment/verification/{hashed_id}'

            url = base_url + params
            data = rec.id
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.update({
                'qr_hashid': hashed_id,
                'hash_salt': salt,
                'qr_code': qr_image,
            })

    @api.model
    def generate_qr_code_for_all(self):
        payments = self.env['account.payment'].search([('qr_code', '=', False)], order="id desc", limit=500)
        for rec in payments:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )

            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            params = '/payment/verification/%s' % (rec.id)
            url = base_url + params
            data = rec.id
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image

    def action_draft(self):
        cancel_move = super(AccountPayment, self).action_draft()
        for rec in self.search([('base_payment_id', '=', self.id)]):
            moves = rec.mapped('move_id.line_ids.move_id')
            moves.filtered(lambda move: move.state == 'posted').button_draft()
            moves.with_context(force_delete=True).unlink()
            rec.write({'state': 'draft', 'invoice_ids': False})
        return cancel_move

    def clear_check(self):
        for rec in self:
            rec.cheque_status = 'cleared'
            return self

    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id', 'advance_payment_account_id')
    def _compute_destination_account_id(self):
        super(AccountPayment, self)._compute_destination_account_id()
        for rec in self:
            if (not rec.invoice_ids and rec.payment_category == 'advance_payment' and rec.payment_type != 'transfer'
                    and rec.is_advance_payment and rec.advance_payment_account_id):
                rec.destination_account_id = rec.advance_payment_account_id.id

    # Base account.payment only sets outstanding_account_id from the payment method line's own
    # payment_account_id (normally blank in a full Accounting install, which relies on the
    # account.payment.register wizard instead). Every payment in this codebase is created
    # directly via account.payment.create() (never through that wizard), so without this
    # fallback _generate_journal_entry()'s `p.outstanding_account_id` check never passes and
    # payments never get a journal entry at all (move_id stays empty, amount_residual on the
    # linked invoice/bill never moves even though it shows as "in payment"). Applies to every
    # payment category, not just advance payments — this was the same bug wearing different
    # symptoms (Apply Advance Payments not working, and separately, Vendor Bills/Customer
    # Invoices staying "in payment" with their full amount still due after being paid).
    # Uses the journal's own default account for the bank/liquidity side — this is always
    # configured on any working bank/cash journal, unlike company.transfer_account_id or a
    # chart-template outstanding account (_get_outstanding_account), which are unset on most
    # companies in this database. destination_account_id (above) already provides the
    # advance-holding side for advance payments specifically, so the two must stay different
    # accounts in that case; for regular payments destination_account_id is the partner's own
    # receivable/payable account, which is likewise always distinct from the journal's account.
    @api.depends('payment_category', 'advance_payment_account_id', 'journal_id')
    def _compute_outstanding_account_id(self):
        super(AccountPayment, self)._compute_outstanding_account_id()
        for rec in self:
            if not rec.outstanding_account_id and rec.journal_id.default_account_id:
                rec.outstanding_account_id = rec.journal_id.default_account_id

    @api.depends('amount', 'invoice_ids', 'move_id.line_ids.amount_residual')
    def _compute_residual(self):
        # Uses account.move.line's own amount_residual (Odoo core), which nets out
        # reconciliation against ALL matched counterpart lines regardless of which move
        # they live on. The Apply Advance Payment wizard books its adjustment entry on a
        # separate account.move (reconciled against this payment's advance-account line),
        # so summing only payment.move_id's own debit/credit (as before) ignored those
        # adjustments entirely and kept showing the full original amount as available.
        for payment in self:
            total = 0.0
            if payment.is_advance_payment:
                payment_type = payment.payment_type
                payment_account = payment.advance_payment_account_id
                move_lines = payment.move_id.line_ids.filtered(lambda l: l.account_id == payment_account)
                if payment_type == 'outbound':
                    total = sum(move_lines.filtered(lambda l: l.debit).mapped('amount_residual'))
                elif payment_type == 'inbound':
                    total = -sum(move_lines.filtered(lambda l: l.credit).mapped('amount_residual'))
                else:
                    raise ValidationError(_('Advance payment did not allow Internal Transfer.'))
            payment.amount_residual = total

    @api.depends('amount_residual', 'amount_to_adjust')
    def _compute_projected_residual(self):
        # Live preview only (not stored): what amount_residual would become after the
        # currently-staged amount_to_adjust (set in the Apply Advance Payment wizard) is
        # actually applied. Kept separate from amount_residual so existing validations that
        # compare amount_to_adjust against the true amount_residual are unaffected.
        for payment in self:
            payment.projected_residual = payment.amount_residual - payment.amount_to_adjust

    @api.onchange('journal_id', 'payment_type')
    def _onchange_journal_payment_type(self):
        company = self.journal_id.company_id
        self.company_id = company.id
        if self.payment_type == 'inbound':
            self.advance_payment_account_id = company.advance_payment_account_id.id
        else:
            self.advance_payment_account_id = company.advance_payment_outgoing_account_id.id

    @api.depends('payment_category')
    def _compute_is_advance(self):
        for rec in self:
            rec.is_advance_payment = True if rec.payment_category == 'advance_payment' else False

    # --------------------------------------------------------------------End Advance Functions

    def create_related_inv_logs(self):
        multi_inv_log = self.env['multi.invoice.payment'].search([('payment_id', '=', False), ('active', '=', True)])

        for payment in self:
            invoices = self.env['account.move'].search([
                ('partner_id', '=', payment.partner_id.id),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
                ('move_type', 'in',
                 ['out_invoice'] if self.payment_type == 'inbound' else ['in_invoice'])
            ])
            if invoices:
                for inv in invoices:
                    if not multi_inv_log or inv.id not in multi_inv_log.mapped('invoice_id').ids:
                        if inv.id not in self.search([('state', '=', 'draft')]).multi_invoice_ids.mapped(
                                'invoice_id').ids:
                            multi_inv_log.create({
                                'invoice_id': inv.id,
                                'payment_due': inv.amount_residual,
                                'payment_amount': inv.amount_residual
                            })
        return True

    def check_partner(self):
        if not self.partner_id and self.env.context.get('default_partner_id', False):
            self.partner_id = self.env.context.get('default_partner_id')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            record.check_partner()
            domain = {'domain': {}}
            constraints = [('id', '=', False)]
            if record._context.get('active_model', False) != 'account.move':
                record.multi_invoice_ids = False
                if record.partner_id:
                    move_ids = record.multi_line_domain()
                    if not move_ids and record.create_related_inv_logs():
                        move_ids = record.multi_invoice_ids.search([
                            ('partner_id', '=', record.partner_id.id),
                            ('state', '=', 'posted'),
                            ('active', '=', True),
                            ('payment_id', '=', False),
                            ('invoice_payment_state', '!=', 'paid'),
                            ('type', 'in', ['out_invoice'] if record.payment_type == 'inbound' else ['in_invoice'])
                        ]).ids
                        constraints = [('id', 'in', move_ids)]
                    else:
                        # delete and create new one
                        new_move_id = self.env['multi.invoice.payment']
                        record.create_related_inv_logs()
                        new_move_ids = record.multi_invoice_ids.search([
                            ('partner_id', '=', record.partner_id.id),
                            ('state', '=', 'posted'),
                            ('active', '=', True),
                            ('payment_id', '=', False),
                            ('invoice_payment_state', '!=', 'paid'),
                            ('type', 'in', ['out_invoice'] if record.payment_type == 'inbound' else ['in_invoice'])
                        ])

                        copied_moves = new_move_ids.browse([])
                        for rec in new_move_ids:
                            copied_moves |= rec.copy()
                        new_move_ids.write({'active': False})
                        constraints = [('id', 'in', copied_moves.ids)]

            else:
                inv = self.env['account.move'].browse(self.env.context['active_id'])
                rec = self.env['multi.invoice.payment'].create({
                    'invoice_id': inv.id,
                    'payment_due': inv.amount_residual,
                    'payment_amount': inv.amount_residual
                })
                record.multi_invoice_ids = rec

        if domain and isinstance(domain, dict) and 'domain' in domain:
            domain['domain']['multi_invoice_ids'] = constraints
        return domain

    def multi_line_domain(self):
        for rec in self:
            return_value = rec.multi_invoice_ids.search([
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'posted'),
                ('active', '=', True),
                ('payment_id', '=', False),
                ('invoice_payment_state', '!=', 'paid'),
                ('type', 'in', ['out_invoice'] if rec.payment_type == 'inbound' else ['in_invoice'])
            ])

            return return_value

    def unlink(self):
        for rec in self:
            self.env['multi.invoice.payment'].search([('payment_id', '=', rec.id)]).unlink()
            register_line = self.env['cash.register.line'].search(
                [('transaction_type', '=', 'refill'), ('record_id', '=', rec.id)])
            if register_line:
                register_line.unlink()

        return super(AccountPayment, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super(AccountPayment, self).create(vals_list)
        multi_inv_log = self.env['multi.invoice.payment']
        for rec in recs:
            if rec.multi_invoice_ids:
                rec.multi_invoice_ids.sudo().write({'payment_id': rec.id})

        # Instead of loading all draft records, use read_group to directly query only partner_id from DB
        draft_partners = self.read_group(
            [('state', '=', 'draft')],  # Filter
            ['partner_id'],  # Only fetch partner_id column
            ['partner_id']  # Group by partner_id to avoid duplicates
        )

        # Extract partner IDs from the grouped result
        open_partner_ids = [dp['partner_id'][0] for dp in draft_partners if dp['partner_id']]

        # Delete 'multi.invoice.payment' records with no payment_id and whose partner is not in open drafts
        if open_partner_ids:
            # Only run 'not in' condition if we actually have open partner IDs
            multi_inv_log.search([
                ('payment_id', '=', False),
                ('partner_id', 'not in', open_partner_ids)
            ]).unlink()
        else:
            # If no draft partners exist, delete all records with payment_id=False
            multi_inv_log.search([('payment_id', '=', False)]).unlink()

        multi_inv_log.search([('active', '=', False)]).unlink()

        return recs

    def write(self, vals):
        with self.env.cr.savepoint():
            multi_inv_log = self.env['multi.invoice.payment']
            rec = super(AccountPayment, self).write(vals)

            # 1. Unlink removed multi-invoices from this payment
            removed_lines = multi_inv_log.search([
                ('payment_id', '=', self.id),
                ('id', 'not in', self.multi_invoice_ids.ids)
            ])
            if removed_lines:
                removed_lines.sudo().write({'payment_id': False})

            # 2. Assign payment_id to added multi-invoices
            if self.multi_invoice_ids:
                self.multi_invoice_ids.sudo().write({'payment_id': self.id})

            # 3. Get partners with open draft payments (use set for faster checks)
            open_partner_ids = set(
                self.search([('state', '=', 'draft')]).mapped('partner_id').ids
            )

            # 4. Unlink orphan multi-invoices (no payment, partner not in open drafts)
            orphan_records = multi_inv_log.search([
                ('payment_id', '=', False),
                ('partner_id', 'not in', list(open_partner_ids))
            ])
            if orphan_records:
                orphan_records.unlink()

            # 5. Clean inactive records
            inactive_records = multi_inv_log.search([('active', '=', False)])
            if inactive_records:
                inactive_records.unlink()

            return rec

    @api.onchange('multi_invoice_ids')
    def _onchange_multi_invoice_ids(self):
        for rec in self.filtered(lambda l: l.multi_invoice_ids):
            for inv in rec.multi_invoice_ids:
                if inv.payment_amount == 0.0:
                    inv.update({
                        'payment_amount': float(inv.payment_due)
                    })
            rec.update({
                'amount': sum(rec.multi_invoice_ids.mapped('payment_amount')) if sum(
                    rec.multi_invoice_ids.mapped('payment_amount')) >= 0 else sum(
                    rec.multi_invoice_ids.mapped('payment_amount')) * -1
            })

    def action_register_payment(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return ''
        new_context = self._context.copy()
        new_context['default_payment_category'] = 'inv_payment'
        if active_ids:
            invoice = self.env['account.move'].browse(active_ids)
            new_context['default_partner_id'] = invoice.partner_id.id

        if len(active_ids) == 1:
            action = {
                'name': _('Register Payment'),
                'res_model': 'account.payment',
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_account_payment_form').id,
                'context': new_context,
                'type': 'ir.actions.act_window',
            }
            rec_exist = self.env['account.payment'].search(
                [('state', '=', 'draft'), ('invoice_ids', '!=', False), ('invoice_ids.id', 'in', active_ids)], limit=1)
            if rec_exist:
                action['res_id'] = rec_exist.id
        else:
            # For multiple invoices, open the standard payment register wizard
            action = {
                'name': _('Register Payment'),
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'context': new_context,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        return action

    def _prepare_payment_moves(self):
        """Removed in Odoo 14+. Multi-invoice payment posting is handled in the action_post override below."""
        return super(AccountPayment, self)._prepare_payment_moves() if hasattr(super(), '_prepare_payment_moves') else []

    def check_advance(self):
        for rec in self:
            if (rec.payment_type == 'outbound' and
                    'advance_payment' in rec.multi_invoice_ids.mapped('payment_difference_handling')):
                raise ValidationError(_("You can not select the advance payment feature while payment type is outbound!"))

    def check_amount_residuals(self):
        for record in self:
            if record.multi_invoice_ids:
                for rec in record.multi_invoice_ids:
                    if rec.invoice_id.amount_residual != rec.payment_due:
                        raise ValidationError(_("Amount Residuals Mismatch."))

    def post(self):
        """The post() method was removed in Odoo 14+; use action_post() instead.
        This is kept as a stub for any remaining Odoo 13 code that calls it."""
        return self.action_post()

    def validate_lines(self):
        for rec in self:
            # Check for advance payment handling and payment difference
            advance_payment_lines = rec.multi_invoice_ids.filtered(lambda l: l.payment_difference_handling == 'advance_payment')
            if advance_payment_lines:
                for line in advance_payment_lines:
                    if line.payment_difference > -1:
                        raise UserError(_("You cannot select advance payment while you are not actually paying it"))
                    if not line.writeoff_account_id:
                        raise UserError(_("You have to select the Advance Payment Account before paying advance payment"))

            # Check for payment difference and invoice type
            non_advance_payment_lines = rec.multi_invoice_ids.filtered(
                lambda x: x.payment_difference_handling != 'advance_payment' and
                           x.payment_difference <= -1 and
                           x.invoice_id.move_type not in ['out_refund', 'in_invoice'])
            if non_advance_payment_lines:
                raise UserError(_("You have to select Advance Payment Action when you are actually paying it"))
