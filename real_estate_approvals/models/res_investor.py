from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResInvestor(models.Model):
    _inherit = 'res.investor'

    approval_request_ids = fields.One2many(
        'approval.request',
        'investor_id',
        string='Approval Requests',
    )
    approval_request_count = fields.Integer(
        compute='_compute_approval_request_count',
    )
    latest_approval_status = fields.Selection(
        selection=[
            ('new', 'To Submit'),
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
            ('cancel', 'Cancelled'),
        ],
        compute='_compute_latest_approval_status',
        store=False,
    )
    is_current_user_approver = fields.Boolean(
        compute='_compute_is_current_user_approver',
        help='True when the current user is a pending approver on the latest approval request.',
    )

    @api.depends('approval_request_ids')
    def _compute_approval_request_count(self):
        for rec in self:
            rec.approval_request_count = len(rec.approval_request_ids)

    @api.depends('approval_request_ids.request_status')
    def _compute_latest_approval_status(self):
        for rec in self:
            latest = rec.approval_request_ids.sorted('create_date', reverse=True)[:1]
            rec.latest_approval_status = latest.request_status if latest else False

    @api.depends(
        'approval_request_ids.request_status',
        'approval_request_ids.approver_ids.user_id',
        'approval_request_ids.approver_ids.status',
    )
    def _compute_is_current_user_approver(self):
        current_uid = self.env.uid
        for rec in self:
            latest = rec.approval_request_ids.sorted('create_date', reverse=True)[:1]
            if not latest or latest.request_status != 'pending':
                rec.is_current_user_approver = False
                continue
            pending_for_me = latest.approver_ids.filtered(
                lambda a: a.user_id.id == current_uid and a.status in ('new', 'pending')
            )
            rec.is_current_user_approver = bool(pending_for_me)

    def _get_investor_approval_category(self):
        category = self.env.ref(
            'real_estate_approvals.approval_category_investor_registration',
            raise_if_not_found=False,
        )
        if not category:
            raise UserError(_(
                'Approval category "Investor Registration" not found. '
                'Please reinstall the Real Estate Approvals module.'
            ))
        return category

    def action_request_approval(self):
        self.ensure_one()
        open_request = self.approval_request_ids.filtered(
            lambda r: r.request_status in ('new', 'pending')
        )
        if open_request:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Approval Request'),
                'res_model': 'approval.request',
                'res_id': open_request[:1].id,
                'view_mode': 'form',
                'target': 'current',
            }
        category = self._get_investor_approval_category()
        request = self.env['approval.request'].create({
            'name': _('Investor Registration — %s') % (self.investor_id or self.ref or _('New')),
            'category_id': category.id,
            'request_owner_id': self.env.user.id,
            'investor_id': self.id,
            'reason': _('Approval requested for investor registration: %s') % (self.investor_id or ''),
        })
        request.action_confirm()
        self.state = 'in_process'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Request'),
            'res_model': 'approval.request',
            'res_id': request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def in_process(self):
        return self.action_request_approval()

    def approve(self):
        for rec in self:
            if rec.latest_approval_status != 'approved':
                raise UserError(_(
                    'Investor "%s" cannot be approved until its approval request '
                    'has been approved by the configured approvers.'
                ) % (rec.investor_id or rec.ref or ''))
        return super().approve()

    def action_view_approval_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Requests'),
            'res_model': 'approval.request',
            'view_mode': 'list,form',
            'domain': [('investor_id', '=', self.id)],
            'context': {'default_investor_id': self.id},
        }

    def _get_pending_request(self):
        self.ensure_one()
        latest = self.approval_request_ids.sorted('create_date', reverse=True)[:1]
        if not latest or latest.request_status != 'pending':
            raise UserError(_('No pending approval request found for this investor.'))
        return latest

    def action_approve_request(self):
        self.ensure_one()
        request = self._get_pending_request()
        my_approver = request.approver_ids.filtered(
            lambda a: a.user_id.id == self.env.uid and a.status in ('new', 'pending')
        )
        if not my_approver:
            raise UserError(_(
                'You are not listed as a pending approver on this request.'
            ))
        request.action_approve()
        return True

    def action_refuse_request(self):
        self.ensure_one()
        request = self._get_pending_request()
        my_approver = request.approver_ids.filtered(
            lambda a: a.user_id.id == self.env.uid and a.status in ('new', 'pending')
        )
        if not my_approver:
            raise UserError(_(
                'You are not listed as a pending approver on this request.'
            ))
        request.action_refuse()
        return True
