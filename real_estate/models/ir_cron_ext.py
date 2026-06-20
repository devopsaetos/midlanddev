# -*- coding: utf-8 -*-

from odoo import models, fields, api

class IrCron(models.Model):

    _inherit = "ir.cron"
    _description = 'Scheduled Actions Ext'

    till_date = fields.Date()