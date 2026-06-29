from odoo import models, fields, api, _


class PrintDocumentsWizard(models.TransientModel):
    _name = 'print.documents.search'
    _description = 'Document Printing'

    document_type = fields.Selection([('file', 'File'), ('allotment', 'Allotment')], default="file",
                                     string="Document Type")
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    file_ids = fields.Many2many('file', string="Files", domain=[('file_status', '=', 'approve')])
    investor_id = fields.Many2one('res.investor', string="Investor")
    investment_id = fields.Many2one('investment', string="Investment", domain=[('state', 'not in', ['draft', 'cancel'])])
    category_id = fields.Many2one('plot.category', string="Category")
    sector_id = fields.Many2one('sector', string="Sector")
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    greeting_letter = fields.Boolean(default=False, string="Greeting Letter")
    file = fields.Boolean(default=False, string="Membership Form")
    ledger = fields.Boolean(default=False, string="Installment Plan")
    receipt = fields.Boolean(default=False, string="Booking Receipt")
    confirmation_receipt = fields.Boolean(default=False, string="Confirmation Receipt")
    search_line_ids = fields.One2many('print.documents.search.line', 'print_search_id')

    @api.onchange('investor_id')
    def change_domain_for_investor(self):
        for rec in self:
            if rec.investor_id:
                return {
                    'domain': {
                        'file_ids': [('investor_id', '=', rec.investor_id.id), ('file_status', '=', 'approve')],
                        'investment_id': [('partner_id', '=', rec.investor_id.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'file_ids': [('id', '=', 0)],
                        'investment_id': [('id', '=', 0)]
                    }
                }

    def search_records(self):
        for rec in self:
            rec.search_line_ids.unlink()
            domain = []
            if rec.date_from:
                domain.append(('booking_date', '>=', rec.date_from))
            if rec.date_to:
                domain.append(('booking_date', '<=', rec.date_to))
            if rec.file_ids:
                domain.append(('id', 'in', rec.file_ids.ids))
            if rec.investor_id:
                domain.append(('investor_id', '=', rec.investor_id.id))
            if rec.investment_id:
                domain.append(('investment_id', '=', rec.investment_id.id))
            if rec.category_id:
                domain.append(('category_id', '=', rec.category_id.id))
            if rec.sector_id:
                domain.append(('sector_id', '=', rec.sector_id.id))
            if rec.unit_category_type_id:
                domain.append(('unit_category_type_id', '=', rec.unit_category_type_id.id))
            domain.append(('file_status', '=', 'approve'))
            files = self.env['file'].search(domain)
            if files:
                for file in files:
                    greeting_letter = file.allotment_detail_ids.filtered(lambda x: x.transaction_type == 'greeting_letter')
                    membership_form = file.allotment_detail_ids.filtered(lambda x: x.transaction_type == 'membership')
                    installment_plan = file.allotment_detail_ids.filtered(lambda x: x.transaction_type == 'installment_plan')
                    booking_receipt = file.allotment_detail_ids.filtered(lambda x: x.transaction_type == 'booking_receipt')
                    confirmation_receipt = file.allotment_detail_ids.filtered(lambda x: x.transaction_type == 'confirmation_receipt')
                    print_queue = self.env['print.queue'].search([('document_type', '=', 'file'), ('files_ids', 'in', file.id)])
                    # print_queues = self.env['print.queue'].search([('document_type', '=', 'file'), ('files_ids', 'in', files.ids), ('state', '=', 'draft')])
                    # if print_queues:
                    #     for lines in print_queues:
                    # self.env['print.documents.search.line'].create({
                    print_gl = rec.greeting_letter
                    print_membership = rec.file
                    print_ledger = rec.ledger
                    print_booking_receipt = rec.receipt
                    print_confirmation_receipt = rec.confirmation_receipt
                    if print_gl and not greeting_letter:
                        print_gl = True
                    else:
                        print_gl = False
                    if print_membership and not membership_form:
                        print_membership = True
                    else:
                        print_membership = False
                    if print_ledger and not installment_plan:
                        print_ledger = True
                    else:
                        print_ledger = False
                    if print_booking_receipt and not booking_receipt:
                        print_booking_receipt = True
                    else:
                        print_booking_receipt = False
                    if print_confirmation_receipt and not confirmation_receipt:
                        print_confirmation_receipt = True
                    else:
                        print_confirmation_receipt = False
                    if print_gl or print_membership or print_ledger or print_booking_receipt or print_confirmation_receipt:
                        rec.search_line_ids = [(0, 0, {
                            'print_queue_id': print_queue.id if print_queue else None,
                            'file_id': file.id if file else None,
                            'greeting_letter': print_gl,
                            'file': print_membership,
                            'ledger': print_ledger,
                            'receipt': print_booking_receipt,
                            'confirmation_receipt': print_confirmation_receipt,
                            'print_search_id': rec.id
                        })]
            return {
                'context': self.env.context,
                'view_mode': 'form',
                # 'view_id': view.id,
                'res_model': self._name,
                'res_id': rec.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def create_print_request(self):
        for rec in self:
            if rec.search_line_ids:
                line_ids = rec.search_line_ids.filtered(lambda l: l.select == True)
                print_lines = []
                for lines in line_ids:
                    print_lines.append((0, 0, {
                        'select': True,
                        'print_queue_id': lines.print_queue_id.id,
                        'file_id': lines.file_id.id,
                        'file': lines.file,
                        'ledger': lines.ledger,
                        'receipt': lines.receipt,
                        'greeting_letter': lines.greeting_letter,
                        'confirmation_receipt': lines.confirmation_receipt,
                    }))
                print_request = self.env['print.documents'].create({
                    'document_type': rec.document_type,
                    'date_from': rec.date_from,
                    'date_to': rec.date_to,
                    'file_ids': rec.file_ids.ids,
                    'investor_id': rec.investor_id.id,
                    'investment_id': rec.investment_id.id,
                    'category_id': rec.category_id.id,
                    'sector_id': rec.sector_id.id,
                    'unit_category_type_id': rec.unit_category_type_id.id,
                    'printing_line_ids': print_lines
                })
                if print_request:
                    return {
                        'name': _('Printing Request'),
                        'res_model': 'print.documents',
                        'type': 'ir.actions.act_window',
                        'context': {},
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': print_request.id,
                        'domain': [('id', '=', print_request.id)],
                        'target': 'self'
                    }


class PrintDocumentsWizardLine(models.TransientModel):
    _name = 'print.documents.search.line'
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
    greeting_letter = fields.Boolean(default=False, string="Greeting Letter")
    file = fields.Boolean(default=False, string="Membership Form")
    ledger = fields.Boolean(default=False, string="Installation Plan")
    receipt = fields.Boolean(default=False, string="Booking Receipt")
    confirmation_receipt = fields.Boolean(default=False, string="Confirmation Receipt")
    print_search_id = fields.Many2one('print.documents.search')
