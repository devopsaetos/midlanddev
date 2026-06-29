from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class DealerRenewal(models.Model):
    _name = 'dealer.renewal.req'
    _description = 'Dealer Renewal Request'

    sequence = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                           default=lambda self: _('New'))
    name = fields.Char(related='dealer_id.name')
    is_unit_booking_agent = fields.Boolean(related='dealer_id.is_unit_booking_agent')
    unit_booking_agent_type = fields.Selection([
        ('main_agent', "Main Dealer"),
        ('sub_agent', "Sub Dealer")],
        string="Dealer Type",
        help="""Type of the Dealer. Either the Main Dealer or the Sub Dealer""",
        related='dealer_id.unit_booking_agent_type'
    )
    state = fields.Selection([
        ('draft', "Draft"),
        ('in_process', 'In Process'),
        ('invoice', 'Invoice'),
        ('approve', "Approve")], default='draft')
    unit_booking_agent_id = fields.Many2one('res.partner',
                                            domain=[('unit_booking_agent_type', '=', 'main_agent')],
                                            related='dealer_id.unit_booking_agent_id')
    company_type = fields.Selection(related='dealer_id.company_type')
    dealer_category_id = fields.Many2one('dealer.category', tracking=True, related='dealer_id.dealer_category_id')
    registration_fee = fields.Float(tracking=True, related='dealer_id.registration_fee')
    security_fee = fields.Float(tracking=True, related='dealer_id.security_fee')
    valid_till = fields.Date(related='dealer_id.valid_till')
    renewal_fee = fields.Float()
    is_invoice_generation = fields.Boolean(default=False)
    dealer_id = fields.Many2one('res.partner')
    next_renewal_date = fields.Date()
    invoice_id = fields.Many2one('account.move')
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(
            self.env['account.move'].search([('dealer_renewal_id', '=', self.id), ('move_type', '=', 'out_invoice'),
                                             ('property_invoice_type', '=', 'renewal')]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', _('New')) == _('New'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('dealer.renewal.request') or _('New')
        return super().create(vals_list)

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'

    def create_invoice(self):
        if not self.is_invoice_generation:
            renewal_fee = self.env['account.move'].create({
                'partner_id': self.dealer_id.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'out_invoice',
                'journal_id': self.env.company.account_journal_id.id,
                'invoice_date': fields.Date.today(),
                'dealer_renewal_id': self.id,
                'property_invoice_type': 'renewal',
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.dealer_renewal').id,
                    'name': self.env.ref('unit_booking.dealer_renewal').name,
                    'account_id': self.env.ref('unit_booking.dealer_renewal').property_account_income_id.id,
                    'price_unit': self.renewal_fee
                })]
            })

            renewal_fee.action_post()
            self.invoice_id = renewal_fee.id

            self.is_invoice_generation = True
            self.state = 'invoice'
        else:
            raise ValidationError(_('Invoice is already generated'))

    def open_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'views': [(self.env.ref('account.view_invoice_tree').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
            'view_mode': 'list,form',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'domain': [('dealer_renewal_id', '=', self.id), ('move_type', '=', 'out_invoice'),
                       ('property_invoice_type', '=', 'renewal')],
        }

    def set_to_approve(self):
        for rec in self:
            rec.state = 'approve'
            rec.dealer_id.state = 'approve'
            rec.dealer_id.valid_till = self.next_renewal_date
