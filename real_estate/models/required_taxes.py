# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TaxSetup(models.Model):
    _name = 'tax.setup'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Tax Setup"

    name = fields.Char(required=True)

    transaction_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('cancelation', 'Cancellation'),
        ('merge', 'Merge'),
        ('refund', 'Refund'),
    ])
    setup_for = fields.Selection([
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ])

    tax_setup_line_ids = fields.One2many('tax.setup.lines', 'tax_setup_id')


class TaxSetupLines(models.Model):
    _name = 'tax.setup.lines'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Tax Setup Lines"

    name = fields.Char(required=True)
    description = fields.Text()
    rate = fields.Float()
    tax_status = fields.Selection([
        ('filer', 'Filer'),
        ('non_filer', 'Non-Filer'),
    ], string='Tax Status')
    product_id = fields.Many2one('product.product')

    tax_setup_id = fields.Many2one('tax.setup')


class RequiredTaxes(models.Model):
    _name = 'required.taxes'
    _description = "Required Taxes"
    _rec_name = 'transfer_req_id'

    membership_id = fields.Many2one('res.member', 'Seller')
    seller_name = fields.Char()
    seller_total_tax = fields.Float(compute='_compute_total_tax')
    seller_invoices = fields.Integer(compute='_compute_seller_invoices')
    seller_required_tax_ids = fields.One2many('required.taxes.line', 'required_taxes_seller_id')

    transferee_partner_id = fields.Many2one('res.member', 'Buyer')
    buyer_name = fields.Char()
    buyer_total_tax = fields.Float(compute='_compute_total_tax')
    buyer_required_tax_ids = fields.One2many('required.taxes.line', 'required_taxes_buyer_id')

    charges_partner_id = fields.Many2one('res.member', 'Partner')
    total_charges = fields.Float()
    other_charges_ids = fields.One2many('other.charges', 'required_taxes_id')

    transfer_req_id = fields.Many2one('file.transfer.request')
    transfer_app_id = fields.Many2one('transfer.application')


    @api.depends('seller_required_tax_ids', 'buyer_required_tax_ids', 'other_charges_ids')
    def _compute_total_tax(self):
        for rec in self:
            rec.seller_total_tax = sum(self.seller_required_tax_ids.mapped('amount'))
            rec.buyer_total_tax = sum(self.buyer_required_tax_ids.mapped('amount'))
            rec.total_charges = sum(self.other_charges_ids.mapped('amount'))


class RequiredTaxesLine(models.Model):
    _name = 'required.taxes.line'
    _description = "Required Taxes Lines"

    name = fields.Char('Member Name')
    rule = fields.Many2one('tax.setup')
    rate = fields.Float()
    amount = fields.Float(store=True, compute='_compute_amount')
    product_id = fields.Many2one('product.product', required=True)

    required_taxes_seller_id = fields.Many2one('required.taxes')
    required_taxes_buyer_id = fields.Many2one('required.taxes')

    @api.depends('required_taxes_seller_id.transfer_req_id', 'required_taxes_buyer_id.transfer_req_id','rate')
    def _compute_amount(self):
        for rec in self:
            if rec.required_taxes_seller_id:
                rec.amount = rec.required_taxes_seller_id.transfer_req_id.deal_price * (rec.rate/100)
            if rec.required_taxes_buyer_id:
                rec.amount = rec.required_taxes_buyer_id.transfer_req_id.deal_price * (rec.rate/100)


class OtherCharges(models.Model):
    _name = 'other.charges'
    _description = "Other Charges"

    amount = fields.Float()
    product_id = fields.Many2one('product.product', required=True, default=lambda s: s.env.ref('real_estate.file_transfer').id)

    required_taxes_id = fields.Many2one('required.taxes')

