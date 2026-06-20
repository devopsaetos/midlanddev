# -*- coding: utf-8 -*-
import base64
import os

from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime
root_path = os.path.dirname(os.path.abspath(__file__))

from xlrd import open_workbook


class ImportData(models.TransientModel):
    _name = "import.data"
    _description = 'Import Data'

    file = fields.Binary(string='Xls file')

    x_action = fields.Selection([
        ('members', 'Members'),
        ('invoices', 'Invoices'),
        ],
        string='Action', required=True)

    def search_record(self,model,key,value):
        if value:
            record = self.env[model].search([(key, '=', value)], limit=1)
            if record:
                return record.id  
            else:
                raise ValidationError("Please create %s First in %s" %(value,model))

    def m2m_records(self,key,value,model):

        return [[6, False, [self.search_record(model, key, rec) for rec in [value]]]]

    def import_members(self):

        member_keys = [
            'name', 'agent_id', 'relation_id', 'relation_name', 'street', 'street2', 'city_id', 'state_id',
            'zip', 'country_id',
            'is_same', 'corespondence_street', 'corespondence_street2', 'corespondence_city', 'corespondence_state_id',
            'corespondence_zip',
            'corespondence_country_id', 'cnic', 'gender', 'passport', 'country_code', 'mobile', 'secondary_phone',
            'phone', 'email']
        #
        # member_keys = [
        #     'name', 'is_member', 'agent_id', 'relation_id', 'relation_name', 'street', 'street2', 'city_id', 'state_id',
        #     'zip', 'country_id',
        #     'is_same', 'corespondence_street', 'corespondence_street2', 'corespondence_city', 'corespondence_state_id',
        #     'corespondence_zip',
        #     'corespondence_country_id', 'cnic', 'gender', 'passport', 'country_code', 'mobile', 'secondary_phone',
        #     'phone', 'email', 'correspondence_mean_id', 'correnponding_option']

        # kin_keys = ['name', 'relation_id', 'relation_name','street', 'street2', 'city_id', 'state_id', 'zip', 'country_id', 
            # 'is_same', 'corespondence_street','corespondence_street2','corespondence_city','corespondence_state_id', 'corespondence_zip',
            # 'corespondence_country_id','gender','relation_with_member', 'country_code', 'mobile', 'secondary_phone', 'phone', 'cnic', 'passport', ]

        sheets = open_workbook(file_contents=base64.b64decode(self.file)).sheets()

        for sheet in sheets:
            for row in range(1,sheet.nrows):
                values = [sheet.cell(row, col).value for col in range(sheet.ncols)]
                member_values = values[:len(member_keys)]
                # kin_values = values[len(member_keys):]
                
                member_data = dict(zip(member_keys, member_values))
                # kin_data = dict(zip(kin_keys, kin_values))
                # print(member_data)
                # print(kin_data)

                member_data['agent_id'] =  self.m2m_records('name',member_data['agent_id'],'res.partner')
                member_data['city_id'] = self.search_record('city', 'name', member_data['city_id'])
                member_data['state_id'] = self.search_record('res.country.state','name', member_data['state_id'])
                member_data['country_id'] = self.search_record('res.country', 'name', member_data['country_id'])
                member_data['corespondence_city'] = self.search_record('city', 'name', member_data['corespondence_city'])
                member_data['corespondence_state_id'] = self.search_record('res.country.state','name', member_data['corespondence_state_id'])
                member_data['corespondence_country_id'] = self.search_record('res.country', 'name', member_data['corespondence_country_id'])
                member_data['country_code'] = self.search_record('res.country.code', 'name', '00'+str(member_data['country_code']).partition('.')[0])
                # member_data['correspondence_mean_id'] =  self.m2m_records('name',member_data['correspondence_mean_id'],'correnpondence.mean')

                # kin_data['city_id'] = self.search_record('city', 'name', kin_data['city_id'])
                # kin_data['state_id'] = self.search_record('res.country.state','name', kin_data['state_id'])
                # kin_data['country_id'] = self.search_record('res.country', 'name', kin_data['country_id'])
                # kin_data['corespondence_city'] = self.search_record('city', 'name', kin_data['corespondence_city'])
                # kin_data['corespondence_state_id'] = self.search_record('res.country.state','name', kin_data['corespondence_state_id'])
                # kin_data['corespondence_country_id'] = self.search_record('res.country', 'name', kin_data['corespondence_country_id'])
                # kin_data['country_code'] = self.search_record('res.country.code', 'name', '00'+str(kin_data['country_code']).partition('.')[0])

                partner = self.env['res.member']
                if not partner.search(['&',('name', '=', member_data['name']),'|',('cnic', '=', member_data['cnic']),('passport', '=', member_data['passport'])]):
                    members = self.env['res.member'].create(member_data)
                    # kin_data['partner_id'] = members.id
                    # kin = self.env['res.member'].create(kin_data)
                    self.env.cr.commit()

    def import_invoices(self):
        wb = open_workbook(file_contents=base64.b64decode(self.file))
        ws = wb.sheets()[0]
        data = {}
        dataline = {}
        for s in wb.sheets():
            for row in range(s.nrows):
                if row > 0:
                    for col in range(s.ncols):
                        if col == 0 and s.cell(row, col).value:
                            data['name'] = s.cell(row, col).value

                        elif col == 1 and s.cell(row, col).value:

                            data['date'] = s.cell(row, col).value
                            recp = self.env['import.invoices'].create(data)

                        elif col == 2 and s.cell(row, col).value:

                            dataline['member_id'] = self.env['res.member'].search([('ref', '=', s.cell(row, col).value.rstrip())]).id
                        elif col == 3 and s.cell(row, col).value:

                            dataline['contract_id'] = self.env['res.contract'].search([('name', '=', s.cell(row, col).value.rstrip())]).id
                        elif col == 4 and s.cell(row, col).value:

                            dataline['ammenities_id'] = self.env['amenity.amenity'].search([('name', '=', s.cell(row, col).value.rstrip())]).id
                        elif col == 5 and s.cell(row, col).value:

                            dataline['meter_number'] = s.cell(row, col).value
                        elif col == 6 and s.cell(row, col).value:

                            dataline['previous_reading'] = s.cell(row, col).value
                        elif col == 7 and s.cell(row, col).value:

                            dataline['new_reading'] = s.cell(row, col).value
                        elif col == 8 and s.cell(row, col).value:

                            dataline['unit_rate'] = s.cell(row, col).value
                        elif col == 9 and s.cell(row, col).value:

                            dataline['amount'] = s.cell(row, col).value
                            dataline['import_invices_id'] = recp.id

                            recp.import_invoice_line.create(dataline)