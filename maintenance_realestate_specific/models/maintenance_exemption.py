from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceExemption(models.Model):
    _name = 'maintenance.exemption'
    _description = 'Maintenance Exemption'
    # 'tools.mixin' removed - it was provided by 'axiom_payment_report', which is not available
    # in this addons tree (see maintenance_charges for the same fix). 'mail.thread'/
    # 'mail.activity.mixin' added so the <chatter/> widget in the form view keeps working.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'exemption_batch_no'

    exemption_batch_no = fields.Char(default='New')
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    exemption_line_ids = fields.One2many('maintenance.exemption.line', 'maintenance_exemption_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit_approve', 'Submit To Approve'),
        ('approved', 'Approved'), ('cancel', 'Cancel')], default='draft')

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record that is not in draft state!'))

        return super(MaintenanceExemption, self).unlink()

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def create(self, vals):
        if vals.get('exemption_batch_no', 'New') == 'New':
            vals['exemption_batch_no'] = self.env['ir.sequence'].next_by_code('maintenance.exemption') or 'New'
        return super(MaintenanceExemption, self).create(vals)

    def button_submit(self):
        for rec in self:
            if rec.exemption_line_ids:
                for line in rec.exemption_line_ids:
                    if line.file_id:
                        file_history_line = self.env['maintenance.exemption.history'].search([('file_id', '=', line.file_id.id), ('exemption_state', '=', 'active'), ('product_id', '=', rec.product_id.id)])
                        if file_history_line:
                            raise ValidationError(_('You cannot add more than one exemption on this file %s!' % line.file_id.name))
            rec.write({'state': 'submit_approve'})

    def button_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})
            if rec.exemption_line_ids:
                for line in rec.exemption_line_ids:
                    if line.exemption_state == 'active':
                        line.file_id.maintenance_exemption_history_ids = [(0, 0, {'maintenance_exemption_id': line.id,
                                                                                  "maintenance_exemption_batch_id": line.maintenance_exemption_id.id})]

    def button_cancel(self):
        for rec in self:
            rec.write({'state': 'cancel'})


class MaintenanceExemptionLine(models.Model):
    _name = 'maintenance.exemption.line'
    _description = 'Maintenance Exemption Line'
    _rec_name = 'exemption_no'

    maintenance_exemption_id = fields.Many2one('maintenance.exemption')
    exemption_no = fields.Char(default='New')
    society_id = fields.Many2one('society', string='Society')
    phase_id = fields.Many2one('society', string='Phase')
    sector_id = fields.Many2one('sector', string='Sector')
    street_id = fields.Many2one('street', string='Street')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    size_id = fields.Many2one('unit.size', string='Size')
    inventory_id = fields.Many2one('plot.inventory', string='Plot No')
    file_id = fields.Many2one('file')
    exemption_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount')])
    exemption_nature = fields.Selection([
        ('partial', 'Partial'),
        ('full', 'Full')])
    exemption_percent = fields.Float()
    exemption_amount = fields.Float()
    from_date = fields.Date()
    to_date = fields.Date()
    exemption_state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')], default='active')

    @api.onchange('file_id', 'inventory_id')
    def fetch_details(self):
        for rec in self:
            if rec.file_id:
                rec.society_id = rec.file_id.society_id
                rec.phase_id = rec.file_id.phase_id
                rec.sector_id = rec.file_id.sector_id
                rec.street_id = rec.file_id.street_id
                rec.category_id = rec.file_id.category_id
                rec.unit_category_type_id = rec.file_id.unit_category_type_id
                rec.size_id = rec.file_id.size_id
                rec.inventory_id = rec.file_id.inventory_id
            elif rec.inventory_id:
                rec.society_id = rec.inventory_id.society_id
                rec.phase_id = rec.inventory_id.phase_id
                rec.sector_id = rec.inventory_id.sector_id
                rec.street_id = rec.inventory_id.street_id
                rec.category_id = rec.inventory_id.category_id
                rec.unit_category_type_id = rec.inventory_id.unit_category_type_id
                rec.size_id = rec.inventory_id.size_id
                rec.file_id = self.env['file'].search([('inventory_id', '=', rec.inventory_id.id)])

    def create(self, vals):
        if vals.get('exemption_no', 'New') == 'New':
            vals['exemption_no'] = self.env['ir.sequence'].next_by_code('maintenance.exemption.line') or 'New'
        return super(MaintenanceExemptionLine, self).create(vals)

    def unlink(self):
        for rec in self:
            if rec.exemption_state != 'inactive':
                raise ValidationError(_('You cannot delete record that is in active state!'))

        return super(MaintenanceExemptionLine, self).unlink()
