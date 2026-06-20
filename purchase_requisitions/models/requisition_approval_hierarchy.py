# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RequisitionApprovalHierarchy(models.Model):
    _name = "requisition.approval.hierarchy"
    _description = "Requisition Approval Hierarchy"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'sequence'

    department_id = fields.Many2one('hr.department')
    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    approval_base = fields.Selection([
        ('position', 'Position'),
        ('role', 'Role'),
        ('user', 'User'),
    ])
    approval_hierarchy_line_ids = fields.One2many('approval.hierarchy.line', 'approval_hierarchy_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['sequence'] = self.env['ir.sequence'].next_by_code(
                'requisition.approval.hierarchy') or '/'
        records = super(RequisitionApprovalHierarchy, self).create(vals_list)
        for res in records:
            if not res.approval_hierarchy_line_ids.filtered(lambda hl: hl.user_id):
                raise UserError(_("Please make approval hierarchy lines otherwise the record will be discarded."))
        return records

    @api.onchange('date_from', 'date_to')
    def date_validations(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise UserError(_("Date from can't be greater than date to."))


class ApprovalHierarchyLine(models.Model):
    _name = "approval.hierarchy.line"
    _description = 'Approval Hierarchy Line'

    approval_hierarchy_id = fields.Many2one('requisition.approval.hierarchy', ondelete='cascade')
    user_id = fields.Many2one('res.users', required=True)
    min_limit = fields.Float('Minimum Limit', default=0.0, required=True)
    max_limit = fields.Float('Maximum Limit', default=0.0, required=True)
    manager_id = fields.Many2one('res.users', related="user_id.user_manager")

    @api.constrains('min_limit', 'max_limit')
    def limits_checks(self):
        for line in self:
            if line.min_limit <= 0:
                raise UserError(_("Minimum limit couldn't be less than or equal to zero."))
            if line.max_limit <= 0:
                raise UserError(_("Maximum limit couldn't be less than or equal to zero."))
            if line.min_limit == line.max_limit:
                raise UserError(_("Minimum and Maximum limits can't be the same."))
            if line.max_limit < line.min_limit:
                raise UserError(_("Maximum limit can't be less than minimum limit."))

    @api.onchange('min_limit', 'max_limit')
    def _onchange_limits(self):
        if self.min_limit < 0:
            raise UserError(_("Minimum limit couldn't be less than zero."))
        if self.min_limit and self.max_limit:
            if self.min_limit == self.max_limit:
                raise UserError(_("Minimum and Maximum limits can't be the same."))
            if self.max_limit < self.min_limit:
                raise UserError(_("Maximum limit can't be less than minimum limit."))

    _sql_constraints = [
        ('uniq_user', 'unique (approval_hierarchy_id,user_id)', 'User Must be Unique!')
    ]

    @api.onchange('user_id')
    def user_validation(self):
        if self.user_id:
            existing = self.env['approval.hierarchy.line'].search([
                ('user_id', '=', self.user_id.id),
                ('approval_hierarchy_id', '!=', self.approval_hierarchy_id.id or False),
            ])
            if existing:
                raise UserError(_("Credentials for this user already provided."))