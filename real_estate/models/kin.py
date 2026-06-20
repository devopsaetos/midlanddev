# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Kin(models.Model):
    _name = 'res.kin'
    _description = "Kin"

    name = fields.Char('Name')
    member_name = fields.Char()
    cnic = fields.Char('CNIC')
    cnic_front = fields.Binary(string='Cinc Front')
    cnic_back = fields.Binary(string='Cinc Back')
    mobile = fields.Char('Mobile')
    mobile_code = fields.Many2one('res.country.code', 'Code')
    relation_with_member = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('wife', 'Wife'),
        ('husband', 'Husband'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('other', 'Other'),
    ])
    relation_name = fields.Char()

    start_date = fields.Date()
    end_date = fields.Date()
    member_id = fields.Many2one('res.member', ondelete='cascade')
    file_id = fields.Many2one('file')
    kin_request_id = fields.Many2one('res.kin.request')