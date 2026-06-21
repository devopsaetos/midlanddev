from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PredefinePlan(models.Model):
    _name = 'predefine.plan'
    _description = "Predefine Plan"

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    confirmation_amount_period = fields.Integer()
    interval_id = fields.Many2one('payment.interval', required=True)
    total_installment = fields.Integer()
    applicable = fields.Selection([
        ('project', 'Project'),
        ('product', 'Product'),
    ])
    include_in_plan = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], default='no')
    unit_category_type_id = fields.Many2one('unit.category.type')

    predefine_plan_line_ids = fields.One2many('predefine.plan.line', 'predefine_plan_id')
    treat_balloon_as = fields.Selection([('installment', 'Installment'), ('balloon', 'Balloon')])


class PredefinePlanLine(models.Model):
    _name = 'predefine.plan.line'
    _description = "Predefine Plan Lines"

    product_id = fields.Many2one('product.realestate', required=True, ondelete='restrict')
    basis = fields.Selection([
        ('percentage', 'Percentage'),
        ('fix', 'Fix'),
    ], default='percentage')
    value = fields.Float()
    interval = fields.Integer()
    frequency = fields.Integer()
    include_installment = fields.Boolean()
    start_from = fields.Integer()

    predefine_plan_id = fields.Many2one('predefine.plan')

    @api.constrains('frequency')
    def check_product_interval(self):
        for rec in self:
            if rec.product_id.id == rec.env.ref('real_estate.possession_amount_product').id:
                if rec.frequency > 1:
                    raise ValidationError(_('Possession amount frequency should be 1'))
            if rec.product_id.id == rec.env.ref('real_estate.confirmation_amount_product').id:
                if rec.frequency > 1:
                    raise ValidationError(_('Confirmation amount frequency should be 1'))

    @api.constrains('basis', 'value')
    def check_percentage_value(self):
        for rec in self:
            if rec.basis == 'percentage' and (rec.value < 0 or rec.value > 100):
                raise ValidationError(_(
                    'Value for "%s" must be between 0 and 100 when Basis is "Percentage" (got %.2f). '
                    'Use Basis "Fix" instead if you meant to enter a fixed amount.'
                ) % (rec.product_id.display_name, rec.value))
