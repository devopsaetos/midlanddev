from odoo import api, fields, models, _


class TaskSubContract(models.Model):
    _name = 'task.subcontract'
    _description = 'Task Subcontract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(default=True)
    priority = fields.Selection([
        ('0', 'Low'), ('1', 'Normal'), ('2', 'High'),
    ], string='Priority', default='0')
    sequence = fields.Char(
        string='Sequence', readonly=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('task.subcontract'),
    )
    description = fields.Text(string='Description')
    subcontractor_job_order = fields.Boolean(string='Subcontractor Job Order')
    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        related='project_id.account_id',
    )
    assigned_to = fields.Many2one('res.partner', string='Sub Contractor', required=True,
                                   domain=[('supplier_rank', '>', 0)])
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    start_date = fields.Datetime(string='Starting Date', default=fields.Datetime.now)
    close_date = fields.Datetime(string='Ending Date')
    deadline = fields.Datetime(string='Deadline')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ('confirm', 'Confirmed'),
    ], string='State', copy=False, default='draft', tracking=True)
    check = fields.Boolean(string='Create Subtask')

    purchase_line_ids = fields.One2many('subtract.plan.products', 'subcontract_id', string='Purchase Order Lines')

    cost_sheet_count = fields.Integer(string='# Cost Sheets', compute='_compute_cost_sheet_count')
    subtask_count = fields.Integer(string='# Subtasks', compute='_compute_subtask_count')
    po_count = fields.Integer(string='# Purchase Orders', compute='_compute_po_count')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id and not self.purchase_line_ids:
            # Any existing Cost Sheet for this task is a valid material-list source to
            # pre-fill a new Sub Contract from, even one already linked to a prior Sub
            # Contract — a task's companion Cost Sheet only ever gets created together
            # with its Sub Contract (see create() below), so restricting this search to
            # "standalone" (task_subcontract_id=False) sheets meant the lines came up
            # empty for every task that already had one subcontract, which is the common
            # case, not the exception. Picking the most recent one (by id) if there are
            # several is a reasonable default; the fallback to Project Budget lines below
            # still applies when the task has no Cost Sheet at all yet.
            cost_sheet = self.env['task.cost.sheet'].search([
                ('task_id', '=', self.task_id.id),
            ], order='id desc', limit=1)
            if cost_sheet:
                self.purchase_line_ids = [(0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.name,
                    'uom_id': line.uom_id.id,
                    'qty': line.quantity,
                    'rate': line.unit_price,
                }) for line in cost_sheet.material_task_cost_line_ids]
            else:
                # No Cost Sheet exists yet for this task at all — fall back to the
                # Project Budget's planned material lines for this task, if any.
                budget_lines = self.env['project.budget.material.line'].search([
                    ('task_id', '=', self.task_id.id),
                ])
                self.purchase_line_ids = [(0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.name,
                    'uom_id': line.uom_id.id,
                    'qty': line.quantity,
                    'rate': line.rate,
                }) for line in budget_lines]

    def _compute_cost_sheet_count(self):
        data = self.env['task.cost.sheet']._read_group(
            [('task_subcontract_id', 'in', self.ids)], ['task_subcontract_id'], ['__count'],
        )
        counts = {rec.id: count for rec, count in data}
        for rec in self:
            rec.cost_sheet_count = counts.get(rec.id, 0)

    def _compute_subtask_count(self):
        data = self.env['project.task']._read_group(
            [('task_subcontract_id', 'in', self.ids)], ['task_subcontract_id'], ['__count'],
        )
        counts = {rec.id: count for rec, count in data}
        for rec in self:
            rec.subtask_count = counts.get(rec.id, 0)

    def _compute_po_count(self):
        data = self.env['purchase.order']._read_group(
            [('task_subcontract_id', 'in', self.ids)], ['task_subcontract_id'], ['__count'],
        )
        counts = {rec.id: count for rec, count in data}
        for rec in self:
            rec.po_count = counts.get(rec.id, 0)

    def action_validate(self):
        self.write({'state': 'valid'})

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_open_create_po_wizard(self):
        self.ensure_one()
        action = self.env.ref('construction_subcontracting.action_create_purchase_order').read()[0]
        action['context'] = {'active_id': self.id, 'active_model': 'task.subcontract'}
        return action

    def po_button_view(self):
        self.ensure_one()
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'domain': [('task_subcontract_id', '=', self.id)],
        }

    def button_view_costsheet(self):
        self.ensure_one()
        return {
            'name': _('Cost Sheets'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'task.cost.sheet',
            'domain': [('task_subcontract_id', '=', self.id)],
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence') or vals['sequence'] == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('task.subcontract')
        records = super().create(vals_list)
        for rec in records:
            if rec.check and rec.task_id:
                self.env['project.task'].create({
                    'parent_id': rec.task_id.id,
                    'name': rec.name,
                    'project_id': rec.project_id.id,
                })
            self.env['task.cost.sheet'].create({
                'task_subcontract_id': rec.id,
                'name': rec.name + ' Cost Sheet',
                'project_id': rec.project_id.id,
                'company_id': rec.company_id.id,
                'task_id': rec.task_id.id,
            })
        return records


class SubContractPurchaseLine(models.Model):
    _name = 'subtract.plan.products'
    _description = 'Subcontract Purchase Line'

    subcontract_id = fields.Many2one('task.subcontract', string='Sub Contract')
    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Char(string='Description')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    qty = fields.Integer(string='Quantity', default=1)
    rate = fields.Float(string='Rate', default=1.0)
    value = fields.Float(string='Value', compute='_compute_value', store=True)
    order_qty = fields.Float(string='Ordered Qty')

    @api.depends('qty', 'rate')
    def _compute_value(self):
        for rec in self:
            rec.value = rec.qty * rec.rate

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.name = self.product_id.name


class TaskCostSheetSubcontractExt(models.Model):
    _inherit = 'task.cost.sheet'

    task_subcontract_id = fields.Many2one('task.subcontract', string='Subcontract')

    def write(self, vals):
        res = super().write(vals)
        if 'material_task_cost_line_ids' in vals:
            for rec in self.filtered('task_subcontract_id'):
                rec._sync_subcontract_purchase_lines()
        return res

    def _sync_subcontract_purchase_lines(self):
        self.ensure_one()
        subcontract = self.task_subcontract_id
        existing_by_product = {
            line.product_id.id: line for line in subcontract.purchase_line_ids
        }
        seen_product_ids = set()
        for cs_line in self.material_task_cost_line_ids:
            seen_product_ids.add(cs_line.product_id.id)
            match = existing_by_product.get(cs_line.product_id.id)
            if match:
                # Never touch a line that already has a PO qty against it — overwriting
                # qty/rate here would silently desync it from the real purchase order.
                if not match.order_qty:
                    match.write({
                        'name': cs_line.description or cs_line.product_id.name,
                        'uom_id': cs_line.uom_id.id,
                        'qty': cs_line.quantity,
                        'rate': cs_line.unit_price,
                    })
            else:
                self.env['subtract.plan.products'].create({
                    'subcontract_id': subcontract.id,
                    'product_id': cs_line.product_id.id,
                    'name': cs_line.description or cs_line.product_id.name,
                    'uom_id': cs_line.uom_id.id,
                    'qty': cs_line.quantity,
                    'rate': cs_line.unit_price,
                })
        # Drop lines whose product was removed from the cost sheet — but only if
        # nothing has been ordered against them yet.
        for product_id, line in existing_by_product.items():
            if product_id not in seen_product_ids and not line.order_qty:
                line.unlink()
