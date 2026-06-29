from odoo import api, fields, models, _

from odoo.exceptions import UserError


class PrintDocuments(models.Model):
    _name = 'print.documents'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Document Printing'

    name = fields.Char('Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    document_type = fields.Selection([('file', 'File'), ('allotment', 'Allotment')], default="file", string="Document Type")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    file_ids = fields.Many2many('file', string="Files")
    investor_id = fields.Many2one('res.investor', string="Investor")
    investment_id = fields.Many2one('investment', string="Investment", domain=[('state', 'not in', ['draft', 'cancel'])])
    category_id = fields.Many2one('plot.category', string="Category")
    sector_id = fields.Many2one('sector', string="Sector")
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    printing_line_ids = fields.One2many('print.documents.line', 'print_document_id')
    state = fields.Selection(selection=[('draft', 'Draft'), ('closed', 'Closed'), ], string='Status', required=True,
                             readonly=True, copy=False, tracking=True,
                             default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('printing.request.sequence') or _('New')
        new_record = super().create(vals_list)
        return new_record

    def close(self):
        print_queues = self.printing_line_ids.mapped('print_queue_id')
        for queue in print_queues:
            queue.state = 'print'
        file_ids = self.printing_line_ids.filtered(lambda l: l.select == True).mapped('file_id.investor_file.id')
        if file_ids:
            investor_files = self.env['investor.file'].search([('id', 'in', file_ids)])
            if investor_files:
                for line in investor_files:
                    line.state = 'file_printed'
                    line.issuance_request_id.state = 'file_printed'
        self.state = 'closed'

    # Function for Only Printing Membership Form
    def print_files(self):
        for rec in self:
            # file_ids = rec.printing_line_ids.filtered(lambda l: l.select == True and l.file == True).mapped('file_id.id')
            # lines = rec.printing_line_ids.filtered(lambda l: l.select == True and l.file == True)
            # file_ids = []
            # if lines:
            #     for line in lines:
            #         if line.print_queue_id.state == 'draft':
            #             file_ids.append(line.file_id.id)
            #             line.print_queue_id.state = 'print'
            files = rec.printing_line_ids.filtered(lambda l: l.select == True and l.file == True).mapped('file_id')
            file_ids = []
            if files:
                for file in files:
                    # confirmation_paid = file.installment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation_amount' and l.payment_status == 'paid')
                    # if confirmation_paid:
                    membership_form_print_record = file.allotment_detail_ids.filtered(lambda l: l.transaction_type == 'membership')
                    if not membership_form_print_record:
                        file_ids.append(file.id)
            if file_ids:
                for file in file_ids:
                    self.env['allotment.details'].create({
                        'printing_request_id': rec.id,
                        'print_date': fields.Date.today(),
                        'transaction_type': 'membership',
                        'print_by': self.env.user.id,
                        'file_id': file
                    })
                report = self.env.ref('member_file_report.member_file_action').report_action(file_ids)
                return report
            else:
                raise UserError(_('There are no Membership Forms to print'))

    def print_installment_plans(self):
        for rec in self:
            files = rec.printing_line_ids.filtered(lambda l: l.select == True and l.ledger == True).mapped('file_id')
            file_ids = []
            if files:
                for file in files:
                    installment_plan_print_record = file.allotment_detail_ids.filtered(lambda l: l.transaction_type == 'installment_plan')
                    if not installment_plan_print_record:
                        file_ids.append(file.id)
            if file_ids:
                for file in file_ids:
                    self.env['allotment.details'].create({
                        'printing_request_id': rec.id,
                        'print_date': fields.Date.today(),
                        'transaction_type': 'installment_plan',
                        'print_by': self.env.user.id,
                        'file_id': file
                    })
                report = self.env.ref('installment_plan_report.installment_plan_action').report_action(file_ids)
                return report
            else:
                raise UserError(_('There are no Installment Plans to print'))

    def print_greeting_letters(self):
        for rec in self:
            files = rec.printing_line_ids.filtered(lambda l: l.select == True and l.greeting_letter == True).mapped(
                'file_id')
            file_ids = []
            if files:
                for file in files:
                    greeting_letter_print_record = file.allotment_detail_ids.filtered(lambda l: l.transaction_type == 'greeting_letter')
                    if not greeting_letter_print_record:
                        file_ids.append(file.id)
            if file_ids:
                for file in file_ids:
                    self.env['allotment.details'].create({
                        'printing_request_id': rec.id,
                        'print_date': fields.Date.today(),
                        'transaction_type': 'greeting_letter',
                        'print_by': self.env.user.id,
                        'file_id': file
                    })
                # report = self.env.ref('real_estate.greeting_letter_action').report_action(file_ids)
                report = self.env.ref('greeting_letter_report.greeting_letter_report_action').report_action(file_ids)
                return report
            else:
                raise UserError(_('There are no Greeting Letters to print'))

    def print_receipts(self):
        for rec in self:
            files = rec.printing_line_ids.filtered(lambda l: l.select == True and l.receipt == True).mapped(
                'file_id')
            file_ids = []
            if files:
                for file in files:
                    booking_receipt_print_record = file.allotment_detail_ids.filtered(lambda l: l.transaction_type == 'booking_receipt')
                    if not booking_receipt_print_record:
                        file_ids.append(file.id)
            if file_ids:
                for file in file_ids:
                    self.env['allotment.details'].create({
                        'printing_request_id': rec.id,
                        'print_date': fields.Date.today(),
                        'transaction_type': 'booking_receipt',
                        'print_by': self.env.user.id,
                        'file_id': file
                    })
                report = self.env.ref('file_receipt_report.action_file_receipt_report').report_action(file_ids)
                return report
            else:
                raise UserError(_('There are no Receipts to print'))

    def print_confirmation_receipts(self):
        for rec in self:
            files = rec.printing_line_ids.filtered(lambda l: l.select == True and l.confirmation_receipt == True).mapped('file_id')
            file_ids = []
            if files:
                for file in files:
                    confirmation_receipt_print_record = file.allotment_detail_ids.filtered(lambda l: l.transaction_type == 'confirmation_receipt')
                    if not confirmation_receipt_print_record:
                        file_ids.append(file.id)
            if file_ids:
                # for file in file_ids:
                #     self.env['allotment.details'].create({
                #         'printing_request_id': rec.id,
                #         'print_date': fields.Date.today(),
                #         'transaction_type': 'confirmation_receipt',
                #         'print_by': self.env.user.id,
                #         'file_id': file
                #     })
                payment_ids = []
                issued_files = self.env['file'].search([('id', 'in', file_ids)])
                for f in issued_files:
                    conf_line = f.installment_plan_ids.filtered(lambda l: l.installment_type == 'confirmation_amount')
                    if conf_line:
                        payment = self.env['multi.invoice.payment'].search([('invoice_id', '=', conf_line.invoice_id.id)], order='id desc')
                        if payment:
                            if len(payment) > 1:
                                payment = payment[0]
                            payment_ids.append(payment.payment_id.id)
                            self.env['allotment.details'].create({
                                'printing_request_id': rec.id,
                                'print_date': fields.Date.today(),
                                'transaction_type': 'confirmation_receipt',
                                'print_by': self.env.user.id,
                                'file_id': f.id
                            })
                if payment_ids:
                    report = self.env.ref('axiom_payment_report.action_confirmation_payment_receipt_report_ncp').report_action(payment_ids)
                    return report
            else:
                raise UserError(_('There are no Confirmation Receipts to print'))


class PrintDocumentsLine(models.Model):
    _name = 'print.documents.line'
    _description = 'Document Printing Line'

    select = fields.Boolean(default=False, string="Select")
    print_queue_id = fields.Many2one('print.queue')
    file_id = fields.Many2one('file', string="File")
    membership_id = fields.Many2one('res.member', string="Member", related='file_id.membership_id')
    investment_id = fields.Many2one('investment', string="Investment #", related='file_id.investment_id')
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product",
                                            related='file_id.unit_category_type_id')
    category_id = fields.Many2one('plot.category', string="Category", related='file_id.category_id')
    booking_date = fields.Date(related='file_id.booking_date')
    sector_id = fields.Many2one('sector', string="Sector", related='file_id.sector_id')
    greeting_letter = fields.Boolean(string="Greeting Letter")
    file = fields.Boolean(string="Membership Form")
    ledger = fields.Boolean(string="Installment Plan")
    receipt = fields.Boolean(string="Booking Receipt")
    confirmation_receipt = fields.Boolean(string="Confirmation Receipt")
    print_document_id = fields.Many2one('print.documents')
