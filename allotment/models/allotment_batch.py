
from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError


class AllotmentBatch(models.Model):
    _name = 'allotment.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Allotment Batch'

    name = fields.Char(required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))

    date = fields.Date('Batch Date', readonly=True, tracking=True)
    batch_responsibe_id = fields.Many2one('res.users', 'Batched By', readonly=True, tracking=True)

    review_date = fields.Date('Review Date', readonly=True, tracking=True)
    review_responsibe_id = fields.Many2one('res.users', 'Issued By ', readonly=True, tracking=True)

    issued_date = fields.Date('Issued Date', readonly=True, tracking=True)
    issued_responsibe_id = fields.Many2one('res.users', 'Issued By', readonly=True, tracking=True)

    approved_date = fields.Date('Approved Date', readonly=True, tracking=True)
    approved_responsibe_id = fields.Many2one('res.users', 'Approved By', readonly=True, tracking=True)

    printed_date = fields.Date('Printed Date', readonly=True, tracking=True)
    printed_responsibe_id = fields.Many2one('res.users', 'Printed By', readonly=True, tracking=True)

    canceled_date = fields.Date('Cancelled Date', readonly=True, tracking=True)
    canceled_responsibe_id = fields.Many2one('res.users', 'Cancelled By', readonly=True, tracking=True)
    sector_id = fields.Many2one('sector', string='Sector')

    batch_line_ids = fields.One2many('allotment.batch.line', 'allotment_batch_id')
    state = fields.Selection([
        ('draft', 'Submit'),
        ('review', 'Review'),
        ('approve', 'Approved'),
        ('print', 'Printed'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('allotment.request.sequence') or 'New'
        result = super().create(vals_list)
        return result

    def action_set_review(self):
        if self.user_has_groups('allotment.group_allotment_review'):
            if not any(line.check and line.inventory_id for line in self.batch_line_ids):
                raise UserError(_('Please select Unit for allotment.'))
            else:
                for file in self.batch_line_ids:
                    if file.check:
                        file.write({'state': 'review'})
                    else:
                        file.unlink()
            return self.write(
                {'state': 'review', 'review_date': fields.Date.today(), 'review_responsibe_id': self.env.user.id})
        else:
            raise UserError(_('User has no access'))

    def action_set_approve(self):
        if self.user_has_groups('allotment.group_allotment_approve'):
            for file in self.batch_line_ids:
                file.file_id.write({
                    'phase_id': file.inventory_id.phase_id.id,
                    'sector_id': file.inventory_id.sector_id.id,
                    'street_id': file.inventory_id.street_id.id,
                    'inventory_id': file.inventory_id.id,
                    'preference_ids': [(6, 0, file.inventory_id.preference_factor_ids.ids)],
                    'allotment_id': self.id,
                    'allotment_no': self.name
                })
                file.inventory_id.state = 'sold'
                file.write({'state': 'approve'})
                # Call the function to create the allotment application
                self.create_allotment_application(file)
            return self.write(
                {'state': 'approve', 'approved_date': fields.Date.today(), 'approved_responsibe_id': self.env.user.id})
        else:
            raise UserError(_('User has no access'))

    def action_set_cancel(self):
        if self.user_has_groups('allotment.group_allotment_review'):
            for file in self.batch_line_ids:
                file.write({'state': 'issue'})
            return self.write(
                {'state': 'print', 'canceled_date': fields.Date.today(), 'canceled_responsibe_id': self.env.user.id})
        else:
            raise UserError(_('User has no access'))

    def action_set_draft(self):
        if self.user_has_groups('allotment.group_allotment_print'):
            for file in self.batch_line_ids:
                file.write({'state': 'issue'})
            return self.write({'state': 'issue'})
        else:
            raise UserError(_('User has no access'))

    def create_allotment_application(self, file):
        # Search for the relevant file charges schedule based on society and phase
        file_charges_schedule = self.env['file.charges.schedule'].search([
            ('society_id', '=', file.society_id.id),
            ('phase_id', '=', file.phase_id.id),
            ('applicable_on', '=', 'allotment'),
            ('date_from', '<=', fields.Date.today()),
            ('date_to', '>=', fields.Date.today())
        ], limit=1)

        if not file_charges_schedule:
            message = _('No applicable File Charges Schedule found for the selected society and phase.')
            file.allotment_batch_id.message_post(body=message)
        # Check for required taxes, documents, and other charges
        required_taxes_lines = file_charges_schedule.required_taxes_line_ids.filtered(lambda l:
                                                                                      l.category_id == file.file_id.category_id and
                                                                                      l.unit_category_type_ids & file.file_id.unit_category_type_id
                                                                                      )
        required_documents_lines = file_charges_schedule.required_documents_line_ids.filtered(lambda l:
                                                                                              l.category_id == file.file_id.category_id and
                                                                                              l.unit_category_type_ids & file.file_id.unit_category_type_id
                                                                                              )
        other_charges_lines = file_charges_schedule.other_charges_line_ids.filtered(lambda l:
                                                                                    l.category_id == file.file_id.category_id and
                                                                                    l.unit_category_type_ids & file.file_id.unit_category_type_id
                                                                                    )

        if not (required_taxes_lines or required_documents_lines or other_charges_lines):
            # Log not found message
            message = _('No matching File Charges Schedule found for File %s. Allotment Application not created.') % (file.file_id.name)
            file.file_id.message_post(body=message)
        else:

            # Create the allotment application
            allotment_application = self.env['file.allotment.application'].create({
                'file_id': file.file_id.id,
                'membership_id': file.file_id.membership_id.id,
            })

            # Create required documents lines
            document_lines = []
            for document_line in required_documents_lines:
                document_lines.append((0, 0, {'name': document_line.name}))
            self.env['required.documents'].create({
                'name': f"{file.file_id.name} - Required Documents",
                'allotment_application_id': allotment_application.id,
                'required_documents_line_ids': document_lines
            })
            # Create required taxes lines
            tax_lines = []
            for tax_line in required_taxes_lines:
                tax_lines.append((0, 0, {
                    'product_id': tax_line.product_id.id,
                    'rate': tax_line.rate
                }))
            # Create other charges lines
            other_charges = []
            for charge_line in other_charges_lines:
                other_charges.append((0, 0, {
                    'product_id': charge_line.product_id.id,
                    'amount': charge_line.amount,
                }))
            self.env['required.taxes'].create({
                'allotment_application_id': allotment_application.id,
                'membership_id': file.file_id.membership_id.id,
                'allotment_required_tax_ids': tax_lines,
                'other_charges_ids': other_charges,
            })
            # Log success message
            message = _('Allotment Application created successfully for File %s with Allotment Application No. %s') % (file.file_id.name,
                                                                                                                     allotment_application.name)
            file.file_id.message_post(body=message)


class AllotmentLine(models.Model):
    _name = 'allotment.batch.line'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Allotment Batch Line'

    allotment_batch_id = fields.Many2one('allotment.batch')
    check = fields.Boolean(default=False, string='Select')
    file_id = fields.Many2one('file', string='File No')
    membership_id = fields.Many2one('res.member', string='Member No',
                                    related='file_id.membership_id', readonly=True)
    tracking_no = fields.Char(string='Tracking ID', related='file_id.tracking_id', readonly=True)
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", related='file_id.society_id',
                                 readonly=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]", related='file_id.phase_id',
                               readonly=True)
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product', readonly=True)
    category_id = fields.Many2one('plot.category', string='Category', related='file_id.category_id', readonly=True)
    preference_ids = fields.Many2many('preference', readonly=True)
    sector_id = fields.Many2one('sector', related='inventory_id.sector_id', string='Sector', store=True, readonly=False)
    street_id = fields.Many2one('street', related='inventory_id.street_id', string='Street', store=True, readonly=False)
    inventory_id = fields.Many2one('plot.inventory',  string='File Unit')
    size_id = fields.Many2one('unit.size', 'Size', related="inventory_id.size_id")
    unit_number = fields.Char(related='inventory_id.name', readonly=True)

    state = fields.Selection([
        ('draft', 'Submit'),
        ('review', 'Review'),
        ('approve', 'Approved'),
        ('print', 'Printed'),
        ('issued', 'Issued'),
        ('cancel', 'Cancel')
    ], default='draft')

    @api.onchange('phase_id', 'sector_id', 'street_id', 'preference_ids')
    def _inventory_domain(self):
        return {'domain': {
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'street_id': [('sector_id', '=', self.sector_id.id)],
            'inventory_id': [('street_id', '=', self.street_id.id)],
        }
        }

    @api.onchange('preference_ids')
    def onchange_preference_ids(self):
        if self.preference_ids:
            return {'domain': {
                'inventory_id': [('preference_factor_ids', 'in', self.preference_ids.ids)],
            }}
