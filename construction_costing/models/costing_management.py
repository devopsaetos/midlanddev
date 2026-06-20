from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TaskCostSheet(models.Model):
    _name = 'task.cost.sheet'
    _description = 'Task Cost Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'

    name = fields.Char(string='Name')
    sequence = fields.Char(
        string='Sequence', readonly=True, copy=False, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('task.cost.sheet'),
    )
    project_id = fields.Many2one('project.project', string='Project')
    # account_id is the analytic account field on project.project in Odoo 19
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        related='project_id.account_id',
    )
    task_issue_customer_id = fields.Many2one('res.partner', string='Job Issue Customer')
    close_date = fields.Datetime(string='Close Date', readonly=True)
    create_by_id = fields.Many2one(
        'res.users', string='Created By',
        default=lambda self: self.env.user, readonly=True,
    )

    material_task_cost_line_ids = fields.One2many(
        'task.cost.line', 'material_task_cost_sheet_id', string='Material Job Cost Lines',
    )
    bills_line_ids = fields.One2many(
        'task.cost.line', 'labour_task_cost_sheet_id', string='Labour Job Cost Lines',
    )
    overhead_task_cost_line_ids = fields.One2many(
        'task.cost.overhead', 'overhead_task_cost_sheet_id', string='Overhead Job Cost Lines',
    )

    total_material_cost = fields.Float(
        compute='_compute_total_material_cost', string='Total Material Cost', store=True,
    )
    total_labour_cost = fields.Float(
        compute='_compute_total_labour_cost', string='Total Labour Cost', store=True,
    )
    total_overhead_cost = fields.Float(
        compute='_compute_total_overhead_cost', string='Total Overhead Cost', store=True,
    )
    total_cost = fields.Float(
        compute='_compute_total_cost', string='Total Cost', store=True,
    )

    task_cost_description = fields.Text(string='Job Cost Description')
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id', string='Currency', store=True,
    )
    stage = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('approve', 'Approved'),
        ('done', 'Done'),
    ], string='Stage', copy=False, default='draft', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
    )
    sale_reference = fields.Text(string='Description Sale Reference')
    task_id = fields.Many2one('project.task', string='Task', required=True)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            existing = self.env['task.cost.sheet'].search([
                ('project_id', '=', self.project_id.id),
                ('task_id', '=', self.task_id.id),
            ])
            if existing:
                raise UserError(_('You cannot create more than one Cost Sheet for the same task.'))
            self.name = '%s - Cost Sheet' % self.task_id.name

    def purchase_order_line_button(self):
        self.ensure_one()
        return {
            'name': _('Purchase Order Lines'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'purchase.order.line',
            'domain': [('job_cost_sheet_id', '=', self.id)],
        }

    def invoice_line_button(self):
        self.ensure_one()
        return {
            'name': _('Invoice Lines'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'account.move.line',
            'domain': [('job_cost_sheet_id', '=', self.id)],
        }

    def action_confirm(self):
        return self.write({'stage': 'confirm'})

    def action_approve(self):
        return self.write({'stage': 'approve'})

    def action_done(self):
        return self.write({'stage': 'done', 'close_date': fields.Datetime.now()})

    @api.depends('material_task_cost_line_ids.subtotal')
    def _compute_total_material_cost(self):
        for rec in self:
            rec.total_material_cost = sum(rec.material_task_cost_line_ids.mapped('subtotal'))

    @api.depends('bills_line_ids.subtotal')
    def _compute_total_labour_cost(self):
        for rec in self:
            rec.total_labour_cost = sum(rec.bills_line_ids.mapped('subtotal'))

    @api.depends(
        'material_task_cost_line_ids.subtotal',
        'bills_line_ids.subtotal',
        'project_id.rate',
    )
    def _compute_total_overhead_cost(self):
        for rec in self:
            rate = rec.project_id.rate or 0.0
            all_subtotals = (
                rec.material_task_cost_line_ids.mapped('subtotal')
                + rec.bills_line_ids.mapped('subtotal')
            )
            rec.total_overhead_cost = sum(s * (rate / 100) for s in all_subtotals)

    @api.depends('total_material_cost', 'total_labour_cost', 'total_overhead_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.total_material_cost + rec.total_labour_cost + rec.total_overhead_cost

    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id

    @api.onchange('bills_line_ids', 'material_task_cost_line_ids')
    def _onchange_calc_overhead(self):
        if not self.project_id.overhead_type or not self.project_id.rate:
            return
        lines = []
        source = (
            self.bills_line_ids if self.project_id.overhead_type == 'labour'
            else self.material_task_cost_line_ids
        )
        for line in source:
            lines.append((0, 0, {
                'date': line.date or False,
                'product_id': line.product_id.id or False,
                'description': line.description or False,
                'quantity': line.quantity or False,
                'uom_id': line.uom_id.id or False,
                'job_type': self.project_id.overhead_type,
                'over_head_value': line.subtotal * (self.project_id.rate / 100),
            }))
        self.overhead_task_cost_line_ids = lines


class TaskCostLine(models.Model):
    _name = 'task.cost.line'
    _description = 'Task Cost Sheet Line'

    material_task_cost_sheet_id = fields.Many2one('task.cost.sheet', string='Material Job Cost Sheet')
    labour_task_cost_sheet_id = fields.Many2one('task.cost.sheet', string='Labour Job Cost Sheet')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Text(string='Description')
    reference = fields.Char(string='Reference')
    quantity = fields.Float(string='Quantity')
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_price = fields.Float(string='Cost/Unit Price', default=1.0)
    actual_purchase_qty = fields.Float(string='Actual Purchased Quantity', default=0.0)
    subtotal = fields.Float(compute='_compute_subtotal', string='Sub Total', store=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id', string='Currency', store=True,
    )
    job_type = fields.Selection([
        ('material', 'Material'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead'),
    ], string='Job Cost Type')
    hours = fields.Float(string='Hours')
    actual_timesheet_hours = fields.Float(string='Actual Timesheet Hours')
    over_head_value = fields.Float(string='Overhead Value')
    total_over_head_value = fields.Float(string='Total Overhead')

    @api.depends('quantity', 'unit_price', 'hours')
    def _compute_subtotal(self):
        for line in self:
            if line.hours:
                line.subtotal = line.hours * line.unit_price
            else:
                line.subtotal = line.quantity * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.uom_id = self.product_id.uom_id
        self.description = self.product_id.name
        self.unit_price = self.product_id.lst_price

    @api.depends('material_task_cost_sheet_id.company_id', 'labour_task_cost_sheet_id.company_id')
    def _compute_currency_id(self):
        for line in self:
            company = (
                line.material_task_cost_sheet_id.company_id
                or line.labour_task_cost_sheet_id.company_id
                or self.env.company
            )
            line.currency_id = company.currency_id


class TaskCostOverHead(models.Model):
    _name = 'task.cost.overhead'
    _description = 'Cost Sheet Overhead Line'

    overhead_task_cost_sheet_id = fields.Many2one('task.cost.sheet', string='Overhead Job Cost Sheet')
    project_id = fields.Many2one('project.project', string='Project')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Text(string='Description')
    reference = fields.Char(string='Reference')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_price = fields.Float(string='Cost/Unit Price', default=1.0)
    subtotal = fields.Float(string='Sub Total')
    job_type = fields.Selection([
        ('material', 'Material'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead'),
    ], string='Job Cost Type')
    hours = fields.Float(string='Hours', default=0.0)
    actual_timesheet_hours = fields.Float(string='Actual Timesheet Hours', default=0.0)
    over_head_value = fields.Float(string='Overhead Value')
    total_over_head_value = fields.Float(string='Total Overhead')
