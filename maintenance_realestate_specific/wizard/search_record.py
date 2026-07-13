from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SearchRecord(models.TransientModel):
    _name = 'search.record'
    _description = 'Search Record'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')], required=True)
    contact_number = fields.Char(string='Contact Number')
    partner_id = fields.Many2one('res.partner', string='Customer')
    search_record_line_ids = fields.One2many('search.record.line', 'search_record_id')

    def search_record(self):
        # res.partner.mobile was removed in Odoo 19 (merged into phone)
        record = self.env['res.partner'].search([('phone', '=', self.contact_number)])
        try:
            if record:
                self.partner_id = record[0].id
        except Exception as e:
            raise ValidationError(_('Some Basic Data for member is not available.See Error :%s' % (e)))
        else:
            self.insert_rec_in_lines()
            return {
                'context': self.env.context,
                'view_mode': 'form',
                'res_model': self._name,
                'res_id': self.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def insert_rec_in_lines(self):
        if self.project_type == 'housing_society':
            file_record = self.env['file'].search([('membership_id', '=', self.partner_id.id),
                                                   ('project_type', '=', self.project_type)])
            if file_record:
                for file in file_record:
                    self.search_record_line_ids = [(0, 0, {
                        'project_type': file.project_type,
                        'file_id': file.id,
                        'society_id': file.society_id.id,
                        'phase_id': file.phase_id.id,
                        'sector_id': file.sector_id.id,
                        'inventory_id': file.inventory_id.id,
                    })]

        elif self.project_type == 'skyscraper':
            file_record = self.env['file'].search([('membership_id', '=', self.partner_id.id),
                                                   ('project_type', '=', self.project_type)])
            if file_record:
                for file in file_record:
                    self.search_record_line_ids = [(0, 0, {
                        'project_type': file.project_type,
                        'file_id': file.id,
                        'society_id': file.society_id.id,
                        'phase_id': file.phase_id.id,
                        'sector_id': file.sector_id.id,
                        'inventory_id': file.inventory_id.id,
                    })]

    def assign_record(self):
        if self.project_type == 'housing_society':
            lines = self.search_record_line_ids.filtered(lambda l: l.is_selected)
            if len(lines) > 1:
                raise ValidationError(_('You Can Select Only One Line'))
            if (lines
                    and self.env.context.get('active_model', False)
                    and self.env.context.get('active_model') == 'helpdesk.ticket'
                    and self.env.context.get('active_id', False)
            ):
                self.env['helpdesk.ticket'].browse(self.env.context.get('active_id')).write({
                    'partner_id': lines.file_id.membership_id.id,
                    'file_id': lines.file_id.id,
                    'society_id': lines.file_id.society_id.id,
                    'phase_id': lines.file_id.phase_id.id,
                    'sector_id': lines.file_id.sector_id.id,
                    'street_id': lines.file_id.street_id.id,
                    'inventory_id': lines.file_id.inventory_id.id,
                    'plot_name': lines.file_id.inventory_id.name
                })
        elif self.project_type == 'skyscraper':
            lines = self.search_record_line_ids.filtered(lambda l: l.is_selected)
            if len(lines) > 1:
                raise ValidationError(_('You Can Select Only One Line'))
            if (lines
                    and self.env.context.get('active_model', False)
                    and self.env.context.get('active_model') == 'helpdesk.ticket'
                    and self.env.context.get('active_id', False)
            ):
                self.env['helpdesk.ticket'].browse(self.env.context.get('active_id')).write({
                    'partner_id': lines.file_id.membership_id.id,
                    'file_id': lines.file_id.id,
                    'society_id': lines.file_id.society_id.id,
                    'phase_id': lines.file_id.phase_id.id,
                    'sector_id': lines.file_id.sector_id.id,
                    'inventory_id': lines.file_id.inventory_id.id,
                    'plot_name': lines.file_id.inventory_id.name
                })


class SearchRecordLine(models.TransientModel):
    _name = 'search.record.line'
    _description = ' Search Record Line'

    project_type = fields.Selection([
        ('skyscraper', 'Skyscraper'),
        ('housing_society', 'Housing Society')])
    is_selected = fields.Boolean(string='is_selected')
    search_record_id = fields.Many2one('search.record')
    file_id = fields.Many2one('file', readonly=True)
    society_id = fields.Many2one('society', domain=[('is_society', '=', True)], readonly=True)
    phase_id = fields.Many2one('society', domain=[('is_society', '!=', True)], readonly=True)
    sector_id = fields.Many2one('sector', readonly=True)
    inventory_id = fields.Many2one('plot.inventory', readonly=True)
