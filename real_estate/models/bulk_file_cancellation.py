# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class BulkFileCancellation(models.Model):
    _name = 'bulk.file.cancellation'
    _description = 'Bulk File Cancellation'

    name = fields.Char(required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New'))
    society_id = fields.Many2one('society', string='Society', required=True, domain="[('is_society', '=', True)]")
    phase_id = fields.Many2one('society', string='Phase', required=True, domain="[('is_society', '!=', True)]")
    sector_id = fields.Many2one('sector', string='Sector', required=True)
    date = fields.Date(string='Date', required=True)
    over_due_installments = fields.Integer(string='Over Due Installments', required=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('lock', 'Lock'),
                              ('approve', 'Approve')], default='draft')
    bulk_file_cancellation_line_ids = fields.One2many('bulk.file.cancellation.line',
                                                      'bulk_file_cancellation_id')

    def lock(self):
        if not self.bulk_file_cancellation_line_ids:
            raise ValidationError('Please search records first.')
        for rec in self:
            rec.state = 'lock'

    def approve(self):
        for rec in self.bulk_file_cancellation_line_ids:
            rec.file_id.state = 'cancel'
            rec.file_id.inventory_id.state = 'avalible_for_sale'
        self.state = 'approve'

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _phase_domain(self):
        return {'domain': {
            'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id)],
        }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('bulk.file.cancellation.sequence') or _('New')
        result = super(BulkFileCancellation, self).create(vals_list)
        return result

    def search_file_records(self):
        self.bulk_file_cancellation_line_ids.unlink()
        files = self.env['file'].search([('state', '=', 'available'), ('payment_states', '=', 'open'),
                                         ('society_id', '=', self.society_id.id),
                                         ('phase_id', '=', self.phase_id.id),
                                         ('sector_id', '=', self.sector_id.id)])
        overdue_file = []
        for rec in files:
            plans = []
            if rec.installment_plan_ids:
                for plan in rec.installment_plan_ids.filtered(lambda s: s.invoice_created == True and s.payment_status == 'not_paid'  and s.date <= self.date):
                    plans.append(plan.id)
                plan_length = len(plans)
                if plan_length >= self.over_due_installments:
                    overdue_file.append(rec.id)
                    print(overdue_file)

        new_data = self.env['file'].browse(overdue_file)
        for file in new_data:
            self.bulk_file_cancellation_line_ids = [(0, 0, {'member_id': file.membership_id.id,
                                                            'membership_name': file.membership_name,
                                                            'file_id': file.id,
                                                            'category_id': file.category_id.id,
                                                            'size_id': file.size_id.id,
                                                            'inventory_id': file.inventory_id.id})]

    def unlink(self):
        for rec in self:
            if rec.state == 'lock' or rec.state == 'approve':
                raise UserError(_('You cannot delete a record once it is locked or approved!'))

        return super(BulkFileCancellation, self).unlink()


class BulkFileCancellationLine(models.Model):
    _name = 'bulk.file.cancellation.line'
    _description = 'Bulk File Cancellation File Line'

    bulk_file_cancellation_id = fields.Many2one('bulk.file.cancellation')
    member_id = fields.Many2one('res.member', string='Member No', readonly=False)
    file_id = fields.Many2one('file', string='File No')
    membership_name = fields.Char(string='Member Name')
    category_id = fields.Many2one('plot.category', string='Category')
    size_id = fields.Many2one('unit.size', string='Size')
    inventory_id = fields.Many2one('plot.inventory', string='Unit No')
    file_state = fields.Selection([('available', 'Available'),
                                   ('cancel', 'Cancel'),
                                   ('inprocess', 'Inprocess'),
                                   ('refund', 'Refund'),
                                   ('merged', 'Merged')], related='file_id.state',
                                  stroe=True, readonly=True)
