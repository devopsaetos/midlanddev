from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class MembersCheck(models.TransientModel):
    _name = 'members.check'
    _description = "Check Members"

    member_type = fields.Selection([
        ('person', 'Individual'),
        ('company', 'Company'),
        ('aop', 'AOP')
    ], default='person')
    cnic = fields.Char('CNIC')

    def existing_record(self):
        search = []
        if self.cnic:
            search.append(('cnic', '=', self.cnic))
        else:
            raise ValidationError(_("Please Enter CNIC."))

        if search:
            partner = self.env['res.member'].search(search)
            if not partner:
                raise ValidationError(_("This member is not yet created. So, you can not see his details."))

            return {
                'name': 'Member Form',
                'view_mode': 'form',
                'res_model': 'res.member',
                'view_id': self.env.ref('real_estate.view_partner_form').id,
                'domain': [('cnic','=',self.cnic)],
                'res_id': partner.id,
                'context': {},
                'type': 'ir.actions.act_window',
                # 'target': 'new'

            }

    def new_record(self):
        obj = self._context.get('current_view')
        search = []
        partner = self.env['res.member']
        if self.cnic:
            search.append(('cnic', '=', self.cnic))
        else:
            raise ValidationError(_("Please Enter CNIC."))

        if search:
            if partner.search(search):
                raise ValidationError(_("This member already exists. So, you can not recreate that."))

        #     else:
        #         partner_id = self.env['res.partner'].create(
        #             {'cnic': self.cnic or False})
        if obj=='building':
            form_view = (self.env.ref('land_development.view_partner_form').id, 'form')
            return {
                'name': 'Member Form',
                'view_mode': 'form',
                'views': [form_view],
                'res_model': 'res.member',
                'view_id': self.env.ref('land_development.view_partner_form').id,
                'context': {'default_project_type': 'skyscraper',
                            'default_cnic': self.cnic,
                            'default_company_type': self.member_type},
                'type': 'ir.actions.act_window',
                }
        if obj=='realestate':
            form_view = (self.env.ref('real_estate.view_partner_form').id, 'form')
            return {
                'name': 'Member Form',
                'view_mode': 'form',
                'views': [form_view],
                'res_model': 'res.member',
                'view_id': self.env.ref('real_estate.view_partner_form').id,
                'context': {'default_project_type': 'housing_society',
                            'default_cnic': self.cnic,
                            'default_company_type': self.member_type},
                'type': 'ir.actions.act_window',
                }