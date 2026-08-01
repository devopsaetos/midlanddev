# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging
import json

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # One2many relationship to store tax line details for the invoice
    tax_line_ids = fields.One2many('account.move.tax', 'move_id',string='Tax Lines',readonly=True,copy=True)



    # One2many to store withholding tax lines
    wht_line_ids = fields.One2many('account.move.wht','move_id',string='WHT Lines',readonly=True)

    wht_total = fields.Float(compute='_compute_wht_total')  # Computed total WHT amount
    taxes_line_ids = fields.One2many('account.move.tax.lines', 'move_id')
    wht_bill_created = fields.Boolean()  # Technical field for tracking WHT billing status# Extended WHT-tax mapping

    def _compute_wht_total(self):
        """
        Computes the total withholding tax amount by summing all related tax line amounts.
        """
        self.wht_total = sum(self.taxes_line_ids.mapped('amount'))



    def create_wht_line(self, line):
        """
        Creates a WHT (Withholding Tax) line for the given journal item.

        :param line: account.move.line object that needs to generate a WHT entry.
        """
        amount = 0
        if self.move_type in ["out_invoice", "in_refund"]:
            amount = line.debit
        elif self.move_type in ["in_invoice", "out_refund"]:
            amount = line.credit

        if amount:
            self.wht_line_ids.create({
                'name': 'Withholding Tax',
                'account_id': line.account_id.id,
                'amount': amount,
                'move_id': self.id
            })

    def _synchronize_business_models(self, changed_fields):
        """
        Keeps account.payment and account.bank.statement.line in sync with journal entries (account.move).
        Uses context flag 'skip_account_move_synchronization' to avoid recursion loops.

        :param changed_fields: Set of modified fields triggering synchronization.
        """
        if self._context.get('skip_account_move_synchronization'):
            return

        # Call parent method to handle standard synchronization
        super()._synchronize_business_models(changed_fields)

    def action_post(self):
        """
        Overrides the post method to automatically create WHT move lines for applicable entries
        based on taxes configured. Also invokes `create_wht_line` where applicable.
        """
        # Pre-filtered WHT lines (custom is_wht_line boolean)
        wht_lines = self.line_ids.filtered(lambda line: line.is_wht_line)

        for move in self:
            if move.move_type in ('in_invoice', 'out_invoice'):
                line_ids = []

                for line in move.line_ids:
                    if line.wht_tax_ids:
                        for wht in line.wht_tax_ids:
                            line_ids = self.generate_wht_move_lines(wht, line, line_ids, move)
                if line_ids:
                    move.write({'line_ids': line_ids})

        for wht_line in wht_lines:
            if wht_line.wht_tax_ids.tax_application == 'invoice':
                self.create_wht_line(wht_line)

        return super(AccountMove, self).action_post()

    def append_entry(self, wht, tax_amount, line, line_ids, move=None, tax_line=None):
        """
        Appends a withholding tax line to the journal entry and adjusts the original debit/credit lines accordingly.

        :param wht: Withholding tax record.
        :param tax_amount: The base tax amount used for WHT calculation.
        :param line: The journal line being processed (dict or ORM object).
        :param line_ids: List of new lines to append.
        :param move: Account move associated.
        :param tax_line: Optional tax line involved in the transaction.
        :return: Modified list of line_ids with appended WHT journal line.
        :return: Modified list of line_ids with appended WHT journal line.
        """
        wht_amount = 0

        if wht.type_tax_use != 'tax':
            # WHT applied on subtotal (not tax-on-tax)
            product_amount_including_tax = tax_amount + line.price_subtotal
            wht_amount = round(line.price_total * (wht.amount / 100), 2)
            # if wht_amount < 0:
            #     wht_amount *= -1

        elif tax_amount and tax_line.ids[0] in wht.sale_tax_id.ids and wht.type_tax_use == 'tax':
            # WHT applied on tax-on-tax scenario
            tax_on_taxes = round(tax_amount * (wht.amount / 100), 2)
            wht_amount = tax_on_taxes

        debit = 0.00
        credit = 0.00
        jv_line_updated = False

        if move:
            if wht_amount > 0:
                if move.move_type == 'out_invoice':
                    if line['credit'] != 0.0 and 'Write-Off' not in line['name'] and \
                            line['name'] not in self.env['account.wht'].search([]).mapped('name'):
                        line['credit'] = round(line['credit'] - wht_amount, 2)
                        jv_line_updated = True
                if move.move_type == 'in_invoice':
                    if line['debit'] != 0.0 and 'Write-Off' not in line['name'] and \
                            line['account_id'] not in [wht.account_id.id]:
                        line['debit'] = round(line['debit'] - wht_amount, 2)
                        jv_line_updated = True
                debit = wht_amount
                credit = 0.00

            if wht_amount < 0:
                if move.move_type == 'out_invoice':
                    if line['credit'] != 0.0 and 'Write-Off' not in line['name'] and \
                            line['name'] not in self.env['account.wht'].search([]).mapped('name'):
                        line['credit'] = round(line['credit'] - wht_amount, 2)
                        jv_line_updated = True
                    debit = 0.00
                    credit = wht_amount * -1
                if move.move_type == 'in_invoice':
                    if line['debit'] != 0.0 and 'Write-Off' not in line['name'] and \
                            line['account_id'] not in [wht.account_id.id]:
                        line['debit'] = round(line['debit'] - wht_amount, 2)
                        jv_line_updated = True
                    debit = wht_amount * -1
                    credit = 0.00

            if wht_amount and jv_line_updated:
                # Custom WHT line is appended to the invoice move
                # debit = wht_amount if move.move_type in ["out_invoice", "in_refund"]  else 0.0
                # credit = wht_amount if move.move_type in ["in_invoice", "out_refund"] else 0.0

                line_ids.append((0, 0, {
                    'name': wht.name,
                    'account_id': wht.account_id.id,
                    'debit': debit,
                    'credit': credit,
                    'partner_id': self.partner_id.id,
                    'display_type': 'tax',
                    'wht_tax_ids': [(6, 0, [wht.id])],
                    'is_wht_line': True
                }))

        return line_ids

    def generate_wht_move_lines(self, wht, line, line_ids, move=None):
        """
        Generates withholding tax (WHT) move lines when tax is applied at the invoice level.

        :param wht: WHT tax object
        :param line: Invoice line for which WHT needs to be applied
        :param line_ids: Existing list of journal line dictionaries
        :param move: Optional account.move record (usually self)
        :return: Updated line_ids including WHT journal entries
        """
        if wht.tax_application == 'invoice':
            tax_amount = 0
            if line.tax_ids:
                for tax_line in line.tax_ids:
                    tax_amount = line.price_subtotal * round(tax_line.amount / 100, 2)
                    return self.append_entry(wht, tax_amount, line, line_ids, move, tax_line=tax_line)
            else:
                return self.append_entry(wht, tax_amount, line, line_ids, move, tax_line=None)
        return line_ids

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        """
        Onchange handler for invoice lines. Optionally assigns default WHT taxes based on partner
        and generates WHT journal entries. Currently, WHT logic is commented but can be toggled as needed.
        Also removes previously generated WHT lines and regenerates if needed.
        """
        invoice_line_ids = self.invoice_line_ids

        line_ids = []
        # for line in invoice_line_ids:
        #     if self.move_type == 'out_invoice' and self.partner_id.sale_wht_ids and not line.wht_tax_ids:
        #         line.wht_tax_ids = self.partner_id.sale_wht_ids.ids
        #     if self.move_type == 'in_invoice' and self.partner_id.purchase_wht_ids and not line.wht_tax_ids:
        #         line.wht_tax_ids = self.partner_id.purchase_wht_ids.ids

        #     if line.wht_tax_ids:
        #         for wht in line.wht_tax_ids:
        #             line_ids = self.generate_wht_move_lines(wht, line, line_ids, self)

        # Remove old WHT lines (is_wht_line = True)
        wht_move_lines = [(2, wht.id) for wht in self.line_ids.filtered(lambda l: l.is_wht_line)]
        if wht_move_lines:
            self.line_ids = wht_move_lines

        if line_ids:
            self.line_ids = line_ids
            self.invoice_line_ids = invoice_line_ids

        return super(AccountMove, self)._onchange_quick_edit_line_ids()

    def action_register_payment(self):
        """
        Overrides the standard 'Register Payment' action to pass default WHT tax IDs to the payment wizard
        when WHT is configured to apply on 'payment'.
        """
        wht_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type != True).wht_tax_ids.filtered(
            lambda s: s.tax_application == 'payment')
        if wht_lines:
            wht_ids = wht_lines.ids
        else:
            wht_ids = []  # or self.invoice_line_ids.mapped('wht_tax_ids').ids

        if wht_ids:
            return {
                'name': _('Register Payment'),
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'context': {
                    'active_model': 'account.move',
                    'active_ids': self.ids,
                    'default_wht_payment_ids': wht_ids,
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        else:
            return super(AccountMove, self).action_register_payment()

    @api.onchange('invoice_line_ids')
    def on_change_tax_ids(self):
        """
        Onchange event to recompute and populate WHT tax lines in `taxes_line_ids` based on
        line-level WHT settings and tax structure (whether tax-on-subtotal or tax-on-tax).
        """
        for move in self:
            move.taxes_line_ids = [(5,)]  # Clear previous WHT tax line records

            for line in move.invoice_line_ids:
                if line.wht_tax_ids:
                    data = []
                    for rec in line.wht_tax_ids:
                        if rec.type_tax_use != 'tax':
                            # WHT applied on subtotal
                            vals = {
                                'name': rec.name,
                                'amount': round(line.price_total * (rec.amount / 100), 2),
                                'account_id': rec.account_id.id,
                                'wht_tax_id': rec.ids[0],
                                'move_id': move.id,
                            }
                            data.append(vals)
                            move.taxes_line_ids = [(0, 0, vals)]

                        if rec.type_tax_use == 'tax' and rec.sale_tax_id.id in line.tax_ids.ids:
                            # WHT applied on tax amount
                            if rec.sale_tax_id.price_include:
                                amount_after_tax = round(line.price_subtotal / (1 + rec.sale_tax_id.amount / 100), 2)
                                tax_amount = line.price_subtotal - amount_after_tax
                            else:
                                tax_amount = round(line.price_subtotal * (rec.sale_tax_id.amount / 100), 2)

                            vals = {
                                'name': rec.name,
                                'amount': round(tax_amount * (rec.amount / 100), 2),
                                'account_id': rec.account_id.id,
                                'wht_tax_id': rec.ids[0],
                                'move_id': move.id,
                            }
                            data.append(vals)
                            move.taxes_line_ids = [(0, 0, vals)]

    def button_draft(self):
        """
        Reverts the move to draft and deletes any WHT journal lines (is_wht_line = True)
        that were created during posting.
        """
        res = super(AccountMove, self).button_draft()
        wht_lines = self.line_ids.filtered(lambda l: l.is_wht_line)
        if wht_lines:
            wht_lines.unlink()

        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Many2many relation to link one or more WHT rules to the invoice line
    wht_tax_ids = fields.Many2many('account.wht',string='WHT')

    # Boolean flag to identify if the line was generated due to WHT logic
    is_wht_line = fields.Boolean()

    # Optional reference to another move, used in case WHT lines relate to a different document
    wht_invoice_ref_id = fields.Many2one('account.move')

    @api.ondelete(at_uninstall=False)
    def _prevent_automatic_line_deletion(self):
        """
        Prevent deletion of critical journal entry lines:
        - Tax lines (except WHT) that would break tax reports
        - Payment term lines affecting payment structure

        Allows deletion only if `dynamic_unlink` context is set (e.g., cleanup scenarios).
        """
        if not self.env.context.get('dynamic_unlink'):
            for line in self:
                if line.display_type == 'tax' and line.move_id.line_ids.tax_ids and not line.is_wht_line:
                    raise ValidationError(_(
                        "You cannot delete a tax line as it would impact the tax report"
                    ))
                elif line.display_type == 'payment_term':
                    raise ValidationError(_(
                        "You cannot delete a payable/receivable line as it would not be consistent "
                        "with the payment terms"
                    ))
