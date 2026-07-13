# -*- coding: utf-8 -*-
# Part of Odoo, Flectra. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from ast import literal_eval


class ResConfigSettingsRSMS(models.TransientModel):
    _inherit = 'res.config.settings'

    balloting_percentage = fields.Float(related='company_id.balloting_percentage', readonly=False)
    knockoff_journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'purchase')], related='company_id.knockoff_journal_id', readonly=False)
    knockoff_payment_method_id = fields.Many2one('account.payment.method', related='company_id.knockoff_payment_method_id', readonly=False)
    merjer_knockoff_journal_id = fields.Many2one('account.journal', related='company_id.merjer_knockoff_journal_id', readonly=False)
    merjer_knockoff_payment_method_id = fields.Many2one('account.payment.method', related='company_id.merjer_knockoff_payment_method_id', readonly=False)
    merjer_adjust_journal_id = fields.Many2one('account.journal', related='company_id.merjer_adjust_journal_id', readonly=False)
    merjer_adjust_payment_method_id = fields.Many2one('account.payment.method', related='company_id.merjer_adjust_payment_method_id', readonly=False)
    merjer_adjust_advance_journal_id = fields.Many2one('account.journal', related='company_id.merjer_adjust_advance_journal_id', readonly=False)
    correspondence_letter_postman = fields.Many2many('res.users', related='company_id.correspondence_letter_postman', readonly=False)
    group_unit_size_in_range = fields.Boolean('Unit Size in Range', implied_group='real_estate.group_unit_size_in_range', readonly=False)
    group_unit_size_in_specific = fields.Boolean(default=True, implied_group='real_estate.group_unit_size_in_specific', readonly=False)
    token_partner_id = fields.Many2one('res.partner', readonly=False, related='company_id.token_partner_id')
    account_journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'sale')], readonly=False, related='company_id.account_journal_id')
    merger_advance_account_id = fields.Many2one('account.account', readonly=False, related='company_id.merger_advance_account_id')
    payment_type = fields.Selection([
        ('osp', 'One Step Payment'),
        ('tsp', 'Two Step Payment'),
    ], readonly=False, related='company_id.payment_type')
    transfer_fee = fields.Float(readonly=False, related='company_id.transfer_fee')
    allow_bank_finance = fields.Boolean(readonly=False, related='company_id.allow_bank_finance')
    payment_terms_installment_id = fields.Many2one('account.payment.term', readonly=False, related='company_id.payment_terms_installment_id')
    payment_terms_initial_id = fields.Many2one('account.payment.term', readonly=False, related='company_id.payment_terms_initial_id')
    payment_terms_final_id = fields.Many2one('account.payment.term', readonly=False, related='company_id.payment_terms_final_id')
    installment_tax_ids = fields.Many2many('account.tax', readonly=False, related='company_id.installment_tax_ids')
    ownership_percentage = fields.Boolean(readonly=False, related='company_id.ownership_percentage')
    # File Cancellation Adjustment Fields
    file_cancel_adjust_account_id = fields.Many2one('account.account', related='company_id.file_cancel_adjust_account_id', readonly=False)
    file_cancel_adjust_journal_id = fields.Many2one('account.journal', related='company_id.file_cancel_adjust_journal_id', readonly=False)
    show_provisional_allotment = fields.Boolean(readonly=False, related='company_id.show_provisional_allotment')

    @api.onchange('group_unit_size_in_range')
    def _onchange_group_unit_size_in_range(self):
        if self.group_unit_size_in_range:
            self.group_unit_size_in_specific = False
        else:
            self.group_unit_size_in_specific = True

    @api.model
    def create(self, values):
        if ('company_id' in values):
            company = self.env['res.company'].browse(values.get('company_id'))
            company.balloting_percentage = self.balloting_percentage
            company.knockoff_journal_id = self.knockoff_journal_id
            company.knockoff_payment_method_id = self.knockoff_payment_method_id
            company.merjer_knockoff_journal_id = self.merjer_knockoff_journal_id
            company.merjer_knockoff_payment_method_id = self.merjer_knockoff_payment_method_id
            company.merjer_adjust_journal_id = self.merjer_adjust_journal_id
            company.merjer_adjust_payment_method_id = self.merjer_adjust_payment_method_id
            company.merjer_adjust_advance_journal_id = self.merjer_adjust_advance_journal_id
            company.correspondence_letter_postman = self.correspondence_letter_postman
            company.token_partner_id = self.token_partner_id
            company.account_journal_id = self.account_journal_id
            company.merger_advance_account_id = self.merger_advance_account_id
            company.payment_type = self.payment_type
            company.transfer_fee = self.transfer_fee
            company.allow_bank_finance = self.allow_bank_finance
            company.payment_terms_installment_id = self.payment_terms_installment_id
            company.payment_terms_initial_id = self.payment_terms_initial_id
            company.payment_terms_final_id = self.payment_terms_final_id
            company.installment_tax_ids = self.installment_tax_ids
            company.ownership_percentage = self.ownership_percentage
            company.file_cancel_adjust_account_id = self.file_cancel_adjust_account_id
            company.file_cancel_adjust_journal_id = self.file_cancel_adjust_journal_id
            company.show_provisional_allotment = self.show_provisional_allotment

        return super(ResConfigSettingsRSMS, self).create(values)
