import json
import base64
import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import dateutil.parser


class InvestmentPlanExt(models.Model):
    _inherit = 'investment.plan'
    _description = 'Investment Plan'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)

    date = fields.Date(required=True)
    amount = fields.Float()
    installment_number = fields.Integer(readonly=False)
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move', 'Ref')
    state = fields.Char(string='Status', readonly=False, related='invoice_id.invoice_way_type')
    # installment_type = fields.Selection([
    #     ('down', 'Down Payment'),
    #     ('installment', 'Investment Installment'),
    #     ('adjustment', 'Investment Adjustment'),
    # ])
    installment_type = fields.Selection([
        ('down', 'Booking Payment'),
        ('installment', 'Investment Installment'),
        ('adjustment', 'Investment Adjustment'),
        ('balloon', 'Balloon'),
        ('final', 'Final Payment'),
        ('possession_amount', 'Possession'),
        ('balloting_amount', 'Balloting'),
        ('confirmation_amount', 'Confirmation')
    ])
    invoice = fields.Char(related='invoice_id.name', store=True, readonly=False)

    payment_date = fields.Date('Payment Date', store=True, compute='_payment_date', readonly=False)
    property_invoice_type = fields.Selection([
        ('initial_payment', 'Initial Payment'),
        ('installment', 'Installment'),
        ('transfer_application', 'Transfer Application'),
        ('others', 'Others'),
    ], related='invoice_id.property_invoice_type', store=True, readonly=False, string='Invoice Type')
    amount_paid = fields.Float('Amount Paid', store=True, compute='_invoice_id_data', readonly=False)
    residual = fields.Float('Amount Due', store=True, compute='_invoice_id_data', readonly=False)
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=False, copy=False, tracking=True,
        related='invoice_id.payment_state')
    file_adjusted_amount = fields.Float()
    adjustment_amount = fields.Float()
    balance_amount = fields.Float()
    double_check_paid_amount = fields.Boolean(compute="_double_check_paid_amount")
    installment_name = fields.Char()
    investment_id = fields.Many2one('investment')

    marketing_share = fields.Float(string="Marketing")
    dealer_share = fields.Float(string="Dealer")
    rebate_amount = fields.Float(string="Rebate Amount")
    rebate_given = fields.Float(string="Rebate Given")
    dealer_rebate_given = fields.Float(string="Dealer Given")
    marketing_rebate_given = fields.Float(string="Marketing Given")
    move_ids = fields.Many2many('account.move')
    net_receivable = fields.Float(string="Net Receivable", compute="compute_net_receivable", store=True)
    net_payment = fields.Float(string="Net Payment")
    rebate_adjustment = fields.Float(string="Rebate Adjustment")

    def compute_net_receivable(self):
        for rec in self:
            rec.net_receivable = rec.amount - rec.dealer_share

    def compute_net_payment(self):
        for rec in self:
            # booking_paid = 0
            # booking_rebate_adjusted = 0
            if rec.installment_type == 'down' and rec.invoice_id and rec.company_id.id in [5, 16]:
                # payment_lines = self.env['multi.invoice.payment'].search([('invoice_id', '=', rec.invoice_id.id), ('payment_id.state', '=', 'posted')])
                # if payment_lines:
                #     booking_paid = sum(x.payment_amount for x in payment_lines)
                #     booking_rebate_adjusted = sum(
                #         x.payment_difference for x in payment_lines.filtered(lambda l: l.payment_difference_handling == 'commission_adjustment' or l.payment_difference_handling ==
                #                                                                        'reconcile'))
                # else:
                #     booking_paid = 0
                #     booking_rebate_adjusted = 0
                rec.rebate_adjustment = rec.dealer_share
                rec.net_payment = rec.amount_paid - rec.dealer_share if rec.amount_paid - rec.dealer_share > 0 else 0
            # if rec.installment_name == 'Confirmation' and rec.company_id.id == 5:
            #     rec.rebate_adjustment = rec.dealer_share
                # rec.net_payment = rec.amount - rec.dealer_share

    def calculate_rebate_given_for_confirmation(self):
        for rec in self.filtered(lambda l: l.installment_type == 'confirmation_amount'):
            dealer_given = 0
            marketing_given = 0
            total_given = 0
            open_files = self.env['investor.file'].search([('investment_id', '=', rec.investment_id.id)])
            if open_files:
                for file in open_files:
                    if file.installment_plan_ids:
                        for line in file.installment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation_amount' and l.move_ids):
                            dealer_given += line.dealer_rebate_given
                            marketing_given += line.marketing_rebate_given
                            total_given += line.rebate_given
            rec.dealer_rebate_given = dealer_given
            rec.marketing_rebate_given = marketing_given
            rec.rebate_given = total_given
        for rec in self.filtered(lambda l: l.installment_type == 'down' and l.move_ids):
            dealer_given = 0
            dealer_given = sum(x.amount_total for x in rec.move_ids)
            rec.dealer_rebate_given = dealer_given
            rec.rebate_given = dealer_given
