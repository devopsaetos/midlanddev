from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DealerAssetAllocation(models.Model):
    _name = 'dealer.asset.allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Asset definition which will be assigned to dealer after registration of dealer'

    name = fields.Char()
    sequence_number = fields.Char('Sequence Number', required=True, copy=False, readonly=True, index=True,
                                  default=lambda self: _('New'))
    record_state = fields.Selection([
        ('draft', 'Draft'),
        ('request', 'Request'),
        ('issued', 'Issued')], default='draft', tracking=True)
    partner_id = fields.Many2one('res.partner')
    main_dealer_id = fields.Many2one('res.partner')
    issue_to_sub_dealer = fields.Boolean(default=False)
    date = fields.Date()
    # Location
    city_id = fields.Many2one('res.city', tracking=True)
    # location_id = fields.Many2one('asset.location', tracking=True)
    # area_id = fields.Many2one('asset.area', tracking=True)

    asset_ids = fields.Many2many('account.asset', 'asset_allocation_account_asset_rel',
                                 'asset_allocation_id', 'account_asset_id')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence_number', _('New')) == _('New'):
                vals['sequence_number'] = self.env['ir.sequence'].next_by_code("dealer.asset.allocation") or _('New')
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

    def allocation_request(self):
        if self.asset_ids:
            for assets in self.asset_ids:
                assets.dealer_asset_allocation_id = self.id
                assets.asset_status = 'request'
            self.record_state = 'request'

    def allocation_approve(self):
        if self.asset_ids:
            for assets in self.asset_ids:
                assets.is_asset_issued = True
                assets.asset_status = 'issued'
            self.record_state = 'issued'
            self.partner_id.dealer_asset_allocation_id = self.id

    def unlink(self):
        for rec in self:
            if rec.record_state != 'draft':
                raise ValidationError(_('Record is not in draft state you are not allowed to delete'))

        return super(DealerAssetAllocation, self).unlink()


class AccountAssetExt(models.Model):
    _inherit = 'account.asset'

    dealer_asset_allocation_id = fields.Many2one('dealer.asset.allocation')
    asset_status = fields.Selection([('draft', 'Draft'),
                                     ('request', 'Request'),
                                     ('issued', 'Issued')], default='draft', tracking=True)
    is_asset_issued = fields.Boolean(default=False)
