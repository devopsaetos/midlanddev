from odoo import api, fields, models


class ProjectBudgetMaterialLine(models.Model):
    _name = 'project.budget.material.line'
    _description = 'Project Budget Material Line'

    project_material_id = fields.Many2one('project.budget', string='Project Budget')
    task_id = fields.Many2one('project.task', string='Task')
    category_id = fields.Many2one('product.category', string='Product Category', ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="[('type', '=', 'consu'), ('categ_id', '=', category_id)]",
    )
    name = fields.Char(string='Description')
    rate = fields.Float(string='Rate')
    value = fields.Float(string='Value', compute='_compute_value', store=True)
    number = fields.Float(string='Number', default=1)
    length = fields.Float(string='Length', default=1)
    width = fields.Float(string='Width', default=1)
    height = fields.Float(string='Height', default=1)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    quantity = fields.Float(
        string='Qty', compute='_compute_quantity', inverse='_inverse_quantity', store=True,
    )

    @api.depends('number', 'length', 'width', 'height')
    def _compute_quantity(self):
        for rec in self:
            rec.quantity = rec.number * rec.length * rec.width * rec.height

    def _inverse_quantity(self):
        for rec in self:
            rec.number = rec.quantity

    @api.depends('quantity', 'rate')
    def _compute_value(self):
        for rec in self:
            rec.value = rec.quantity * rec.rate

    @api.onchange('category_id')
    def _onchange_category_id(self):
        self.product_id = False
