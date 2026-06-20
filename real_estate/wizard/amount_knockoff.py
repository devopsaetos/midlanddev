# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AmountKnockoff(models.TransientModel):
    _name = "amount.knockoff"
    _description = "Amount Knockoff"

    name = fields.Char()
    application_id = fields.Many2one('plot.merger.application', readonly=True)
    invoice_ids =  fields.Many2many('account.move', readonly=True)


    def knockoff(self):
        for rec in self:
            self.application_id.knockoff = True
            if not self.env.company.merjer_knockoff_journal_id.id or not self.env.company.merjer_knockoff_payment_method_id.id:
                raise ValidationError(_('You should have to set Journal and payment methods first for accomplishing this process'))
            for inv in rec.invoice_ids:
                if inv.state in "open":
                    created_inv = []
                    date = False
                    description = False

                    if inv.state in ['draft', 'cancel']:
                        raise UserError(_('Cannot create credit note for the draft/cancelled invoice.'))
                    if inv.reconciled and mode in ('cancel'):
                        raise UserError(_('Cannot create a credit note for the invoice which is already reconciled, invoice should be unreconciled first, then only you can add credit note for this invoice.'))

                    date = fields.Date.today()

                    description = inv.name
                    refund = inv.refund(date, date, description, inv.journal_id.id)

                    created_inv.append(refund.id)
                    movelines = inv.move_id.line_ids
                    to_reconcile_ids = {}
                    to_reconcile_lines = self.env['account.move.line']
                    for line in movelines:
                        if line.account_id.id == inv.account_id.id:
                            to_reconcile_lines += line
                            to_reconcile_ids.setdefault(line.account_id.id, []).append(line.id)
                        if line.reconciled:
                            line.remove_move_reconcile()
                    refund.action_invoice_open()
                    for tmpline in refund.move_id.line_ids:
                        if tmpline.account_id.id == inv.account_id.id:
                            to_reconcile_lines += tmpline
                    to_reconcile_lines.filtered(lambda l: l.reconciled == False).reconcile()

            rec.env['file'].search([('name', '=', inv.name)]).state = 'cancel'