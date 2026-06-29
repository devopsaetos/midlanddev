from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class DealPack(models.Model):
    _name = 'deal.pack'
    _description = 'Deal Pack'

    deal_pack_name = fields.Char(string='Name')
    name = fields.Char(copy=False, readonly=True, index=True, tracking=True, default=lambda self: _('New'))
    start_date = fields.Date('Start date', required=True, tracking=True,
                             default=fields.Date.today())
    end_date = fields.Date('End date', required=True, tracking=True, default=fields.Date.today())
    launch_type = fields.Selection([
        ('pre_launch', 'Pre Launch'),
        ('on_launch', 'On Launch'),
        ('post_launch', 'Post Launch'),
    ])
    state = fields.Selection([('draft', 'Draft'),
                              ('approve', 'Approve'),
                              ('cancel', 'Cancel')], default='draft')
    total_quantity = fields.Integer(compute='_compute_total', store=True)

    deal_pack_lines_ids = fields.One2many('deal.pack.lines', 'deal_pack_id')

    def approve_deal_pack(self):
        for rec in self:
            if not rec.deal_pack_lines_ids:
                raise ValidationError(_('Add at least one line before approving'))
            rec.state = 'approve'

    def cancel_deal_pack(self):
        for rec in self:
            rec.state = 'cancel'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('deal.pack') or _('New')
        result = super().create(vals_list)
        return result

    @api.depends('deal_pack_lines_ids.quantity')
    def _compute_total(self):
        for rec in self:
            rec.total_quantity = sum(rec.deal_pack_lines_ids.mapped('quantity'))

    @api.constrains('start_date', 'end_date')
    def check_date(self):
        for rec in self:
            if rec.end_date < rec.start_date:
                raise ValidationError(
                    _("End date can't be in past"))

    @api.depends('name', 'deal_pack_name')
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.name and record.name != 'New':
                name = "%s / %s" % (record.name, record.deal_pack_name)
            result.append((record.id, name))
        return result

    def unlink(self):
        for rec in self:
            if rec.state == 'approve':
                raise ValidationError(_('You cannot delete a record once it is approved.'))
        return super(DealPack, self).unlink()


class DealPackLines(models.Model):
    _name = 'deal.pack.lines'
    _description = 'Deal Pack line'

    sector_id = fields.Many2one('sector', tracking=True)
    category_id = fields.Many2one('plot.category', 'Category', tracking=True)
    unit_category_type_id = fields.Many2one('unit.category.type')
    quantity = fields.Integer()

    deal_pack_id = fields.Many2one('deal.pack')

    @api.constrains('quantity')
    def check_quantity(self):
        for rec in self:
            if rec.quantity == 0:
                raise ValidationError(
                    _("Quantity can't be 0"))