from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InvestmentAssignPlanWizard(models.TransientModel):
    _name = 'investment.assign.plan.wizard'
    _description = 'Assign Plan on Reserved Deal'

    investment_id = fields.Many2one('investment', required=True, readonly=True)
    line_ids = fields.One2many('investment.assign.plan.wizard.line', 'wizard_id', string="Lines")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        investment_id = self.env.context.get('default_investment_id')
        if investment_id and 'line_ids' in fields_list:
            investment = self.env['investment'].browse(investment_id)
            lines = investment.investment_line_ids if investment.reservation_type == 'bulk' else investment.inventory_ids
            missing = lines.filtered(lambda l: not l.predefine_plan_id)
            vals['line_ids'] = [(0, 0, {
                'investment_line_id': line.id if investment.reservation_type == 'bulk' else False,
                'plot_inventory_id': line.id if investment.reservation_type == 'unit' else False,
                'sector_id': line.sector_id.id,
                'street_id': line.street_id.id,
                'unit_category_type_id': line.unit_category_type_id.id,
            }) for line in missing]
        return vals

    def action_confirm(self):
        self.ensure_one()
        if self.line_ids.filtered(lambda l: not l.predefine_plan_id):
            raise UserError(_("Please select a Plan for every line before confirming."))
        for line in self.line_ids:
            record = line.investment_line_id or line.plot_inventory_id
            record.predefine_plan_id = line.predefine_plan_id.id
            record.own_plan = True
            # Same math the row's own onchange runs (calculate_amount_and_values) -
            # called directly here since a plain write() doesn't trigger onchains.
            record.calculate_amount_and_values()
        # Piggyback on InvestmentExt.write()'s existing recompute of the header's
        # combined schedule fields (down_payment/confirmation_amount/...) for
        # multiple_plans deals, instead of duplicating that aggregation here.
        self.investment_id.write({})
        return {'type': 'ir.actions.act_window_close'}


class InvestmentAssignPlanWizardLine(models.TransientModel):
    _name = 'investment.assign.plan.wizard.line'
    _description = 'Assign Plan on Reserved Deal Line'

    wizard_id = fields.Many2one('investment.assign.plan.wizard')
    investment_line_id = fields.Many2one('investment.line')
    plot_inventory_id = fields.Many2one('plot.inventory')
    sector_id = fields.Many2one('sector', readonly=True)
    street_id = fields.Many2one('street', readonly=True)
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product", readonly=True)
    predefine_plan_id = fields.Many2one(
        'predefine.plan', string="Plan",
        domain="[('unit_category_type_id','=',unit_category_type_id)]")
