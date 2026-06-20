from odoo import models, fields, _, api


class LegalDispute(models.Model):
    _name = 'legal.dispute'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Legal Dispute'
    _rec_name = 'dispute_seq'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society'),
    ])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'In Process'),
        ('resolved', 'Resolved')], default='draft', tracking=True)
    dispute_seq = fields.Char('Dispute Sequence', required=True, copy=False, readonly=True, index=True,
                              default=lambda self: _('New'))
    dispute_date = fields.Date('Dispute Date', required=True, tracking=True)
    filed_by = fields.Char('Filed By', tracking=True)
    court = fields.Char('Court', tracking=True)
    case_type = fields.Char('Case Type', tracking=True)
    legal_team = fields.Char('Legal Team', tracking=True)
    mark_disputed = fields.Boolean()
    society_id = fields.Many2one('society', 'Society', domain=[('is_society', '=', True)], tracking=True)

    legal_dispute_line_ids = fields.One2many('legal.dispute.line', 'legal_dispute_id')
    dispute_info_ids = fields.One2many('dispute.info', 'dispute_id')

    def make_file_disputed(self):
        for rec in self.legal_dispute_line_ids:
            rec.file_id.file_status = 'dispute'
            rec.file_id.inventory_id.state = 'dispute'
        self.state = 'in_process'

    def resolved(self):
        for rec in self.legal_dispute_line_ids:
            rec.file_id.file_status = 'approve'
            rec.file_id.inventory_id.state = 'sold'
        self.state = 'resolved'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('dispute_seq', _('New')) == _('New'):
                vals['dispute_seq'] = self.env['ir.sequence'].next_by_code('legal.dispute.sequence') or _('New')
        result = super(LegalDispute, self).create(vals_list)
        return result


class LegalDisputeLine(models.Model):
    _name = 'legal.dispute.line'
    _description = 'Legal Dispute Line'

    file_id = fields.Many2one('file')
    phase_id = fields.Many2one('society', 'Phase')
    sector_id = fields.Many2one('sector')
    street_id = fields.Many2one('street')
    inventory_id = fields.Many2one('plot.inventory', 'Unit No')
    category_id = fields.Many2one('plot.category', 'Category', required=True)
    unit_category_type_id = fields.Many2one('unit.category.type', required=True)
    size_id = fields.Many2one('unit.size', 'Size')
    unit_class_id = fields.Many2one('unit.class')
    no_of_units = fields.Integer()

    legal_dispute_id = fields.Many2one('legal.dispute')

    @api.onchange('legal_dispute_id', 'phase_id', 'sector_id', 'street_id', 'file_id')
    def _phase_sector_domain(self):
        return {
            'domain': {
                'file_id': [('society_id', '=', self.legal_dispute_id.society_id.id), ('file_status', '=', 'approve')],
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.legal_dispute_id.society_id.id)],
                'sector_id': [('phase_id', '=', self.phase_id.id)],
                'street_id': [('sector_id', '=', self.sector_id.id)],
            }
        }

    @api.onchange('inventory_id')
    def _onchange_inventory(self):
        for rec in self:
            if rec.phase_id:
                rec.sector_id = rec.inventory_id.sector_id.id
                rec.street_id = rec.inventory_id.street_id.id
                rec.category_id = rec.inventory_id.category_id.id
                rec.size_id = rec.inventory_id.size_id.id
                rec.unit_category_type_id = rec.inventory_id.unit_category_type_id.id
                rec.unit_class_id = rec.inventory_id.unit_class_id.id

    @api.onchange('file_id')
    def onchange_file(self):
        for rec in self:
            if rec.file_id:
                rec.write({'phase_id': rec.file_id.phase_id.id,
                           'sector_id': rec.file_id.sector_id.id,
                           'street_id': rec.file_id.street_id.id,
                           'inventory_id': rec.file_id.inventory_id.id,
                           'category_id': rec.file_id.category_id.id,
                           'unit_category_type_id': rec.file_id.unit_category_type_id.id,
                           'size_id': rec.file_id.size_id.id,
                           'unit_class_id': rec.file_id.unit_class_id.id,
                           'no_of_units': 1, })


class DisputeInfo(models.Model):
    _name = 'dispute.info'
    _description = 'Dispute Information'

    hearing_date = fields.Date('Hearing Date', required=True)
    next_date = fields.Date('Next Date', required=True)
    outcome = fields.Char()

    dispute_id = fields.Many2one('legal.dispute', 'Legal Dispute')
