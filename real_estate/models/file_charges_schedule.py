from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class FileChargesSchedule(models.Model):
    _name = 'file.charges.schedule'
    _description = 'File Charges Schedule'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')], default="housing_society")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, string="Company")
    name = fields.Char(required=True)
    applicable_on = fields.Selection([
        ('map', 'Map'),
        ('swap', 'Swap'),
        ('restore', 'Restore File'),
        ('demarcation', 'Demarcation'),
        ('allotment', 'Allotment'),
    ])
    date_from = fields.Date()
    date_to = fields.Date()
    society_id = fields.Many2one('society', string='Society', domain="[('is_society', '=', True)]")
    phase_id = fields.Many2one('society', string='Phase', domain="[('is_society', '!=', True)]")

    calculation_basis = fields.Selection([
        ('marla', 'Per Marla'),
        ('sq_feet', 'Per Sq. Feet'),
    ])
    fee_calculation = fields.Selection([
        ('fix', 'Fix'),
        ('variable', 'Variable'),
    ])
    amount = fields.Float()

    charges_schedule_line_ids = fields.One2many('file.charges.schedule.line', 'charges_schedule_id')
    required_taxes_line_ids = fields.One2many('required.taxes.line', 'file_charges_schedule_id')
    required_documents_line_ids = fields.One2many('required.documents.line', 'file_charges_schedule_id')
    other_charges_line_ids = fields.One2many('other.charges', 'file_charges_schedule_id')

    @api.constrains('required_taxes_line_ids', 'other_charges_line_ids')
    def _check_duplicate_lines(self):
        for schedule in self:
            self._check_duplicate(schedule.required_taxes_line_ids, 'required taxes')
            self._check_duplicate(schedule.other_charges_line_ids, 'other charges')

    def _check_duplicate(self, line_ids, line_type):
        seen = set()
        for line in line_ids:
            key = (line.category_id.id, tuple(line.unit_category_type_ids.ids), line.product_id.id)
            if key in seen:
                raise ValidationError(
                    _('Duplicate %s line detected with the same Category, Product, and Unit Category combination.') % line_type
                )
            seen.add(key)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if self.filtered(lambda c: c.date_to and c.date_from > c.date_to):
            raise ValidationError(_('Date to must be greater than date from.'))

    @api.onchange('society_id', 'phase_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)]
            }
        }

    @api.model
    def unlink(self):
        raise ValidationError(_('You are not allowed to delete File Charges Schedule records.'))


class FileChargesScheduleLine(models.Model):
    _name = 'file.charges.schedule.line'
    _description = 'File Charges Schedule Line'

    area_from = fields.Integer()
    area_to = fields.Integer()
    amount = fields.Float()

    charges_schedule_id = fields.Many2one('file.charges.schedule')


class RequiredTaxesLineExt(models.Model):
    _inherit = 'required.taxes.line'

    file_charges_schedule_id = fields.Many2one('file.charges.schedule', tracking=True)
    category_id = fields.Many2one('plot.category', string='Category', tracking=True)
    unit_category_type_ids = fields.Many2many('unit.category.type', string='Product', tracking=True)


class RequiredDocumentsExt(models.Model):
    _inherit = 'required.documents.line'

    file_charges_schedule_id = fields.Many2one('file.charges.schedule', string="File Charges Schedule", tracking=True)
    category_id = fields.Many2one('plot.category', string='Category', tracking=True)
    unit_category_type_ids = fields.Many2many('unit.category.type', string='Product', tracking=True)


class OtherChargesExt(models.Model):
    _inherit = 'other.charges'

    file_charges_schedule_id = fields.Many2one('file.charges.schedule', string="File Charges Schedule", tracking=True)
    category_id = fields.Many2one('plot.category', string='Category', tracking=True)
    unit_category_type_ids = fields.Many2many('unit.category.type', string='Product', tracking=True)
