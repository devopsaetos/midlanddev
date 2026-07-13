from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceExemptionWithdrawal(models.Model):
    _name = 'maintenance.exemption.withdrawal'
    _description = 'Maintenance Exemption Withdrawal'
    # 'tools.mixin' removed - it was provided by 'axiom_payment_report', which is not available
    # in this addons tree (see maintenance_charges for the same fix). 'mail.thread'/
    # 'mail.activity.mixin' added so the <chatter/> widget in the form view keeps working.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'withdrawal_batch_no'

    withdrawal_batch_no = fields.Char(default='New')
    product_id = fields.Many2one('product.product', string='Charge Type', domain=lambda self: self._product_domain())
    withdrawal_line_ids = fields.One2many('maintenance.exemption.withdrawal.line',
                                          'maintenance_exemption_withdrawal_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit_approve', 'Submit To Approve'),
        ('approved', 'Approved'), ('cancel', 'Cancel')], default='draft')

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete record that is not in draft state!'))

        return super(MaintenanceExemptionWithdrawal, self).unlink()

    @api.model
    def _product_domain(self):
        return [('id', 'in', self.env['maintenance.charges.type.lines'].sudo().search([]).mapped('product_id.id'))]

    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['withdrawal_batch_no'] = self.env['ir.sequence'].next_by_code(
                'maintenance.exemption.withdrawal') or 'New'
        return super(MaintenanceExemptionWithdrawal, self).create(vals)

    def button_submit(self):
        for rec in self:
            rec.write({'state': 'submit_approve'})

    def button_approve(self):
        for rec in self:
            rec.write({'state': 'approved'})
            if rec.withdrawal_line_ids:
                for line in rec.withdrawal_line_ids:
                    if line.file_id:
                        line.file_id.exemption_withdrawal_history_ids = [
                            (0, 0, {'maintenance_exemption_withdrawal_id': line.id,
                                    "withdrawal_batch_id": line.maintenance_exemption_withdrawal_id.id})]

                    if line.maintenance_exemption_id:
                        line.maintenance_exemption_id.write({'exemption_state': 'inactive'})

    def button_cancel(self):
        for rec in self:
            rec.write({'state': 'cancel'})


class MaintenanceExemptionWithdrawalLine(models.Model):
    _name = 'maintenance.exemption.withdrawal.line'
    _description = 'Maintenance Exemption Withdrawal Line'
    _rec_name = 'exemption_withdrawal_no'

    maintenance_exemption_withdrawal_id = fields.Many2one('maintenance.exemption.withdrawal')

    exemption_withdrawal_no = fields.Char(default='New')
    society_id = fields.Many2one('society', string='Society')
    phase_id = fields.Many2one('society', string='Phase')
    sector_id = fields.Many2one('sector', string='Sector')
    street_id = fields.Many2one('street', string='Street')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type', string="Product")
    size_id = fields.Many2one('unit.size', string='Size')
    inventory_id = fields.Many2one('plot.inventory', string='Plot No')
    file_id = fields.Many2one('file')
    maintenance_exemption_id = fields.Many2one('maintenance.exemption.line',
                                               domain="['|', ('inventory_id', '=', inventory_id), ('file_id', '=', file_id), ('exemption_state', '=', 'active')]")
    from_date = fields.Date(related='maintenance_exemption_id.from_date')
    to_date = fields.Date(related='maintenance_exemption_id.to_date')

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
                # rec.maintenance_exemption_id = self.env['maintenance.exemption.line'].search(
                #     [('maintenance_exemption_id.state', '=', 'approved'), ('file_id', '=', rec.file_id.id)], limit=1)
            elif rec.inventory_id:
                rec.society_id = rec.inventory_id.society_id
                rec.phase_id = rec.inventory_id.phase_id
                rec.sector_id = rec.inventory_id.sector_id
                rec.street_id = rec.inventory_id.street_id
                rec.category_id = rec.inventory_id.category_id
                rec.unit_category_type_id = rec.inventory_id.unit_category_type_id
                rec.size_id = rec.inventory_id.size_id
                rec.file_id = self.env['file'].search([('inventory_id', '=', rec.inventory_id.id)])
                # rec.maintenance_exemption_id = self.env['maintenance.exemption.line'].search(
                    # [('maintenance_exemption_id.state', '=', 'approved'), ('inventory_id', '=', rec.inventory_id.id)],
                    # limit=1)

    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['exemption_withdrawal_no'] = self.env['ir.sequence'].next_by_code(
                'maintenance.exemption.withdrawal.line') or 'New'
        return super(MaintenanceExemptionWithdrawalLine, self).create(vals)

    def unlink(self):
        for rec in self:
            if rec.maintenance_exemption_withdrawal_id.state != 'draft':
                raise ValidationError(_('You cannot delete record that is not in draft state!'))

        return super(MaintenanceExemptionWithdrawalLine, self).unlink()
