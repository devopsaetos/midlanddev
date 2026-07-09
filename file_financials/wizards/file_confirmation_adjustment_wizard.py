from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError


class FileConfirmationAdjustmentWizard(models.TransientModel):
    _name = 'file.confirmation.adjustment.wizard'
    _description = 'File Confirmation Adjustment Wizard'

    file_id = fields.Many2one('file')
    from_file = fields.Boolean()
    confirmation_residual = fields.Float(string="Confirmation Due Amount")
    amount = fields.Float(string="Amount to Adjust")
    advance_payment_id = fields.Many2one('account.payment', string="Advance Payment")
    advance_residual = fields.Float(string="Remaining Advance")
    adjust_commission = fields.Selection([('yes', 'Yes'), ('no', 'No')], default="no", string="Adjust Commission")

    @api.onchange('file_id')
    def populate_confirmation_data(self):
        for rec in self:
            if rec.file_id:
                rec.confirmation_residual = rec.file_id.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').residual if rec.file_id.installment_plan_ids else 0.00
                return {'domain': {
                    'advance_payment_id': [('is_advance_payment', '=', True), ('partner_id', '=', rec.file_id.investor_id.partner_id.id), ('amount_residual', '>', 0), ('state', '=', 'paid')]
                }
                }

    @api.onchange('advance_payment_id')
    def change_advance_residual(self):
        for rec in self:
            if rec.advance_payment_id:
                rec.advance_residual = rec.advance_payment_id.amount_residual
            else:
                rec.advance_residual = 0

    def generate_file_confirmation_adjustments(self):
        for rec in self:
            if rec.amount < 1:
                raise ValidationError('Please Enter the Amount to Adjust')
            if rec.amount > rec.confirmation_residual:
                error = f"You cannot Adjust more amount than Remaining"
                raise ValidationError(error)
            if rec.advance_payment_id:
                if rec.amount > rec.advance_payment_id.amount_residual:
                    error = f"You can only Adjust Amount of {rec.advance_payment_id.amount_residual} against selected Advance Payment."
                    raise ValidationError(error)
                else:
                    invoice = rec.file_id.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').invoice_id
                    payment_difference_handling = 'open'
                    if rec.adjust_commission == 'yes':
                        payment_difference_handling = 'commission_adjustment'
                    else:
                        if rec.amount == rec.confirmation_residual:
                            payment_difference_handling = 'reconcile'
                    multi_invoice_ids = self.env['multi.invoice.payment'].create({
                        'invoice_id': invoice.id,
                        'payment_due': invoice.amount_residual,
                        'payment_amount': rec.amount,
                        'payment_difference_handling': payment_difference_handling,
                        'writeoff_account_id': self.env.company.commission_adjustment_account_id.id if payment_difference_handling == 'commission_adjustment' else False,
                    })
                    Payment = self.env['account.payment'].with_context(
                        default_multi_invoice_ids=[(4, multi_invoice_ids.id, False)])

                    new_payment = Payment.create({
                        'payment_date': fields.Date.today(),
                        'payment_nature': 'on_account',
                        'advance_payment_id': rec.advance_payment_id.id,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'payment_category': 'multi_inv_payment',
                        'file_id': rec.file_id.id,
                        'partner_id': rec.file_id.membership_id.id,
                        'amount': rec.amount,
                        'journal_id': self.env.company.confirmation_adjustment_journal_id.id,
                        'company_id': self.env.company.id,
                        # 'branch_id': self.env.branch.id,
                        'currency_id': self.env.company.currency_id.id,
                        # 'payment_difference_handling': 'reconcile' if rec.amount == rec.confirmation_residual else 'open',
                        'communication': rec.advance_payment_id.name,
                    })
                    new_payment.action_post()
                    return {
                        'name': 'Confirmation Payment Adjustment',
                        'res_model': 'account.payment',
                        'type': 'ir.actions.act_window',
                        'context': {},
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': new_payment.id,
                        'domain': [('id', '=', new_payment.id)],
                        'target': 'self'
                    }


class FileModelExt(models.Model):
    _inherit = 'file'
    _description = "File"

    show_adjust_confirmation_button = fields.Boolean(compute="check_adjustment_button_visibility")

    def check_adjustment_button_visibility(self):
        for rec in self:
            show = False
            if rec.installment_plan_ids and rec.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').invoice_id:
                if rec.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').residual > 0:
                    show = True
            rec.show_adjust_confirmation_button = show

    def open_confirmation_adjustment_wizard(self):
        if self.installment_plan_ids and self.installment_plan_ids.filtered(lambda l: l.installment_name == 'Confirmation').invoice_id:
            return {
                'res_model': 'file.confirmation.adjustment.wizard',
                'type': 'ir.actions.act_window',
                'context': {'default_file_id': self.id, 'default_from_file': True},
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': self.env.ref("file_financials.file_confirmation_adjustment_wizard_form").id,
                'target': 'new'
            }
        else:
            raise ValidationError("Please Create the Confirmation Invoice First.")
