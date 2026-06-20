# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ReminderLetters(models.TransientModel):
    _name = 'reminder.letters'

    _description = "Reminder Letter"

    MONTH_SELECTION = [
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ]
    starting_month = fields.Selection(MONTH_SELECTION, string="Starting Month")
    ending_month = fields.Selection(MONTH_SELECTION, string="Ending Month")

    members_id = fields.Many2many('res.member')


    def print_letters(self):
    	starting_month = self.starting_month
    	ending_month = self.ending_month

    	record_id = []

    	for file in self.env['file'].search([('membership_id', 'in', self.members_id.ids)]):
    		if self.env['installment.plan'].search_count([
    			('file_id', '=', file.id),
    			('state', '=', 'open'),
    			('date', '<', fields.Date.today())]):
    				record_id.append(file.id)

    	file_id = self.env['file'].search([('id', 'in', record_id)])

    	return self.env.ref('real_estate.reminder_letter_action').report_action(file_id)