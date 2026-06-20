# -*- coding: utf-8 -*-

from odoo import models, fields, api

# class FollowUP(models.Model):
# 	# _name = 'followup'
# 	_inherit = 'res.partner'
# 	_inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin','ir.branch.company.mixin']
# 	_description = "Follow UP"
# 	sale_person = fields.Many2one('res.partner')
# 	zero_to_thirty = fields.Integer('0-30')
# 	thirty_to_sixty = fields.Integer('30-60')
# 	sixty_to_ninty = fields.Integer('60-90')