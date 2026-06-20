# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AmountAdjust(models.TransientModel):
    _name = "amount.adjust"
    _description = "Amount Adjust"

    balance_amount = fields.Float()
    application_id = fields.Many2one('plot.merger.application', readonly=True)
    membership_id = fields.Many2one('res.member', string='Member No')
    invoice_ids =  fields.Many2many('account.move')


    def adjustment_check(self,including_criteria,balance,file,priority_product,amount=0):

        for line in self.invoice_ids:
            if line.name == file.file_id.name and line.state in "open":
                for prod in line.invoice_line_ids:
                    if not including_criteria:
                        if prod.product_id == priority_product:
                            amount = prod.price_unit if prod.price_unit <= balance else balance
                            if amount > 0:
                                self.adjust_payment(amount,line)
                            balance = balance - amount
                    
                    else:
                        amount = line.amount_residual if line.amount_residual <= balance else balance
                        if amount > 0:
                            self.adjust_payment(amount,line)

                        balance = balance - amount

        return balance

    def adjust_payment(self,amount,line):
                        
        payment = self.env['account.payment'].create({
            'payment_method_id': self.env.company.merjer_adjust_payment_method_id.id, # compulsory
            'partner_type': 'customer',
            'partner_id': line.partner_id.id,
            'amount': amount ,
            'memo': line.name,
            'state': 'draft',
            'payment_type': 'inbound',
            'journal_id': self.env.company.merjer_adjust_journal_id.id, # compulsory
            'invoice_ids': [(4, line.id)]
        })

        payment.action_validate_invoice_payment()


    def adjust(self):
        self.application_id.adjust = True

        if (
            not self.env.company.merjer_adjust_journal_id.id
            or 
            not self.env.company.merjer_adjust_payment_method_id.id
            or
            not self.env.company.merjer_adjust_advance_journal_id.id
            ):
            raise ValidationError(_('You should have to set Journal and payment methods first for accomplishing this process'))

        balance = int(round(self.balance_amount))
        
        # Pay priority of the file first

        for file in self.application_id.target_merger_id:
            
            if file.ajustment_priority == 'installment':
                priority_product = self.env.ref('real_estate.installment_product')
            elif file.ajustment_priority == 'balloting':
                priority_product = self.env.ref('real_estate.balloting_product')
            elif file.ajustment_priority == 'preference':
                priority_product = self.env.ref('real_estate.preferences_product')
            elif file.ajustment_priority == 'file':
                priority_product = 'file'


            if not file.ajustment_priority == 'file':
                balance = self.adjustment_check(False,balance,file,priority_product)
            elif file.ajustment_priority == 'file':
                balance = self.adjustment_check(True,balance,file,priority_product)
        
        # Pay remaining invoices if balance is still available
        for file in self.application_id.target_merger_id:
            if balance > 0:
                balance = self.adjustment_check(True,balance,file,'file')
        
        # Pay advance payment if balance is still available
        if balance > 0:
            action = self.env.ref('real_estate.action_advance_popup').read()[0]
            name = self.application_id.target_merger_id.mapped('file_id')[-1]
            action['context'] = "{'default_membership_id':%s,'default_file_id':%s,'default_amount':%s}" %(self.membership_id.id,name.id,balance)
            return action