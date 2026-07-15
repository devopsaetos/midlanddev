from odoo import fields, models, api


class FileMaintenanceExt(models.Model):
    _inherit = 'file'

    maintenance_exemption_history_ids = fields.One2many('maintenance.exemption.history', 'file_id')
    exemption_withdrawal_history_ids = fields.One2many('maintenance.exemption.withdrawal.history', 'file_id')


class MaintenanceExemptionHistory(models.Model):
    _name = 'maintenance.exemption.history'
    _description = 'Maintenance Exemption History'

    file_id = fields.Many2one('file')
    maintenance_exemption_id = fields.Many2one('maintenance.exemption.line')
    maintenance_exemption_batch_id = fields.Many2one('maintenance.exemption')
    product_id = fields.Many2one('product.product', string='Charge Type', related='maintenance_exemption_batch_id.product_id')
    exemption_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount')], related='maintenance_exemption_id.exemption_type')
    exemption_nature = fields.Selection([
        ('partial', 'Partial'),
        ('full', 'Full')], related='maintenance_exemption_id.exemption_nature')
    exemption_percent = fields.Float(related='maintenance_exemption_id.exemption_percent')
    exemption_amount = fields.Float(related='maintenance_exemption_id.exemption_amount')
    from_date = fields.Date(related='maintenance_exemption_id.from_date')
    to_date = fields.Date(related='maintenance_exemption_id.to_date')
    exemption_state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')], related='maintenance_exemption_id.exemption_state')


class MaintenanceExemptionWithdrawalHistory(models.Model):
    _name = 'maintenance.exemption.withdrawal.history'
    _description = 'Maintenance Exemption Withdrawal History'

    file_id = fields.Many2one('file')
    maintenance_exemption_withdrawal_id = fields.Many2one('maintenance.exemption.withdrawal.line')
    withdrawal_batch_id = fields.Many2one('maintenance.exemption.withdrawal')
    product_id = fields.Many2one('product.product', string='Charge Type', related='withdrawal_batch_id.product_id')
    from_date = fields.Date(related='maintenance_exemption_withdrawal_id.from_date')
    to_date = fields.Date(related='maintenance_exemption_withdrawal_id.to_date')
