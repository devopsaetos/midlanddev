from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InvestmentAddInventoryWizard(models.TransientModel):
    _name = 'investment.add.inventory.wizard'
    _description = 'Add Inventory on Reserved Deal'

    investment_id = fields.Many2one('investment', required=True, readonly=True)
    # view domains can only reach one level via parent.<field> - this exposes
    # the deal's own phase_id directly on the wizard for that purpose.
    phase_id = fields.Many2one(related='investment_id.phase_id', readonly=True)
    line_ids = fields.One2many('investment.add.inventory.wizard.line', 'wizard_id', string="Lines")

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one unit."))
        if self.line_ids.filtered(lambda l: not l.inventory_id):
            raise UserError(_("Please select a unit for every line."))
        inventory_recs = self.line_ids.mapped('inventory_id')
        if len(inventory_recs) != len(set(inventory_recs.ids)):
            raise UserError(_("The same unit is selected more than once."))
        if inventory_recs.filtered(lambda i: i.state != 'avalible_for_sale'):
            raise UserError(_(
                "One or more selected units are no longer Available For Sale "
                "(someone else may have just reserved them) - please review."))

        for line in self.line_ids:
            line.inventory_id.write({
                'state': 'investor',
                'investment_id': self.investment_id.id,
                'investor_unit_price': line.investor_unit_price,
            })
        self.investment_id.inventory_ids = [(4, i.id) for i in inventory_recs]
        # Same auto-match used elsewhere (change_booking_and_confirmation) -
        # picks up a per-product predefine.plan for these new units if the
        # deal is plan_type == 'predefine'.
        self.investment_id._auto_assign_predefine_plan(inventory_recs)
        return {'type': 'ir.actions.act_window_close'}


class InvestmentAddInventoryWizardLine(models.TransientModel):
    _name = 'investment.add.inventory.wizard.line'
    _description = 'Add Inventory on Reserved Deal Line'

    wizard_id = fields.Many2one('investment.add.inventory.wizard')
    inventory_id = fields.Many2one('plot.inventory', string="Plot", required=True)
    sector_id = fields.Many2one(related='inventory_id.sector_id', readonly=True)
    category_id = fields.Many2one(related='inventory_id.category_id', readonly=True)
    unit_category_type_id = fields.Many2one(
        related='inventory_id.unit_category_type_id', string="Product", readonly=True)
    list_price = fields.Float(related='inventory_id.list_price', readonly=True)
    investor_unit_price = fields.Float(string="Investor Price")

    @api.onchange('inventory_id')
    def _onchange_inventory_id(self):
        if self.inventory_id:
            self.investor_unit_price = self.inventory_id.list_price
