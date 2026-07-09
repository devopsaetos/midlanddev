from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectBudget(models.Model):
    _name = 'project.budget'
    _description = 'Project Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence desc'

    sequence = fields.Char(string='Code', readonly=True, copy=False, default='New')
    name = fields.Char(string='Name', required=True, tracking=True)
    project_id = fields.Many2one('project.project', string='Project', required=True)
    customer_id = fields.Many2one(
        'res.partner', string='Customer',
        related='project_id.partner_id', readonly=True,
    )
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='State', default='draft', tracking=True)
    budget_from_task = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Get Budget from Task', default='no')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    task_budget_ids = fields.One2many('task.budget', 'project_budget_id', string='Task Budgets')
    material_ids = fields.One2many(
        'project.budget.material.line', 'project_material_id', string='Materials',
    )
    task_ids = fields.One2many('project.budget.tasks', 'project_budget_id', string='Tasks')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', 'New') == 'New':
                vals['sequence'] = self.env['ir.sequence'].next_by_code('project.budget.seq')
        return super().create(vals_list)

    @api.model
    def default_get(self, field_names):
        res = super().default_get(field_names)
        project_id = self._context.get('active_id')
        if project_id:
            res['project_id'] = project_id
        return res

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            count = self.env['project.budget'].search_count(
                [('project_id', '=', self.project_id.id)]
            )
            if count > 0:
                raise UserError(_('You cannot create more than one Budget for the same Project.'))

    @api.onchange('budget_from_task')
    def _onchange_budget_from_task(self):
        # Pulls from task.cost.sheet (actual costed material/labour/overhead per task),
        # not the separate task.budget model — task.budget is a distinct, disconnected
        # budgeting concept that in practice never gets created/approved, so this always
        # produced empty rows. Cost Sheet is the record that's actually kept up to date.
        if self.budget_from_task == 'yes':
            cost_sheets = self.env['task.cost.sheet'].search([
                ('project_id', '=', self.project_id.id),
            ])
            materials = []
            tasks = []
            for cs in cost_sheets:
                for line in cs.material_task_cost_line_ids:
                    materials.append((0, 0, {
                        'task_id': cs.task_id.id,
                        'product_id': line.product_id.id,
                        'uom_id': line.uom_id.id,
                        'number': line.quantity,
                        'rate': line.unit_price,
                    }))
                tasks.append((0, 0, {
                    'task_id': cs.task_id.id,
                    'material_value': cs.total_material_cost,
                    'service_value': cs.total_labour_cost,
                    'ovherhead_value': cs.total_overhead_cost,
                    'total_value': cs.total_cost,
                }))
            self.material_ids = materials
            self.task_ids = tasks
        else:
            self.material_ids = False
            self.task_ids = False

    def action_confirm(self):
        return self.write({'state': 'confirmed'})

    def action_approved(self):
        return self.write({'state': 'approved'})

    def action_reject(self):
        return self.write({'state': 'rejected'})

    def action_reset_to_draft(self):
        return self.write({'state': 'draft'})


class ProjectBudgetTasks(models.Model):
    _name = 'project.budget.tasks'
    _description = 'Project Budget Task Line'

    project_budget_id = fields.Many2one('project.budget', string='Project Budget')
    task_id = fields.Many2one('project.task', string='Task')
    material_value = fields.Float(string='Material')
    service_value = fields.Float(string='Service')
    ovherhead_value = fields.Float(string='Overhead')  # keep original spelling — avoids DB column rename
    total_value = fields.Float(string='Total')

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            cost_sheet = self.env['task.cost.sheet'].search(
                [('task_id', '=', self.task_id.id)], limit=1,
            )
            if cost_sheet:
                self.material_value = cost_sheet.total_material_cost
                self.service_value = cost_sheet.total_labour_cost
                self.ovherhead_value = cost_sheet.total_overhead_cost
                self.total_value = cost_sheet.total_cost

    def detail_task_budgeting(self):
        self.ensure_one()
        cost_sheet = self.env['task.cost.sheet'].search(
            [('task_id', '=', self.task_id.id)], limit=1,
        )
        return {
            'name': _('Task Cost Sheet'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'task.cost.sheet',
            'target': 'new',
            'res_id': cost_sheet.id,
            'context': {'default_task_id': self.task_id.id},
        }


class ProjectBudgetProjectExt(models.Model):
    _inherit = 'project.project'

    budget_count = fields.Integer(string='# Budgets', compute='_compute_budget_count')

    def _compute_budget_count(self):
        data = self.env['project.budget']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count'],
        )
        counts = {project.id: count for project, count in data}
        for rec in self:
            rec.budget_count = counts.get(rec.id, 0)

    def action_create_project_budget(self):
        self.ensure_one()
        if self.budget_count > 0:
            raise UserError(_('You cannot create more than one Budget for the same Project.'))
        view_id = self.env.ref('construction_budget.project_budget_view_form').id
        return {
            'name': _('Project Budget'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'res_model': 'project.budget',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }

    def button_view_project_budget(self):
        self.ensure_one()
        return {
            'name': _('Project Budget'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'project.budget',
            'domain': [('project_id', '=', self.id)],
            'context': dict(self._context),
        }
