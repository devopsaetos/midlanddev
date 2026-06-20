# -*- coding: utf-8 -*-

# from odoo import models, fields, api
#
# class CorrespondenceMean(models.Model):
#     _name = 'correnpondence.mean'
#     _description = "Correspondence Mean"
#
#     name=fields.Char()
#
#
# class Correspondence(models.Model):
#     _name = 'correnpondence'
#     _description = "Correspondence"
#
#     name = fields.Selection([
#         ('reminder' , 'Reminder')
#     ])
#
#     membership_id = fields.Many2one('res.partner', 'Member', domain="[('is_member', '=', 1)]")
#
#     file_id = fields.Many2one('file','File Ref:')
#
#     month = fields.Many2one('fiscal.month')
#
#     letter = fields.Many2many('ir.attachment', 'correspondence_ir_attachments_rel',
#         'correspondence_id', 'attachment_id', 'Letter')
#
#     status = fields.Selection([
#         ('sent' , 'Sent')
#     ])