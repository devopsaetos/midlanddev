from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubcontractPOWizard(models.TransientModel):
    _name = 'subcontract.purchase.wizard'
    _description = 'Create Purchase Order from Subcontract'

    subcontract_id = fields.Many2one('task.subcontract', string='Sub Contract')
    subcontractor_id = fields.Many2one('res.partner', string='Sub Contractor')
    line_ids = fields.One2many(
        'subcontract.purchase.wizard.line', 'wizard_id', string='Lines',
        default=lambda self: self._default_lines(),
    )

    @api.model
    def _default_lines(self):
        active_id = self._context.get('active_id')
        active_model = self._context.get('active_model')
        if active_model != 'task.subcontract' or not active_id:
            return []
        plan_lines = self.env['subtract.plan.products'].search([
            ('subcontract_id', '=', active_id),
        ])
        return [(0, 0, {
            'product_id': l.product_id.id,
            'name': l.name,
            'uom_id': l.uom_id.id,
            'available_qty': l.order_qty if l.order_qty else l.qty,
            'given_qty': l.qty,
            'rate': l.rate,
            'qty': l.qty,
            'value': l.value,
            'task_subcontract_line_id': l.id,
        }) for l in plan_lines if l.qty != l.order_qty]

    def create_purchase_order(self):
        self.ensure_one()
        active_id = self._context.get('active_id')
        subcontract = self.env['task.subcontract'].browse(active_id)

        lines_to_order = self.line_ids.filtered('check')
        if not lines_to_order:
            return {'type': 'ir.actions.act_window_close'}

        order_lines = [(0, 0, {
            'product_id': l.product_id.id,
            'name': l.name,
            'product_qty': l.qty,
            'price_unit': l.rate,
            'date_planned': fields.Datetime.now(),
            'product_uom': l.uom_id.id,
            'task_subcontract_id': subcontract.id,
            'subcontract_line_id': l.task_subcontract_line_id,
        }) for l in lines_to_order]

        purchase = self.env['purchase.order'].create({
            'partner_id': subcontract.assigned_to.id,
            'task_subcontract_id': subcontract.id,
            'project_id': subcontract.project_id.id,
            'task_id': subcontract.task_id.id,
            'company_id': subcontract.company_id.id,
            'order_line': order_lines,
        })

        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'purchase.order',
            'view_id': self.env.ref('purchase.purchase_order_form').id,
            'res_id': purchase.id,
            'target': 'new',
        }


class SubcontractPOWizardLine(models.TransientModel):
    _name = 'subcontract.purchase.wizard.line'
    _description = 'Subcontract Purchase Wizard Line'

    wizard_id = fields.Many2one('subcontract.purchase.wizard')
    check = fields.Boolean(string='Select', default=False)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    name = fields.Char(string='Description', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    qty = fields.Float(string='Quantity', default=1.0)
    given_qty = fields.Float(string='Given Qty', readonly=True)
    available_qty = fields.Integer(string='Available Qty', readonly=True)
    rate = fields.Float(string='Rate', readonly=True)
    value = fields.Float(string='Value', readonly=True)
    task_subcontract_line_id = fields.Integer(string='Subcontract Line Id')

    @api.constrains('qty')
    def _check_qty(self):
        for rec in self:
            if rec.qty > rec.available_qty:
                raise ValidationError(
                    _('Quantity cannot exceed the available quantity (%s).') % rec.available_qty
                )
