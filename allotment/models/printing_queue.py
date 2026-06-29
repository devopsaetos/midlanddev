from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError


class PrintQueue(models.Model):
    _name = 'print.queue'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Print Queue'

    name = fields.Char(required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    document_type = fields.Selection([
        ('allotment', 'Allotment'),
        ('file', 'File'),
        ('processing_letter', 'Processing Letter')], tracking=True)
    allotment = fields.Selection([
        ('new', 'New'),
        ('transfer', 'Transfer'),
        ('re_allotment', 'Re-allotment')], tracking=True)
    batch_id = fields.Many2one('allotment.batch', domain="[('state', '=', 'approve')]", tracking=True)
    transaction_ref = fields.Char()
    member_ids = fields.Many2many('res.member', string='Member No')
    files_ids = fields.Many2many('file', string='File')
    sector_id = fields.Many2one('sector', string='Sector')
    transfer_application_id = fields.Many2one('transfer.application')
    line_ids = fields.One2many(comodel_name='print.queue.line', inverse_name='print_queue_id', required=False)
    state = fields.Selection([('draft', 'Draft'), ('print', 'Printed')], string='Status', default='draft', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('allotment.request.sequence') or 'New'
        result = super().create(vals_list)
        return result

    @api.onchange('batch_id')
    def onchange_method_batch_id(self):
        self.line_ids.unlink()
        lines = []
        for rec in self.batch_id.batch_line_ids:
            lines.append((0, 0, {
                'file_id': rec.file_id.id,
                'membership_id': rec.membership_id.id,
                'tracking_no': rec.tracking_no,
                'society_id': rec.society_id.id,
                'phase_id': rec.phase_id.id,
                'unit_category_type_id': rec.unit_category_type_id.id,
                'category_id': rec.category_id.id,
                'sector_id': rec.sector_id.id,
                'street_id': rec.street_id.id,
                'inventory_id': rec.inventory_id.id
            }))
        self.line_ids = lines

    def print_action(self):
        if self.user_has_groups('allotment.group_allotment_print'):
            files = []
            if not any(self.line_ids or self.files_ids) and self.document_type != 'processing_letter':
                raise ValidationError('Please select files to print.')
            if self.document_type == 'allotment' and self.allotment == 'new':
                for file in self.line_ids:
                    file.file_id.write({
                                        'allotment_detail_ids': [(0, 0, {
                                                    'print_date': fields.Date.today(),
                                                    'transaction_type': 'allotment',
                                                    'print_by': self.env.user.id,
                                                })]
                                        })
                    self.env['printing.history'].create({'document_type': self.document_type,
                                                         'file_id': file.file_id.id,
                                                         'print_date': fields.Date.today(),
                                                         'print_by': self.env.user.id
                                                         })
                    files.append(file.file_id.id)
                self.state = 'print'
                self.batch_id.state = 'print'
                return self.env.ref('membership_form.action_allotment_letter2').report_action(files)
            for file in self.files_ids:
                if self.document_type == 'file' and self.allotment == 'transfer':
                    file.write({
                                'allotment_detail_ids': [(0, 0, {
                                'print_date': fields.Date.today(),
                                'transaction_type': 'file_transfer',
                                'print_by': self.env.user.id,
                            })]
                    })
                    self.env['printing.history'].create({'document_type': self.document_type,
                                                         'file_id': file.id,
                                                         'print_date': fields.Date.today(),
                                                         'print_by': self.env.user.id
                                                         })
                    files.append(file.id)
                    self.state = 'print'

                    # Creating Allotment Printing Request
                    self.create({
                        'document_type': 'allotment',
                        'allotment': 'transfer',
                        'transaction_ref': self.name,
                        'member_ids': [(6, 0, self.member_ids.ids)],
                        'files_ids': [(6, 0, self.files_ids.ids)],
                        'line_ids': [(0, 0, {
                            'file_id': file.id,
                            'membership_id': file.membership_id.id,
                            'tracking_no': file.tracking_id,
                            'society_id': file.society_id.id,
                            'phase_id': file.phase_id.id,
                            'unit_category_type_id': file.unit_category_type_id.id,
                            'category_id': file.category_id.id,
                            'sector_id': file.sector_id.id,
                            'street_id': file.street_id.id,
                            'inventory_id': file.inventory_id.id
                        }) for file in self.files_ids]

                    })
                    return self.env.ref('membership_form.membership_form_action').report_action(files)
            if self.document_type == 'processing_letter' and self.allotment == 'transfer':
                transfer = []
                for rec in self.transfer_application_id:
                    rec.file_id.write({
                        'allotment_detail_ids': [(0, 0, {
                            'print_date': fields.Date.today(),
                            'transaction_type': 'processing',
                            'print_by': self.env.user.id,
                        })]
                    })
                    self.env['printing.history'].create({'document_type': self.document_type,
                                                         'file_id': rec.file_id.id,
                                                         'print_date': fields.Date.today(),
                                                         'print_by': self.env.user.id
                                                         })
                    transfer.append(rec.id)
                    self.state = 'print'
                    return self.env.ref('membership_form.processing_form_action').report_action(transfer)
        else:
            raise UserError(_('User has no access'))

    def unlink(self):
        for rec in self:
            if rec.state == 'print':
                raise UserError(_('You cannot delete a record once it is printed.'))
        return super(PrintQueue, self).unlink()


class PrintQueueLine(models.Model):
    _name = 'print.queue.line'
    _description = 'PrintQueueLine'

    print_queue_id = fields.Many2one('print.queue')

    file_id = fields.Many2one('file', string='File No', store=True)
    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    tracking_no = fields.Char(string='Tracking ID', related='file_id.tracking_id', readonly=True)
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id',
                                 readonly=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id',
                               readonly=True)
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product', readonly=True)
    category_id = fields.Many2one('plot.category', string='Plot Category', related='file_id.category_id', readonly=True)
    preference_ids = fields.Many2many('preference', readonly=True)
    sector_id = fields.Many2one('sector', related='file_id.sector_id')
    street_id = fields.Many2one('street', related='file_id.street_id', required=True, string='Street')
    inventory_id = fields.Many2one('plot.inventory', required=True, string='File Unit')
