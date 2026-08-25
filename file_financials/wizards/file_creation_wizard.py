from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InvestmentFileCreationWizard(models.TransientModel):
    _name = 'investment.file.creation.wizard'
    _description = 'Selective Create Open File on Investor Deal'

    investment_id = fields.Many2one('investment', required=True, readonly=True)
    line_ids = fields.One2many(
        'investment.file.creation.wizard.line', 'wizard_id', string="Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        investment_id = res.get('investment_id') or self.env.context.get('default_investment_id')
        if investment_id:
            investment = self.env['investment'].browse(investment_id)
            # only units that don't already have an open file are offered -
            # this wizard is meant to be reopened repeatedly as more payment
            # comes in, so already-issued units must not be selectable again.
            pending = investment.inventory_ids.filtered(lambda i: not i.investor_file_id)
            res['line_ids'] = [(0, 0, {'inventory_id': inv.id}) for inv in pending]
        return res

    def action_create_open_files(self):
        self.ensure_one()
        checked = self.line_ids.filtered(lambda l: l.is_checked)
        if not checked:
            raise UserError(_("Please select at least one unit."))

        # Even on a multi-plan ("Multiple Plans") deal, _get_installment_plan_groups()
        # (investment.py) always collapses everything into ONE combined Booking row
        # for the whole deal - not one per unit's own predefine_plan_id - so units of
        # different plans still draw from the same single pool. Eligibility is
        # therefore checked deal-wide, not per selected unit's own plan.
        booking_lines = self.investment_id.investment_plan_ids.filtered(
            lambda l: l.installment_type in ('down', 'down_payment') and l.amount_paid > 0)
        # amount_paid already reflects the invoice's true paid amount, whether it
        # was settled by cash or by a rebate netted off against it (a Net Off
        # rebate closes the invoice to Paid without a separate cash payment) - a
        # rebate-settled invoice is just as usable to fund Open File creation as
        # a cash-settled one, so the full amount_paid counts toward the pool.
        pool = sum(l.amount_paid for l in booking_lines)
        already_distributed = sum(self.env['installment.plan'].search([
            ('investor_file_id.investment_id', '=', self.investment_id.id),
            ('installment_type', 'in', ('down', 'down_payment')),
        ]).mapped('amount_paid'))
        available = pool - already_distributed
        needed = sum(checked.mapped('estimated_booking_share'))
        if needed > available:
            raise UserError(_(
                "Not enough Booking payment received yet for the selected unit(s): "
                "need %(needed)s, only %(available)s available. Select fewer units "
                "or wait for more payment.",
                needed=needed, available=available))

        self.investment_id.create_open_file(inventory=checked.mapped('inventory_id'))
        return {'type': 'ir.actions.act_window_close'}

    def _prorate(self):
        self.ensure_one()
        # Booking and Down Payment are independent amounts - a plan can carry
        # either, or both at once - so the prorated upfront share is based on
        # their combined total, not Booking alone.
        upfront_total = self.investment_id.down_payment + self.investment_id.down_payment_amount
        return (upfront_total / self.investment_id.total_amount) \
            if self.investment_id.total_amount else 0.0


class InvestmentFileCreationWizardLine(models.TransientModel):
    _name = 'investment.file.creation.wizard.line'
    _description = 'Selective Create Open File on Investor Deal Line'

    wizard_id = fields.Many2one('investment.file.creation.wizard')
    inventory_id = fields.Many2one('plot.inventory', string="Plot", required=True, readonly=True)
    sector_id = fields.Many2one(related='inventory_id.sector_id', readonly=True)
    street_id = fields.Many2one(related='inventory_id.street_id', readonly=True)
    category_id = fields.Many2one(related='inventory_id.category_id', readonly=True)
    size_id = fields.Many2one(related='inventory_id.size_id', readonly=True)
    name = fields.Char(related='inventory_id.name', readonly=True, string="Plot No.")
    investor_unit_price = fields.Float(related='inventory_id.investor_unit_price', readonly=True)
    estimated_booking_share = fields.Float(
        string="Estimated Booking Share", compute='_compute_estimated_booking_share')
    is_checked = fields.Boolean(default=False, string="Select")

    @api.depends('inventory_id', 'wizard_id.investment_id')
    def _compute_estimated_booking_share(self):
        for line in self:
            line.estimated_booking_share = round(
                line.inventory_id.investor_unit_price * line.wizard_id._prorate())
