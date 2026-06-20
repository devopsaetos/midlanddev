# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
import re


class Cnic(models.Model):
    _name = 'res.cnic'
    _description = "CNIC"

    cnic = fields.Char('CNIC', copy=False)
    cnic_expiry_date = fields.Date('CNIC Expiry Date')
    cnic_front = fields.Binary(attachment=True, string='CNIC Front')
    cnic_back = fields.Binary(attachment=True, string='CNIC Back')
    member_name = fields.Char()
    phone = fields.Char()
    address = fields.Text()
    name = fields.Char('Father/Spouse')
    father_spouse_cnic = fields.Char('Father CNIC')
    tax_status = fields.Selection([
        ('filer', 'Filer'),
        ('non_filer', 'Non-Filer'),
    ], string='Tax Status')
    ownership = fields.Float()

    member_id = fields.Many2one('res.member', ondelete='cascade')
    token_id = fields.Many2one('token.money')

    # @api.constrains('ownership')
    # def check_percentage(self):
    #     for rec in self:
    #         if rec.member_id.is_member:
    #             if rec.ownership < 0:
    #                 raise ValidationError("Ownership Percentage must be greater than 0.")

    @api.constrains('cnic')
    def validate_cnic(self):
        for rec in self:
            data = self.search([('id', '!=', rec.id), ('cnic', '=', rec.cnic)])
            if data:
                raise ValidationError(_('CNIC must be unique'))
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(rec.cnic) is not None:
                raise ValidationError(_('Please enter complete CNIC Number'))

    # @api.constrains('father_spouse_cnic')
    # def validate_father_cnic(self):
    #     for rec in self:
    #         regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
    #         if rec.father_spouse_cnic and regex.search(rec.father_spouse_cnic) is not None:
    #             raise ValidationError(_('Please enter valid Father/Mother CNIC'))