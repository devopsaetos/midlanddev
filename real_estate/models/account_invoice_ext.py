# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountInvoiceExt(models.Model):
    _inherit = 'account.move'

    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('adv_and_securities', 'Advances and Securities'),
        ('installment', 'Installment'),
        ('initial_payment_plus_installment', 'Initial Payment + Installment'),
        ('transfer_application', 'Transfer Application'),
        ('rent', 'Rent'),
        ('others', 'Others'), ('token', 'Token'),
        ('investment', 'Investment'), ('investment_installment', 'Investment Installment'),
        ('maintenance', 'Maintenance Charges'), ('map_fee', 'Mapping Fee'),
        ('tax', 'PRA-Tax'), ('236k_sale', '236k-Sale'),
        ('236k_sale', '236k-Sale'),
        ('demarcation', 'Demarcation'),
        ('merger_adjustment', 'Merger Adjustment'),
    ])

    invoice_way_type = fields.Char(compute='_invoice_status')
    invoice_way_value = fields.Char()
    not_sync = fields.Boolean()
    file_ids = fields.Many2one('file', string="Files")
    installment_id = fields.Many2one('installment.plan', string="Installment No.")
    crm_id = fields.Many2one('crm.lead')
    token_id = fields.Many2one('token.money')
    required_tax_id = fields.Many2one('required.taxes', 'Required Taxes', readonly=True)

    token_partner = fields.Char()
    transaction_type = fields.Char('Transaction Type', default='Others')
    unit_swap_request_id = fields.Many2one('unit.swapping.request')
    merger_application_id = fields.Many2one('plot.merger.application', readonly=True)

    # is_draft_duplicated_ref_ids / is_exact_move_duplicate / action_delete_duplicates
    # moved to default_payment/models/account_move.py — that module loads before this one
    # and needs them available when its own inheriting view of account.move.form validates.

    def _invoice_status(self):
        for rec in self:
            if not rec.not_sync:
                rec.invoice_way_type = rec.state
            else:
                rec.invoice_way_type = rec.invoice_way_value

    def _post(self, soft=True):
        try:
            return super(AccountInvoiceExt, self)._post(soft=soft)
        except UserError as e:
            if "Even magicians can't post nothing!" in str(e):
                pass
            else:
                raise

    @api.model_create_multi
    def create(self, vals_list):
        file_id = None

        for val in vals_list:
            if self.env.context.get('active_model') and self.env.context.get('active_model') == "file":
                file_id = self.env['file'].browse(self.env.context['active_ids'])

            if val.get('file_ids') != None:
                file_id = val.get('file_ids')
                file_id = self.env['file'].browse(file_id)
                del val['file_ids']

        # if file_id:

        # for rec in vals['invoice_line_ids']:
        #
        # 	if file_id.is_downpayment != 'not_paid'  and rec[2]['product_id'] == self.env.ref('real_estate.downpayment_product').id:
        # 		raise ValidationError(_("You could not pay Down Payment twice for a same invoice"))
        #
        # 	if file_id.is_preference != 'not_paid'  and rec[2]['product_id'] == self.env.ref('real_estate.preferences_product').id:
        # 		raise ValidationError(_("You could not pay Prefernce twice for a same invoice"))
        #
        # 	if file_id.is_balloting != 'not_paid'  and rec[2]['product_id'] == self.env.ref('real_estate.balloting_product').id:
        # 		raise ValidationError(_("You could not pay Balloting twice for a same invoice"))

        rec = super(AccountInvoiceExt, self).create(vals_list)

        if file_id:
            file_id.file_payment_history_id.create({
                'invoice_id': rec.id,
                'file_id': file_id.id})

        return rec
