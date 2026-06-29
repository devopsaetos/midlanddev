from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class DealerRebate(models.Model):
    _name = 'dealer.rebate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Dealer Rebate'
    _rec_name = 'policy_name'

    name = fields.Char(string='Serial Number', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))

    state = fields.Selection([('draft', 'Draft'), ('active', 'Active')], default='draft', tracking=True)
    policy_name = fields.Char(string="Policy Name")
    effective_from = fields.Date(tracking=True)
    effective_to = fields.Date(tracking=True)

    # company related fields
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True, readonly=True)
    # branch_id = fields.Many2one('res.branch', default=lambda self: self.env.branch, tracking=True, readonly=True)

    # relational fields
    rebate_line_ids = fields.One2many('dealer.rebate.line', 'rebate_id', tracking=True)
    # numerical field
    total_rebate = fields.Float(string="Policy Rebate")

    def set_to_active(self):
        for rec in self:
            rec.state = 'active'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("rebate.policy") or _('New')
        return super().create(vals_list)

    @api.constrains('rebate_line_ids')
    def category_constrains(self):
        for category in self.rebate_line_ids:
            record = self.rebate_line_ids.filtered(lambda s: s.category_id.id == category.category_id.id)
            if len(record) > 1:
                raise ValidationError(
                    _(f"You cannot have multiple lines with same Category '{ record[1].category_id.name}'"))

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
            raise ValidationError(_("Rebate Policy is already exist in:: %s" % (record.mapped('name')[0])))
        if self.effective_from < fields.Date.today():
            raise ValidationError(_("Effective From can't be in past"))
        if self.effective_to:
            if self.effective_to < fields.Date.today():
                raise ValidationError(_("Effective To can't be in past"))
            elif self.effective_to < self.effective_from:
                raise ValidationError(_("Effective to can't be smaller than effective from"))


class DealerRebateLine(models.Model):
    _name = 'dealer.rebate.line'
    _description = 'Dealer Rebate Line'

    # selection fields
    settlement_option = fields.Selection([('net_off', 'Net Off'), ('separate', 'Separate')], tracking=True)
    calculation_basis = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')], tracking=True)
    rate_calculation = fields.Selection([('per_marla', 'Per Marla'), ('per_file', 'Per File')], tracking=True)

    # Numerical fields
    total_rebate = fields.Float(tracking=True)
    rebate_at_deal = fields.Float(tracking=True)
    rebate_at_sale = fields.Float(tracking=True)

    # relational fields
    rebate_id = fields.Many2one('dealer.rebate')
    sector_id = fields.Many2one('sector', readonly=False)
    category_id = fields.Many2one('plot.category', string='Category')

    # @api.constrains('rebate_at_deal', 'rebate_at_sale')
    # def check_value_for_rebate(self):
    #     for rec in self:
    #         if rec.calculation_basis:
    #             if (rec.rebate_at_deal + rec.rebate_at_sale) > rec.total_rebate:
    #                 raise ValidationError(_(f"'Rebate At Deal' and 'Rebate At Sale' can't be greater than 'Total Rebate' in each line"))
