# -*- coding: utf-8 -*-
from odoo import fields, models, api


class Street(models.Model):
    _name = 'street'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Street'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sector_id = fields.Many2one('sector', required=True)
    street_type = fields.Many2one('street.type', required=True)
    company_id = fields.Many2one('res.company', string="Company", tracking=True)
    branch_id = fields.Many2one('res.company', string="Branch", tracking=True)
    plot_inventory_ids = fields.One2many('plot.inventory', 'street_id')

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('code', 'unique (code)', 'Code must be unique!'),
    # ]


class StreetType(models.Model):
    _name = 'street.type'
    _description = 'Street Type'

    name = fields.Char(required=True)
    code = fields.Char(required=True)

    # Odoo 19 ignores _sql_constraints (startup warning) and this constraint does not exist in the
    # database, so it is not enforced. Kept as a note; enabling it (models.Constraint) would start
    # rejecting duplicates, which is a behaviour change.
    # _sql_constraints = [
    #     ('code', 'unique (code)', 'Code must be unique!'),
    # ]

