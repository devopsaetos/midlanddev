from odoo import fields, models, api, _


class BuyBack(models.Model):
    _name = 'buy.back'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Buy Back Open File which is allotted or issued to dealer'

    # char fields
    name = fields.Char()
    sequence_number = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                                  default=lambda self: _('New'))
    # selection field
    state = fields.Selection([('draft', 'Draft'),
                              ('in_process', 'In Process'),
                              ('approve', 'Approve')],
                             default='draft', tracking=True)
    buy_back_option = fields.Selection([('cash', 'Cash'),
                                        ('adjustment', 'Adjustment')], tracking=True)
    # date field
    date = fields.Date()

    # relational fields
    partner_id = fields.Many2one('res.partner', tracking=True)
    main_dealer_id = fields.Many2one('res.partner', tracking=True)
    buy_back_line_ids = fields.One2many('buy.back.line', 'buy_back_id')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch, tracking=True)
    invoice_id = fields.Many2one('account.move')
    dealer_cancellation_id = fields.Many2one('dealer.cancellation.req')

    # boolean field
    issue_to_sub_dealer = fields.Boolean(default=False, tracking=True)
    # numeric field
    total_initial_payment = fields.Float()
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'
            for open_file in rec.buy_back_line_ids:
                open_file.units_booking_id.state = 'draft'
                rec.total_initial_payment += open_file.units_booking_id.initial_payment

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'domain': [('buy_back_id', '=', self.id)],
        }

    def _compute_no_of_invoices(self):
        for rec in self:
            rec.no_of_invoices = len(rec.env['account.move'].search([('buy_back_id', '=', rec.id)]))

    def buy_back_scanning(self):
        return {
            'name': _('QR'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'file.qr.scanning',
            'type': 'ir.actions.act_window',
            'context': {
                'default_issue_to_sub_dealer': self.issue_to_sub_dealer,
                'default_buy_back_id': self.id,
            },
            'target': 'new'
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence_number', _('New')) == _('New'):
                vals['sequence_number'] = self.env['ir.sequence'].next_by_code("buy.back.open.file") or _('New')
        return super().create(vals_list)

    @api.onchange('issue_to_sub_dealer')
    def _dealer_sub_dealer_domain(self):
        if self.issue_to_sub_dealer:
            return {'domain': {
                'partner_id': [('is_unit_booking_agent', '=', True), ('unit_booking_agent_type', '=', 'sub_agent'),
                               ('state', '=', 'approve')],
            }
            }
        elif not self.issue_to_sub_dealer:
            return {'domain': {
                'partner_id': [('is_unit_booking_agent', '=', True), ('unit_booking_agent_type', '=', 'main_agent'),
                               ('state', '=', 'approve')],
            }
            }

    @api.onchange('partner_id')
    def onchange_issue_to_sub_agent(self):
        for rec in self:
            if rec.partner_id and rec.partner_id.unit_booking_agent_type == 'sub_agent':
                rec.main_dealer_id = rec.partner_id.unit_booking_agent_id.id

    def approve(self):
        if self.buy_back_option == 'cash':
            invoice = self.env['account.move'].create({
                'buy_back_id': self.id,
                'move_type': 'in_invoice',
                'partner_id': self.partner_id.id,
                'company_id': self.env.company.id,
                # 'branch_id': self.env.branch.id,
                'property_invoice_type': 'buy_back',
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.buy_back_open_file').id,
                    'name': self.env.ref('unit_booking.buy_back_open_file').name,
                    'account_id': self.env.ref(
                        'unit_booking.buy_back_open_file').property_account_income_id.id,
                    'price_unit': self.total_initial_payment,
                })]
            })
            invoice.action_post()
            self.invoice_id = invoice.id
        elif self.buy_back_option == 'adjustment':
            prod = [(0, 0, {
                'product_id': self.env.ref('unit_booking.buy_back_open_file').id,
                'name': self.env.ref('unit_booking.buy_back_open_file').name,
                'account_id': self.env.ref('unit_booking.buy_back_open_file').property_account_income_id.id,
                'price_unit': self.total_initial_payment
            })]
            # Credit Note
            invoice = self.env['account.move'].create({
                'move_type': 'out_refund',
                'partner_id': self.partner_id.id,
                'company_id': self.env.company.id,
                # 'branch_id': self.env.branch.id,
                'invoice_date': fields.Date.today(),
                # 'journal_id': self.env.company.account_journal_id.id,
                'invoice_line_ids': prod,
            })
            invoice.action_post()
            self.invoice_id = invoice.id
        self.state = 'approve'
        amount_deducted = 0
        for open_file in self.buy_back_line_ids:
            # getting the current allotment deal plan of current file
            deal_installment_plan = open_file.units_booking_id.unit_booking_allotment_id.booking_plan_ids.filtered(lambda l: l.installment_type in
                                                        ['installment', 'balloon',
                                                         'possession_amount',
                                                         'balloting_amount',
                                                         'confirmation_amount'] and not l.invoice_created)
            # checking the remaining installments should be greater
            if len(deal_installment_plan) > 0:
                # calculating amount for deduction for deal installment plan because file is no longer part of that deal
                amount_deducted = open_file.units_booking_id.initial_payment / len(deal_installment_plan)
                for plan in deal_installment_plan:
                    plan.write({'file_adjusted_amount': plan.file_adjusted_amount + amount_deducted,
                                'balance_amount': plan.balance_amount - amount_deducted,
                                'residual': plan.residual - amount_deducted})
            if open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids:
                open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids = [(0, 0, {
                    'installment_number': open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids[-1].installment_number + 1,
                    'date': fields.Date.today(),
                    'transaction_type': 'buy_back',
                    'amount': open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids[-1].new_amount,
                    'new_amount': open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids[-1].new_amount - amount_deducted,
                    'old_balance': open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids[-1].new_balance,
                    'new_balance': open_file.units_booking_id.unit_booking_allotment_id.booking_allotment_history_ids[-1].new_balance - open_file.units_booking_id.initial_payment,
                    'booking_allotment_id': open_file.units_booking_id.unit_booking_allotment_id.id,
                })]
            open_file.units_booking_id.state = 'print'
            current_row_open_file_in_deal_plan = open_file.units_booking_id.unit_booking_allotment_id.unit_booking_allotment_line_ids.filtered(lambda l: l.units_booking_id == open_file.units_booking_id)
            current_row_open_file_in_deal_plan.state = 'draft'
            open_file.units_booking_id.agent_id = False
            open_file.units_booking_id.sub_agent_id = False
            open_file.units_booking_id.unit_booking_allotment_id = False


class BuyBackLine(models.Model):
    _name = 'buy.back.line'
    _description = 'Buy Back Open File line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', related='units_booking_id.unit_category_type_id')
    price = fields.Float(related='units_booking_id.sale_amount')
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment',
                                                related='units_booking_id.unit_booking_allotment_id')
    state = fields.Selection(related='units_booking_id.state')

    buy_back_id = fields.Many2one('buy.back')

    @api.onchange('units_booking_id')
    def onchange_method(self):
        if self.buy_back_id.issue_to_sub_dealer:
            return {
                'domain': {
                    'units_booking_id': [
                        ('sub_agent_id', '=', self.buy_back_id.partner_id.id),
                        ('state', 'in', ['allotment', 'issued']),
                        ('agent_id', '=', self.buy_back_id.main_dealer_id.id)]
                }
            }
        elif not self.buy_back_id.issue_to_sub_dealer:
            return {
                'domain': {
                    'units_booking_id': [
                        ('state', 'in', ['allotment', 'issued']),
                        ('agent_id', '=', self.buy_back_id.partner_id.id),
                        ('sub_agent_id', '=', False)]
                }
            }
