from odoo import fields, models, api


class ResCompanyExt(models.Model):
    _inherit = 'res.company'

    balloting_percentage = fields.Float()
    knockoff_journal_id = fields.Many2one('account.journal')
    knockoff_payment_method_id = fields.Many2one('account.payment.method')
    merjer_knockoff_journal_id = fields.Many2one('account.journal')
    merjer_knockoff_payment_method_id = fields.Many2one('account.payment.method')
    merjer_adjust_journal_id = fields.Many2one('account.journal')
    merjer_adjust_payment_method_id = fields.Many2one('account.payment.method')
    merjer_adjust_advance_journal_id = fields.Many2one('account.journal')
    correspondence_letter_postman = fields.Many2many('res.users')
    token_partner_id = fields.Many2one('res.partner', readonly=False)
    account_journal_id = fields.Many2one('account.journal', readonly=False)
    payment_type = fields.Selection([
        ('osp', 'One Step Payment'),
        ('tsp', 'Two Step Payment'),
    ], default='osp')
    transfer_fee = fields.Float()
    allow_bank_finance = fields.Boolean()
    payment_terms_installment_id = fields.Many2one('account.payment.term')
    payment_terms_initial_id = fields.Many2one('account.payment.term')
    payment_terms_final_id = fields.Many2one('account.payment.term')
    installment_tax_ids = fields.Many2many('account.tax')
    ownership_percentage = fields.Boolean()
    # For File Cancellation Adjustment
    file_cancel_adjust_account_id = fields.Many2one('account.account')
    file_cancel_adjust_journal_id = fields.Many2one('account.journal')
    show_provisional_allotment = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        return super(ResCompanyExt, self.with_context({'active_model': 'res.company'})).create(vals_list)
