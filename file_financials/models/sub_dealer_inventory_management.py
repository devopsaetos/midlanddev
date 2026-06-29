from odoo import api, fields, models, _

from odoo.exceptions import UserError
from datetime import datetime, date


class SubDealerInventoryManagement(models.Model):
    _name = 'subdealer.inventory.management'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Sub Dealer Inventory Management'

    name = fields.Char('Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company", tracking=True)
    date = fields.Date(string="Date", tracking=True, default=lambda self: fields.Datetime.today())
    transaction_type = fields.Selection([('d_2_s', 'Dealer to Sub Dealer'),
                                         ('s_2_d', 'Sub-Dealer to Main Dealer')],
                                        string="Transaction Type", default="d_2_s", tracking=True)
    request_platform = fields.Selection([('system', 'System'), ('portal', 'Portal')], string="Request Platform", tracking=True)
    investor_id = fields.Many2one('res.investor', string="Sub Dealer", domain=[('investor_type', '=', 'sub_dealer')], tracking=True)
    main_investor_id = fields.Many2one('res.investor', string="Main Investor", tracking=True)
    investment_id = fields.Many2one('investment', string="Investment", tracking=True)
    category_ids = fields.Many2many('plot.category', string="Category", tracking=True)
    unit_category_type_ids = fields.Many2many('unit.category.type', string="Product", tracking=True)
    investor_file_ids = fields.Many2many('investor.file', string="Open Files", tracking=True)
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('in_approval', 'In Approval'), ('approved', 'Approved'), ('processed', 'Processed'), ('cancel', 'Cancelled')],
        string='Status',
        required=True,
        readonly=True, copy=False, tracking=True,
        default='draft')

    @api.onchange('name', 'company_id', 'transaction_type', 'investor_id', 'main_investor_id', 'investment_id', 'category_ids', 'unit_category_type_ids')
    def _investor_files_domain(self):
        for rec in self:
            domain = [('state', '=', 'open')]
            if rec.company_id:
                domain.append(('society_id.company_id.id', '=', rec.company_id.id))
            if rec.transaction_type == 'd_2_s' and rec.main_investor_id:
                domain.append(('investor_id', '=', rec.main_investor_id.id))
                domain.append(('sub_investor_id', '=', False))
            if rec.transaction_type == 's_2_d' and rec.investor_id:
                domain.append(('sub_investor_id', '=', rec.investor_id.id))
            if rec.investment_id:
                domain.append(('investment_id', '=', rec.investment_id.id))
            if rec.category_ids:
                domain.append(('category_id', 'in', rec.category_ids.ids))
            if rec.unit_category_type_ids:
                domain.append(('unit_category_type_id', 'in', rec.unit_category_type_ids.ids))
            return {
                'domain': {
                    'investor_file_ids': domain,
                }
            }

    @api.onchange('investor_file_ids')
    def check_validation(self):
        for rec in self:
            if (not rec.investor_id and not rec.main_investor_id and not rec.investment_id and not rec.transaction_type and not rec.category_ids and not
            rec.unit_category_type_ids):
                raise ValidationError("Please Fill in all the required fields above to select Files")

    @api.onchange('investor_id')
    def update_main_investor(self):
        for rec in self:
            if rec.investor_id:
                rec.main_investor_id = rec.investor_id.main_investor_id.id

    def draft(self):
        for rec in self:
            rec.state = 'draft'

    def in_approval(self):
        for rec in self:
            rec.state = 'in_approval'

    def approve_request(self):
        for rec in self:
            rec.state = 'approved'

    def cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def process_request(self):
        for rec in self:
            if rec.investor_file_ids:
                for file in rec.investor_file_ids:
                    if rec.transaction_type == 'd_2_s':
                        file.issued_to_sub_dealer = True
                        file.sub_investor_id = rec.investor_id.id
                        self.env['open.file.issuance.history'].create({
                            'investor_file_id': file.id,
                            'issuance_date': datetime.now(),
                            'issuance_type': 'sub_investor',
                            'request_platform': rec.request_platform,
                            'request_id': rec.id,
                        })
                    if rec.transaction_type == 's_2_d':
                        file.issued_to_sub_dealer = False
                        file.sub_investor_id = None
                        self.env['open.file.issuance.history'].create({
                            'investor_file_id': file.id,
                            'issuance_date': datetime.now(),
                            'issuance_type': 'investor',
                            'request_platform': rec.request_platform,
                            'request_id': rec.id,
                        })
            else:
                raise ValidationError("Please Add some Files to Issue")
            rec.state = 'processed'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('subdealer.inventory.management.sequence') or _('New')
        new_record = super().create(vals_list)
        return new_record


class OpenFileIssuanceHistory(models.Model):
    _name = 'open.file.issuance.history'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Open File Issuance History'

    investor_file_id = fields.Many2one('investor.file', tracking=True)
    file_id = fields.Many2one('file', tracking=True)
    issuance_date = fields.Datetime(string="Issuance Date", tracking=True)
    issuance_type = fields.Selection([('customer', 'Customer'), ('investor', 'To Investor'), ('sub_investor', 'To Sub Investor')], string="Issuance Type",
                                     tracking=True)
    request_platform = fields.Selection([('system', 'System'), ('portal', 'Portal')], string="Request Platform", tracking=True)
    request_id = fields.Many2one('subdealer.inventory.management', string="Request No.", tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company", tracking=True)
