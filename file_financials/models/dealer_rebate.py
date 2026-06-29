from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class DealerRebate(models.Model):
    _inherit = 'dealer.rebate'
    _description = 'Dealer Rebate'

    @api.constrains('effective_from', 'effective_to')
    def _check_double(self):
        record = self.search(
            [('id', '!=', self.id),
             '|',
             '|',
             '|',
             '&',
             ('effective_from', '<=', self.effective_from),
             ('effective_to', '=', False),

             '&',
             ('effective_from', '<=', self.effective_from),
             ('effective_to', '>=', self.effective_from),

             '|',
             '&',
             ('effective_from', '<=', self.effective_to),
             ('effective_to', '=', False),

             '&',
             ('effective_from', '<=', self.effective_to),
             ('effective_to', '>=', self.effective_to),
             '&',
             ('effective_from', '>=', self.effective_from),
             ('effective_to', '<=', self.effective_to),

             ]
        )

        if not record and not self.effective_to:
            record = self.search([
                ('effective_from', '>=', self.effective_from),
                ('id', '!=', self.id)
            ])

        if record:
            pass
            # raise ValidationError(_("Rebate Policy is already exist in:: %s" % (record.mapped('name')[0])))
        if self.effective_from < fields.Date.today():
            raise ValidationError(_("Effective From can't be in past"))
        if self.effective_to:
            if self.effective_to < fields.Date.today():
                raise ValidationError(_("Effective To can't be in past"))
            elif self.effective_to < self.effective_from:
                raise ValidationError(_("Effective to can't be smaller than effective from"))

    @api.constrains('rebate_line_ids')
    def category_constrains(self):
        for category in self.rebate_line_ids:
            record = self.rebate_line_ids.filtered(lambda s: s.category_id.id == category.category_id.id)
            if len(record) > 1:
                pass
                # raise ValidationError(
                #     _(f"You cannot have multiple lines with same Category '{record[1].category_id.name}'"))


class DealerRebateLineExt(models.Model):
    _inherit = 'dealer.rebate.line'
    _description = 'Dealer Rebate Line'

    partner_id = fields.Many2one('res.partner')
    agent_type = fields.Selection([('dealer', 'Dealer'), ('marketing_company', 'Marketing Company')], default="dealer", string="Agent Type", required=True,
                                  tracking=True)
    transaction_type = fields.Selection([('booking', 'Booking'), ('confirmation', 'Confirmation')], default="booking", string="Transaction Type", required=True,
                                        tracking=True)
    calculation_basis = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')], default="percentage", tracking=True)
    settlement_option = fields.Selection(selection_add=[('files', 'Files')])
    # Numerical fields
    marketing_rebate_percentage = fields.Float(tracking=True)
    dealer_rebate_percentage = fields.Float(tracking=True)
    rebate_given = fields.Float(string='Rebate Given')
    move_id = fields.Many2one('account.move', string="Entry #")

