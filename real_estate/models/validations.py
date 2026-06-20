from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re


class Partner(models.Model):
    _inherit = 'res.member'

    @api.onchange('vat')
    def check_special_char_vat(self):
        if self.vat:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]')
            if regex.search(self.vat) is not None:
                raise ValidationError(_('Only Numbers Are Allowed'))

    @api.constrains('vat')
    def check_constrain_special_char_vat(self):
        if self.vat:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]')
            if regex.search(self.vat) is not None:
                raise ValidationError(_('Only Numbers Are Allowed'))

    @api.onchange('city')
    def check_special_char_city(self):
        if self.city:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[0-9]')
            if regex.search(self.city) is not None:
                raise ValidationError(_('Special Characters And Numbers Are Not Allowed in City'))

    @api.constrains('city')
    def check_constrain_special_char_city(self):
        if self.city:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[0-9]')
            if regex.search(self.city) is not None:
                raise ValidationError(_('Special Characters And Numbers Are Not Allowed in City'))

    @api.onchange('zip')
    def check_special_char_zip(self):
        if self.zip:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.zip) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Zip'))

    @api.constrains('zip')
    def check_constrain_special_char_zip(self):
        if self.zip:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.zip) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Zip'))

    @api.onchange('function')
    def check_special_char_function(self):
        if self.function:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[0-9]')
            if regex.search(self.function) is not None:
                raise ValidationError(_('Special Characters And Numbers Are Not Allowed in Job Position'))

    @api.constrains('function')
    def check_constrain_special_char_function(self):
        if self.function:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[0-9]')
            if regex.search(self.function) is not None:
                raise ValidationError(_('Special Characters And Numbers Are Not Allowed in Job Position'))

    @api.onchange('phone')
    def check_special_char_phone(self):
        if self.phone:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.phone) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Phone'))

    @api.constrains('phone')
    def check_constrain_special_char_phone(self):
        if self.phone:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.phone) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Phone'))

    # @api.onchange('mobile')
    # def check_special_char_mobile(self):
    #     if self.mobile:
    #         regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
    #         if regex.search(self.mobile) is not None:
    #             raise ValidationError(_('Only Numbers Are Allowed in Mobile'))

    @api.constrains('mobile')
    def check_constrain_special_char_mobile(self):
        if self.mobile:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.mobile) is not None:
                raise ValidationError(_('Please enter complete mobile number'))

    # @api.onchange('email')
    # def check_valid_email(self):
    #     if self.email:
    #         regex = re.compile('^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$')
    #         if not (re.search(regex, self.email)):
    #             raise ValidationError(_('Please Enter Valid Email'))

    # @api.constrains('email')
    # def check_constrain_valid_email(self):
    #     if self.email:
    #         regex = re.compile('^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$')
    #         if not (re.search(regex, self.email)):
    #             raise ValidationError(_('Please Enter Valid Email'))


class CountryState(models.Model):
    _inherit = 'res.country.state'

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('name', False):
                val['name'] = val['name'].capitalize()
        return super(CountryState, self).create(vals_list)

    @api.constrains('name', 'code')
    def duplicate_data(self):
        for rec in self:
            data = self.search(['&', '|', ('name', '=', rec.name), ('code', '=', rec.code), ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('State Name Or State Code Is Already Present'))


class ResCity(models.Model):
    _inherit = 'city'

    @api.onchange('zip')
    def check_special_char_zip(self):
        if self.zip:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.zip) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Zip'))

    @api.constrains('zip')
    def check_constrain_special_char_zip(self):
        if self.zip:
            regex = re.compile('[@_!#$%^&*()<>?/\|}{~:;.=""]|[a-z]')
            if regex.search(self.zip) is not None:
                raise ValidationError(_('Only Numbers Are Allowed in Zip'))

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('name', False):
                val['name'] = val['name'].capitalize()
        return super(ResCity, self).create(vals_list)

    @api.constrains('name')
    def check_duplicate_data(self):
        for rec in self:
            data = self.search(['&', '|', ('name', '=', rec.name), ('zip', '=', rec.zip), ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('City Or Zip is Already created'))


class ResAuthority(models.Model):
    _inherit = 'res.authority'

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get('name', False):
                val['name'] = val['name'].capitalize()
        return super(ResAuthority, self).create(vals_list)

    @api.constrains('name', 'code')
    def check_duplicate_data(self):
        for rec in self:
            data = self.search(['&', '|', ('code', '=', rec.code), ('name', '=', rec.name), ('id', '!=', rec.id)])
            if data:
                raise ValidationError(_('Name Or Code Is Already Present'))
