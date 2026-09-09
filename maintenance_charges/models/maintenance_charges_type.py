from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class MaintenanceChargesType(models.Model):
    _name = 'maintenance.charges.type'
    # 'tools.mixin' removed - it was provided by 'axiom_payment_report', which is
    # not available in this addons tree (dependency commented out in __manifest__.py).
    # 'mail.thread'/'mail.activity.mixin' added explicitly (matching the convention used
    # everywhere else in this project, e.g. change_unit_type.py) so tracking=True fields
    # and the <chatter/> widget in the form view keep working.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Maintenance Charges Type'

    name = fields.Char(tracking=True)
    society_id = fields.Many2one('society', 'Society', required=True, domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', required=True, domain="[('is_society','!=',True)]")
    sector_ids = fields.Many2many('sector')

    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)
    unit_type = fields.Selection([
        ('marla', 'Marla'),
        ('sq_feet', 'Sq. Feet'),
    ], tracking=True)

    maintenance_charges_type_line_ids = fields.One2many('maintenance.charges.type.lines', 'maintenance_charges_type_id')

    @api.onchange('society_id', 'phase_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_ids': [('phase_id', '=', self.phase_id.id)],
            }
        }


class MaintenanceChargesTypeLine(models.Model):
    _name = 'maintenance.charges.type.lines'
    _description = 'Maintenance Charges Type Lines'

    product_id = fields.Many2one('product.product', required=True)
    basis_on = fields.Selection([
        ('fix', 'Fix'),
        ('percentage', 'Percentage'),
    ], default='fix')
    value = fields.Float()
    amount = fields.Float()

    maintenance_charges_type_id = fields.Many2one('maintenance.charges.type')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Amount must be greater than 0 for charge type line "%s".') % rec.product_id.display_name)
