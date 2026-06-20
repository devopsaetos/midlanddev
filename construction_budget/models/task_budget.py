from odoo import api, fields, models


class TaskBudget(models.Model):
    _name = 'task.budget'
    _description = 'Task Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'

    sequence = fields.Char(string='Code', readonly=True, copy=False, default='New')
    name = fields.Char(string='Name', required=True, tracking=True)
    task_id = fields.Many2one('project.task', string='Task')
    project_id = fields.Many2one(
        'project.project', string='Project',
        related='project_budget_id.project_id', store=True, readonly=False,
    )
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='State', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    project_budget_id = fields.Many2one('project.budget', string='Project Budget')
    material_ids = fields.One2many('task.budget.material.line', 'task_budget_id', string='Materials')
    service_ids = fields.One2many('task.budget.service.line', 'task_budget_id', string='Services')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        active_id = self._context.get('active_id')
        if active_id:
            res['task_id'] = active_id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', 'New') == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('task.budget.seq')
            if not vals.get('name'):
                task = self.env['project.task'].browse(
                    vals.get('task_id') or self._context.get('active_id')
                )
                if task:
                    vals['name'] = 'BFQ ' + task.name
        return super().create(vals_list)

    def action_confirm(self):
        return self.write({'state': 'confirmed'})

    def action_approved(self):
        return self.write({'state': 'approved'})

    def action_reject(self):
        return self.write({'state': 'rejected'})

    def action_reset_to_draft(self):
        return self.write({'state': 'draft'})


class TaskBudgetMaterialLine(models.Model):
    _name = 'task.budget.material.line'
    _description = 'Task Budget Material Line'

    task_budget_id = fields.Many2one('task.budget', string='Task Budget')
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
    uom_id = fields.Many2one('uom.uom', string='UoM', related='product_id.uom_id', store=True)
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


class TaskBudgetServiceLine(models.Model):
    _name = 'task.budget.service.line'
    _description = 'Task Budget Service Line'

    task_budget_id = fields.Many2one('task.budget', string='Task Budget')
    category_id = fields.Many2one('product.category', string='Product Category', ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Product',
        domain="[('type', '=', 'service'), ('categ_id', '=', category_id)]",
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
