# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class AccountMoveExtension(models.Model):
    _inherit = 'account.move'

    investor_file_id = fields.Many2one('investor.file')
    property_invoice_type = fields.Selection(selection_add=[
        ('down', 'Booking'),
        ('confirmation_amount', 'Confirmation'),
        ('balloon', 'Balloon'),
        ('balloting_amount', 'Balloting'),
        ('possession_amount', 'Possession'),
        ('final', 'Final Payment'),
        ('merger_fee', 'Merger Fee')
    ])

    def get_balance_of_account(self, account_id):
        balance = 0
        today = fields.Date.today().strftime("%Y-%m-%d")
        today_date = str(today)
        # today_date = '2022-10-06'
        account_sql = "SELECT COALESCE(SUM(line.debit - line.credit),0) AS balance FROM account_move_line line INNER JOIN account_move move ON (line.move_id=move.id) WHERE move.state = 'posted' " \
                      "AND line.account_id = " + str(account_id) + " AND move.date = '" + today_date + "' "
        self.env.cr.execute(account_sql)
        account_balance = self._cr.fetchall()[0]
        if account_balance:
            balance = account_balance
        return int(balance[0])

    @api.model
    def send_accounts_balance_sms(self):
        today = fields.Date.today().strftime("%Y-%m-%d")
        today_date = str(today)
        # account_1_debit_entries = self.env['account.move.line'].search([('move_id.date', '<=', today_date), ('move_id.state', '=', "posted"), ('account_id', '=', account_1_id)])
        # account_1_debits = sum(line.debit for line in debit_entries)
        #
        # account_1_credit_entries = self.env['account.move.line'].search([('move_id.date', '<=', today_date), ('move_id.state', '=', "posted"), ('account_id', '=', account_1_id)])
        # account_1_credits = sum(line.credit for line in credit_entries)
        # account_1_balance = account_1_debits - account_1_credits
        account_1 = self.env['account.account'].search([('id', '=', 3366)])
        account_2 = self.env['account.account'].search([('id', '=', 3064)])
        account_3 = self.env['account.account'].search([('id', '=', 3061)])
        account_1_id = account_1.id
        account_2_id = account_2.id
        account_3_id = account_3.id
        # account_1_sql = "SELECT COALESCE(SUM(line.debit - line.credit),0) AS balance FROM account_move_line line INNER JOIN account_move move ON (line.move_id=move.id) WHERE line.account_id = "
        #                  ""+account_1_id+" AND move.state = 'posted' AND move.date <= '"+today_date+"'"
        # account_1_sql = "SELECT COALESCE(SUM(line.debit - line.credit),0) AS balance FROM account_move_line line INNER JOIN account_move move ON (line.move_id=move.id) WHERE move.state = 'posted' " \
        #                 "AND line.account_id = " + str(account_1_id) + " AND move.date <= '" + today_date + "' "
        # self.env.cr.execute(account_1_sql)
        # account_1_balance = self._cr.fetchall()[0]
        account_1_balance = self.get_balance_of_account(account_1_id)
        account_2_balance = self.get_balance_of_account(account_2_id)
        account_3_balance = self.get_balance_of_account(account_3_id)
        # balances = account_1_balance + account_2_balance + account_3_balance
        company = self.env['res.company'].search([('id', '=', 5)], limit=1)
        message_body = f"Today's Position for the Accounts is :\n{account_1.name} = {account_1_balance}\n{account_2.name} = {account_2_balance}\n{account_3.name} = {account_3_balance}"
        # send_to = company.owner_mobile
        # #self.env['tools.mixin'].sudo().simple_send(message_body, send_to)
        if company.mobile_numbers:
            for mobile in company.mobile_numbers:
                message = f"Dear {mobile.name},\n {message_body}"
                #self.env['tools.mixin'].sudo().simple_send(message, mobile.number)
