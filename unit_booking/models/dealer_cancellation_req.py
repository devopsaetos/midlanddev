from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class DealerCancellation(models.Model):
    _name = 'dealer.cancellation.req'
    _description = 'Dealer Cancellation Request'

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
    security_fee = fields.Float(tracking=True, related='dealer_id.security_fee', store=True)
    valid_till = fields.Date(related='dealer_id.valid_till')
    cancellation_reason = fields.Text()
    is_invoice_generation = fields.Boolean(default=False)
    dealer_id = fields.Many2one('res.partner')
    invoice_id = fields.Many2one('account.move')
    no_of_invoices = fields.Integer(compute='_compute_no_of_invoices')

    def _compute_no_of_invoices(self):
        self.no_of_invoices = len(
            self.env['account.move'].search([('dealer_cancellation_id', '=', self.id), ('move_type', '=', 'in_invoice'),
                                             ('property_invoice_type', '=', 'dealer_cancellation')]))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', _('New')) == _('New'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('dealer.cancellation.request') or _('New')
        return super().create(vals_list)

    def in_process(self):
        for rec in self:
            rec.state = 'in_process'

    def create_invoice(self):
        if not self.is_invoice_generation:
            security_fee = self.env['account.move'].create({
                'partner_id': self.dealer_id.id,
                # 'branch_id': self.env.branch.id,
                'move_type': 'in_invoice',
                'invoice_date': fields.Date.today(),
                'dealer_cancellation_id': self.id,
                'property_invoice_type': 'dealer_cancellation',
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.env.ref('unit_booking.dealer_cancellation').id,
                    'name': self.env.ref('unit_booking.dealer_cancellation').name,
                    'account_id': self.env.ref('unit_booking.dealer_cancellation').property_account_income_id.id,
                    'price_unit': self.security_fee
                })]
            })

            security_fee.action_post()
            self.invoice_id = security_fee.id

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
            'domain': [('dealer_cancellation_id', '=', self.id), ('move_type', '=', 'in_invoice'),
                       ('property_invoice_type', '=', 'dealer_cancellation')],
        }

    def set_to_approve(self):
        asset_record = self.env['dealer.asset.allocation']
        asset_record = asset_record.search([('partner_id', '=', self.dealer_id.id)])
        if asset_record:
            for asset in asset_record:
                for assets in asset.asset_ids:
                    assets.dealer_asset_allocation_id = False
                    assets.asset_status = 'draft'
                    assets.is_asset_issued = False
        self.state = 'approve'
        self.dealer_id.state = 'cancel'
