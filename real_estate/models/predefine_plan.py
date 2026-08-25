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

    def get_schedule_params(self, amount, no_of_units):
        """The product-by-product percentage/fixed math Investment._onchange_total_amount()
        used to run inline against self.total_amount/self.no_of_units - factored out here so
        a per-bucket plan-group can run the exact same math against its own sub-total/unit
        count. confirmation_amount_period/confirmation_period_type are added by
        file_financials/models/predefine_plan.py; referencing them here matches what the
        onchange this replaces already assumed."""
        # NOTE: include_in_plan/treat_balloon_as are deliberately NOT in this dict -
        # they're fields on predefine.plan itself, not on investment, so they were
        # never something _onchange_total_amount could self.update() onto the deal;
        # the create_installment_plan loop always reads them straight off
        # self.predefine_plan_id.include_in_plan/.treat_balloon_as. Callers doing
        # per-group generation should read them the same way, off
        # group['predefine_plan_id'], not off this returned dict.
        self.ensure_one()
        params = {
            'interval_id': self.interval_id.id,
            'grace_period': self.confirmation_amount_period,
            'grace_period_type': self.confirmation_period_type,
            'total_installment': self.total_installment,
            'down_payment': 0.0,
            'down_payment_amount': 0.0,
            'down_payment_interval': 0,
            'down_payment_frequency': 0,
            'down_payment_start': 0,
            'balloting_amount': 0.0,
            'balloon_payment': 0.0,
            'balloon_payment_interval': 0,
            'balloon_payment_frequency': 0,
            'balloon_payment_start': 0,
            'include_installment': False,
            'add_balloon_amount': 0.0,
            'add_balloon_interval': 0,
            'add_balloon_frequency': 0,
            'possession_amount': 0.0,
            'possession_amount_interval': 0,
            'possession_amount_frequency': 0,
            'confirmation_amount': 0.0,
            'confirmation_amount_interval': 0,
            'confirmation_amount_frequency': 0,
            'primary_amount': 0.0,
            'primary_amount_interval': 0,
            'primary_amount_frequency': 0,
        }
        for pre_plan in self.predefine_plan_line_ids:
            value = round(amount * (pre_plan.value / 100) if pre_plan.basis == 'percentage'
                          else pre_plan.value * no_of_units)
            product_id = pre_plan.product_id.id
            if product_id == self.env.ref('real_estate.downpayment_product').id:
                params['down_payment'] = value
            elif product_id == self.env.ref('real_estate.down_payment_product').id:
                params['down_payment_amount'] = value
                params['down_payment_interval'] = pre_plan.interval
                params['down_payment_frequency'] = pre_plan.frequency
                params['down_payment_start'] = pre_plan.start_from
            elif product_id == self.env.ref('real_estate.final_product').id:
                params['balloting_amount'] = value
            elif product_id == self.env.ref('real_estate.balloon_payment').id:
                params['balloon_payment'] = value
                params['balloon_payment_interval'] = pre_plan.interval
                params['balloon_payment_frequency'] = pre_plan.frequency
                params['balloon_payment_start'] = pre_plan.start_from
                params['include_installment'] = pre_plan.include_installment
            elif product_id == self.env.ref('real_estate.additional_balloon').id:
                params['add_balloon_amount'] = value
                params['add_balloon_interval'] = pre_plan.interval
                params['add_balloon_frequency'] = pre_plan.frequency
            elif product_id == self.env.ref('real_estate.possession_amount_product').id:
                params['possession_amount'] = value
                params['possession_amount_interval'] = pre_plan.interval
                params['possession_amount_frequency'] = pre_plan.frequency
            elif product_id == self.env.ref('real_estate.confirmation_amount_product').id:
                params['confirmation_amount'] = value
                params['confirmation_amount_interval'] = pre_plan.interval
                params['confirmation_amount_frequency'] = pre_plan.frequency
            elif product_id == self.env.ref('real_estate.balloting_product').id:
                params['primary_amount'] = value
                params['primary_amount_interval'] = pre_plan.interval
                params['primary_amount_frequency'] = pre_plan.frequency
        return params


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
            if rec.product_id.id == rec.env.ref('real_estate.down_payment_product').id:
                if rec.frequency > 1:
                    raise ValidationError(_('Down Payment frequency should be 1'))

    @api.constrains('basis', 'value')
    def check_percentage_value(self):
        for rec in self:
            if rec.basis == 'percentage' and (rec.value < 0 or rec.value > 100):
                raise ValidationError(_(
                    'Value for "%s" must be between 0 and 100 when Basis is "Percentage" (got %.2f). '
                    'Use Basis "Fix" instead if you meant to enter a fixed amount.'
                ) % (rec.product_id.display_name, rec.value))
