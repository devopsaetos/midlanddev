# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class CancellationDetail(models.Model):
    _name = 'cancellation.detail'
    _description = "Cancellation Detail"

    name =fields.Char('Cancel')
    convert = fields.Char()
    date = fields.Date()
    remarks = fields.Text()

    file_id = fields.Many2one('file')