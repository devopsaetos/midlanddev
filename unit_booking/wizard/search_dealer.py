from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SearchDealer(models.TransientModel):
    _name = 'search.dealer'
    _description = 'Search Dealer'

    dealer_id = fields.Many2one('res.partner')
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    process = fields.Selection([('renewal', 'Renewal'), ('cancellation', 'Cancellation')])
    search_line_ids = fields.One2many('search.dealer.line', 'search_id')

    def search_related_records(self):
        domain = [('is_unit_booking_agent', '=', True), ('state', 'not in', ['draft', 'renewal', 'cancellation'])]
        self.search_line_ids.unlink()
        if self.dealer_id:
            domain.append(('id', '=', self.dealer_id.id))
        if self.date_from:
            domain.append(('valid_till', '>=', self.date_from))
        if self.date_to:
            domain.append(('valid_till', '<=', self.date_to))
        record_set = self.env['res.partner'].search(domain)
        if record_set:
            for record in record_set:
                self.search_line_ids = [(0, 0, {
                    'dealer_id': record.id,
                })]
        if not record_set:
            raise ValidationError(_('Record not found'))

        return {
            'name': _('Search'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def create_req(self):
        if self.process == 'renewal':
            dealer_ids = []
            new_created_record_list = []
            record_set_id = False
            record_set = self.env['dealer.renewal.req']
            for rec in self.search_line_ids.filtered(lambda checked: checked.is_checked):
                rec.dealer_id.state = 'renewal'
                dealer_ids.append(rec.dealer_id.id)
                record_set_id = record_set.create({
                    'dealer_id': rec.dealer_id.id,
                })
                new_created_record_list.append(record_set_id.id)
            # issuance req tree and form view of current issued record
            tree_view = (self.env.ref('unit_booking.renewal_tree_view').id, 'tree')
            form_view = (self.env.ref('unit_booking.renewal_form_view').id, 'form')
            if len(new_created_record_list) > 1:
                return {
                    'name': _('Dealer Renewal Request'),
                    'context': self.env.context,
                    'res_model': 'dealer.renewal.req',
                    'type': 'ir.actions.act_window',
                    'views': [tree_view, form_view],
                    'view_mode': 'list,form',
                    'domain': [('dealer_id', 'in', dealer_ids), ('state', '=', 'draft')],
                    'target': 'self'
                }
            else:
                return {
                    'name': _('Dealer Renewal Request'),
                    'context': self.env.context,
                    'res_model': 'dealer.renewal.req',
                    'type': 'ir.actions.act_window',
                    'res_id': record_set_id.id,
                    'view_mode': 'form',
                    'target': 'self'
                }
        elif self.process == 'cancellation':
            dealer_ids = []
            new_created_record_list = []
            record_set_id = False
            record_set = self.env['dealer.cancellation.req']
            for rec in self.search_line_ids.filtered(lambda checked: checked.is_checked):
                rec.dealer_id.state = 'in_process'
                dealer_ids.append(rec.dealer_id.id)
                record_set_id = record_set.create({
                    'dealer_id': rec.dealer_id.id,
                })
                new_created_record_list.append(record_set_id.id)
            # issuance req tree and form view of current issued record
            tree_view = (self.env.ref('unit_booking.dealer_cancellation_tree_view').id, 'tree')
            form_view = (self.env.ref('unit_booking.dealer_cancellation_form_view').id, 'form')
            if len(new_created_record_list) > 1:
                return {
                    'name': _('Dealer Renewal Request'),
                    'context': self.env.context,
                    'res_model': 'dealer.cancellation.req',
                    'type': 'ir.actions.act_window',
                    'views': [tree_view, form_view],
                    'view_mode': 'list,form',
                    'domain': [('dealer_id', 'in', dealer_ids), ('state', '=', 'draft')],
                    'target': 'self'
                }
            else:
                return {
                    'name': _('Dealer Renewal Request'),
                    'context': self.env.context,
                    'res_model': 'dealer.cancellation.req',
                    'type': 'ir.actions.act_window',
                    'res_id': record_set_id.id,
                    'view_mode': 'form',
                    'target': 'self'
                }


class SearchDealerLine(models.TransientModel):
    _name = 'search.dealer.line'
    _description = 'Search Dealer Line'

    is_checked = fields.Boolean(default=False)
    state = fields.Selection([
        ('draft', "Draft"),
        ('in_process', 'In Process'),
        ('invoice', 'Invoice'),
        ('approve', "Approve"), ('renewal', 'Renewal')], default='draft', related='dealer_id.state')
    unit_booking_agent_type = fields.Selection([
        ('main_agent', "Main Dealer"),
        ('sub_agent', "Sub Dealer")],
        string="Dealer Type",
        help="""Type of the Dealer. Either the Main Dealer or the Sub Dealer""",
        related='dealer_id.unit_booking_agent_type'
    )
    dealer_id = fields.Many2one('res.partner')
    dealer_category_id = fields.Many2one('dealer.category', tracking=True, related='dealer_id.dealer_category_id')
    registration_fee = fields.Float(related='dealer_id.registration_fee')
    security_fee = fields.Float(related='dealer_id.security_fee')
    valid_till = fields.Date(related='dealer_id.valid_till')
    search_id = fields.Many2one('search.dealer')
