from odoo import models, fields, api, _


class DiscountPolicy(models.Model):
    _name = 'discount.policy'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Discount Policy'

    name = fields.Char(string="Name", tracking=True)
    date_from = fields.Date(string="From Date", tracking=True)
    date_to = fields.Date(string="Till Date", tracking=True)
    percentage = fields.Float(string="Percentage %", tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, string="Company", tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
    ], default='draft', tracking=True)

    def draft(self):
        self.state = 'draft'

    def active(self):
        self.state = 'active'
