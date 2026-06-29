from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OpenFileQRReading(models.TransientModel):
    _name = 'open.file.qr.reading'
    _description = 'Open File QR Reading'

    # selection fields
    unit_selection_option = fields.Selection([('scanning', 'Scanning'), ('range', 'Range')])
    file_adding_option = fields.Selection([('platter', 'Platter'), ('manual', 'Manual')])
    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    units_booking_id = fields.Many2one('units.booking')
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    open_file_qr_line_ids = fields.One2many('open.file.qr.reading.line', 'open_file_qr_id')
    allotment_id = fields.Many2one('unit.booking.allotment')
    issuance_id = fields.Many2one('unit.booking.issuance')
    unit_booking_cancellation_id = fields.Many2one('unit.booking.cancellation')
    platter_id = fields.Many2one('units.platter')

    # numerical fields
    no_of_units = fields.Integer()

    # boolean fields
    is_search_done = fields.Boolean(default=False)

    def range_data(self):
        self.open_file_qr_line_ids.unlink()
        lines = []
        unit_booking_obj = self.env['units.booking']
        for rec in self:
            data = unit_booking_obj.search([('number', '>=', int(rec.unit_booking_starting_id.number)),
                                            ('number', '<=', int(rec.unit_booking_ending_id.number)),
                                            ('batch_id', '=', rec.batch_id.id),
                                            ('prefix_id', 'in', [rec.unit_booking_starting_id.prefix_id.id,
                                                                 rec.unit_booking_ending_id.prefix_id.id])])

            if data:
                for record in data:
                    if not rec.platter_id:
                        if rec.allotment_id and not rec.unit_booking_cancellation_id and not rec.issuance_id:

                            val = {'units_booking_id': record.id,
                                   'phase_id': record.phase_id.id,
                                   'society_id': record.society_id.id,
                                   'sector_id': record.sector_id.id,
                                   'category_id': record.category_id.id,
                                   'unit_category_type_id': record.unit_category_type_id.id,
                                   'batch_id': record.batch_id.id,
                                   }
                            lines.append((0, 0, val))

                        elif rec.issuance_id and rec.allotment_id and not rec.unit_booking_cancellation_id:
                            if record.unit_booking_allotment_id == rec.allotment_id and record.state == 'allotment':
                                val = {'units_booking_id': record.id,
                                       'phase_id': record.phase_id.id,
                                       'society_id': record.society_id.id,
                                       'sector_id': record.sector_id.id,
                                       'category_id': record.category_id.id,
                                       'unit_category_type_id': record.unit_category_type_id.id,
                                       'batch_id': record.batch_id.id,
                                       }
                                lines.append((0, 0, val))

                        elif rec.allotment_id and rec.unit_booking_cancellation_id and not rec.issuance_id:
                            if (record.unit_booking_allotment_id == rec.allotment_id
                                    and record.state in ['allotment', 'issued']
                                    and record.batch_id == rec.allotment_id.unit_batch_id
                                    and record.agent_id == rec.allotment_id.partner_id):
                                val = {'units_booking_id': record.id,
                                       'phase_id': record.phase_id.id,
                                       'society_id': record.society_id.id,
                                       'sector_id': record.sector_id.id,
                                       'category_id': record.category_id.id,
                                       'unit_category_type_id': record.unit_category_type_id.id,
                                       'batch_id': record.batch_id.id,
                                       }
                                lines.append((0, 0, val))
                    else:
                        val = {
                            'units_booking_id': record.id,
                            'phase_id': record.phase_id.id,
                            'society_id': record.society_id.id,
                            'sector_id': record.sector_id.id,
                            'category_id': record.category_id.id,
                            'unit_category_type_id': record.unit_category_type_id.id,
                            'batch_id': record.batch_id.id,
                        }
                        lines.append((0, 0, val))
                    rec.open_file_qr_line_ids = lines
                    lines = []
            else:
                raise ValidationError(_('No record found'))
            rec.is_search_done = True
        return {
            'name': _('Range'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.onchange('file_adding_option')
    def change_platter_domain(self):
        for rec in self:
            if rec.file_adding_option == 'platter':
                return {
                    'domain': {
                        'platter_id': [('unit_batch_id', '=', rec.batch_id.id), ('state', '=', 'active')]
                    }
                }
            else:
                if rec.allotment_id and not rec.unit_booking_cancellation_id and not rec.issuance_id:
                    deal_added_files = rec.allotment_id.unit_booking_allotment_line_ids.mapped(
                        'units_booking_id.id')
                    if not deal_added_files:
                        deal_added_files = [0]
                    return {
                        'domain': {
                            'units_booking_id': [('batch_id', '=', rec.batch_id.id),
                                                 ('id', 'not in', deal_added_files),
                                                 ('state', '=', 'print')],
                            'unit_booking_starting_id': [('batch_id', '=', rec.batch_id.id),
                                                         ('id', 'not in', deal_added_files),
                                                         ('state', '=', 'print')],
                            'unit_booking_ending_id': [('batch_id', '=', rec.batch_id.id),
                                                       ('id', 'not in', deal_added_files),
                                                       ('state', '=', 'print')]
                        }
                    }

    @api.onchange('unit_booking_starting_id', 'no_of_units', 'unit_booking_ending_id')
    def onchange_unit_booking_starting_id(self):
        for rec in self:
            if not rec.platter_id:
                if rec.allotment_id and not rec.unit_booking_cancellation_id and not rec.issuance_id:
                    deal_added_files = rec.allotment_id.unit_booking_allotment_line_ids.mapped(
                        'units_booking_id.id')
                    if not deal_added_files:
                        deal_added_files = [0]
                    if rec.unit_booking_starting_id and rec.no_of_units:
                        rec.unit_booking_ending_id = self.env['units.booking'].search([
                            ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                            ('batch_id', '=', rec.batch_id.id),
                            ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                            ('id', 'not in', deal_added_files),
                            ('state', '=', 'print')], limit=1).id

                    if rec.unit_booking_starting_id and rec.unit_booking_ending_id and not rec.no_of_units:
                        rec.no_of_units = (rec.unit_booking_ending_id.number - rec.unit_booking_starting_id.number) + 1

                    if rec.unit_booking_starting_id and not rec.no_of_units:
                        return {
                            'domain': {
                                'unit_booking_ending_id': [('number', '>', rec.unit_booking_starting_id.number),
                                                           ('batch_id', '=', rec.batch_id.id),
                                                           ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                                                           ('id', 'not in', deal_added_files),
                                                           ('state', '=', 'print')]
                            }
                        }
                elif rec.issuance_id and rec.allotment_id and not rec.unit_booking_cancellation_id:
                    if rec.unit_booking_starting_id and rec.no_of_units:
                        rec.unit_booking_ending_id = self.env['units.booking'].search([
                            ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                            ('batch_id', '=', rec.batch_id.id),
                            ('unit_booking_allotment_id', '=', rec.issuance_id.unit_booking_allotment_id.id),
                            ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                            ('state', '=', 'allotment')], limit=1).id

                    if rec.unit_booking_starting_id and rec.unit_booking_ending_id and not rec.no_of_units:
                        rec.no_of_units = (rec.unit_booking_ending_id.number - rec.unit_booking_starting_id.number) + 1

                    if rec.unit_booking_starting_id and not rec.no_of_units:
                        return {
                            'domain': {
                                'unit_booking_ending_id': [
                                    ('number', '>', rec.unit_booking_starting_id.number),
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                                    ('unit_booking_allotment_id', '=', rec.issuance_id.unit_booking_allotment_id.id),
                                    ('state', '=', 'allotment')]
                            }
                        }
                elif rec.allotment_id and rec.unit_booking_cancellation_id and not rec.issuance_id:
                    if rec.unit_booking_starting_id and rec.no_of_units:
                        rec.unit_booking_ending_id = self.env['units.booking'].search([
                            ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                            ('batch_id', '=', rec.batch_id.id),
                            ('state', 'in', ['allotment', 'issued']),
                            ('unit_booking_allotment_id', '=', rec.allotment_id.id),
                            ('agent_id', '=', rec.allotment_id.partner_id.id),
                            ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id)], limit=1).id

                    if rec.unit_booking_starting_id and rec.unit_booking_ending_id and not rec.no_of_units:
                        rec.no_of_units = (rec.unit_booking_ending_id.number - rec.unit_booking_starting_id.number) + 1

                    if rec.unit_booking_starting_id and not rec.no_of_units:
                        return {
                            'domain': {
                                'unit_booking_ending_id': [
                                    ('number', '>', rec.unit_booking_starting_id.number),
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('state', 'in', ['allotment', 'issued']),
                                    ('unit_booking_allotment_id', '=', rec.allotment_id.id),
                                    ('agent_id', '=', rec.allotment_id.partner_id.id),
                                    ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                                ]
                            }
                        }
            else:
                if (len(rec.platter_id.platter_line_ids) + rec.no_of_units) > rec.platter_id.platter_size:
                    raise ValidationError('Cannot Add Files more than Platter Size')
                currently_added_files = rec.platter_id.platter_line_ids.mapped('units_booking_id.id')
                if not currently_added_files:
                    currently_added_files = [0]
                if rec.unit_booking_starting_id and rec.no_of_units:
                    if rec.allotment_id:
                        deal_added_files = rec.allotment_id.unit_booking_allotment_line_ids.mapped(
                            'units_booking_id.id')
                        if not deal_added_files:
                            deal_added_files = [0]
                        rec.unit_booking_ending_id = self.env['units.booking'].search([
                            ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                            ('batch_id', '=', rec.batch_id.id),
                            ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                            ('id', 'in', currently_added_files),
                            ('id', 'not in', deal_added_files),
                            ('state', '=', 'print')
                        ], limit=1).id
                    else:
                        rec.unit_booking_ending_id = self.env['units.booking'].search([
                            ('number', '=', (rec.unit_booking_starting_id.number + rec.no_of_units) - 1),
                            ('batch_id', '=', rec.batch_id.id),
                            ('prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                            ('id', 'not in', currently_added_files)], limit=1).id

                if rec.unit_booking_starting_id and rec.unit_booking_ending_id and not rec.no_of_units:
                    rec.no_of_units = (rec.unit_booking_ending_id.number - rec.unit_booking_starting_id.number) + 1

                if rec.unit_booking_starting_id and not rec.no_of_units:
                    if rec.allotment_id:
                        deal_added_files = rec.allotment_id.unit_booking_allotment_line_ids.mapped(
                            'units_booking_id.id')
                        if not deal_added_files:
                            deal_added_files = [0]
                        return {
                            'domain': {
                                'unit_booking_ending_id': [('number', '>', rec.unit_booking_starting_id.number),
                                                           ('batch_id', '=', rec.batch_id.id),
                                                           (
                                                           'prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                                                           ('id', 'in', currently_added_files),
                                                           ('id', 'not in', deal_added_files),
                                                           ('state', '=', 'print')]
                            }
                        }
                    else:
                        return {
                            'domain': {
                                'unit_booking_ending_id': [('number', '>', rec.unit_booking_starting_id.number),
                                                           ('batch_id', '=', rec.batch_id.id),
                                                           (
                                                           'prefix_id', '=', rec.unit_booking_starting_id.prefix_id.id),
                                                           ('id', 'not in', currently_added_files),
                                                           ('state', '=', 'print')]
                            }
                        }

    @api.onchange('allotment_id', 'issuance_id', 'unit_booking_cancellation_id', 'platter_id', 'batch_id')
    def onchange_method(self):
        for rec in self:
            if not rec.platter_id:
                if rec.allotment_id and not rec.unit_booking_cancellation_id and not rec.issuance_id:
                    if rec.unit_selection_option == 'scanning':
                        return {
                            'domain': {
                                'units_booking_id': [('batch_id', '=', rec.batch_id.id), ('state', '=', 'print')]
                            }
                        }
                    else:
                        if rec.file_adding_option == 'platter':
                            return {
                                'domain': {
                                    'unit_booking_starting_id': [('batch_id', '=', rec.batch_id.id),
                                                                 ('state', '=', 'print')]
                                }
                            }
                        else:
                            return {
                                'domain': {
                                    'unit_booking_starting_id': [('batch_id', '=', rec.batch_id.id),
                                                                 ('state', '=', 'print')]
                                }
                            }
                elif rec.issuance_id and rec.allotment_id and not rec.unit_booking_cancellation_id:
                    if rec.unit_selection_option == 'scanning':
                        return {
                            'domain': {
                                'units_booking_id': [
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('state', '=', 'allotment'),
                                    ('unit_booking_allotment_id', '=', rec.allotment_id.id)]
                            }
                        }
                    else:
                        return {
                            'domain': {
                                'unit_booking_starting_id': [
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('state', '=', 'allotment'),
                                    ('unit_booking_allotment_id', '=', rec.allotment_id.id)]
                            }
                        }
                elif rec.allotment_id and rec.unit_booking_cancellation_id and not rec.issuance_id:
                    if rec.unit_selection_option == 'scanning':
                        return {
                            'domain': {
                                'units_booking_id': [
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('state', 'in', ['allotment', 'issued']),
                                    ('unit_booking_allotment_id', '=', rec.allotment_id.id),
                                    ('agent_id', '=', rec.allotment_id.partner_id.id)]
                            }
                        }
                    else:
                        return {
                            'domain': {
                                'unit_booking_starting_id': [
                                    ('batch_id', '=', rec.batch_id.id),
                                    ('state', 'in', ['allotment', 'issued']),
                                    ('unit_booking_allotment_id', '=', rec.allotment_id.id),
                                    ('agent_id', '=', rec.allotment_id.partner_id.id)]
                            }
                        }
            else:
                currently_added_files = rec.platter_id.platter_line_ids.mapped('units_booking_id.id')
                if not currently_added_files:
                    currently_added_files = [0]
                deal_added_files = rec.allotment_id.unit_booking_allotment_line_ids.mapped(
                    'units_booking_id.id')
                if not deal_added_files:
                    deal_added_files = [0]
                if rec.unit_selection_option == 'scanning':
                    if rec.allotment_id:
                        if rec.file_adding_option == 'platter':
                            platter_open_files = rec.platter_id.platter_line_ids.mapped('units_booking_id.id')
                            if not platter_open_files:
                                platter_open_files = [0]
                            return {
                                'domain': {
                                    'units_booking_id': [('id', 'in', platter_open_files),
                                                         ('id', 'not in', deal_added_files),
                                                         ('state', '=', 'print')]
                                }
                            }
                    else:
                        return {
                            'domain': {
                                'units_booking_id': [('batch_id', '=', rec.batch_id.id),
                                                     ('id', 'not in', currently_added_files),
                                                     ('state', '=', 'print'),
                                                     ('added_in_platter', '=', False)]
                            }
                        }
                else:
                    if rec.allotment_id:
                        if rec.file_adding_option == 'platter':
                            platter_open_files = rec.platter_id.platter_line_ids.mapped('units_booking_id.id')
                            if not platter_open_files:
                                platter_open_files = [0]
                            return {
                                'domain': {
                                    'unit_booking_starting_id': [('id', 'in', platter_open_files),
                                                                 ('id', 'not in', deal_added_files),
                                                                 ('state', '=', 'print')]
                                }
                            }
                    else:
                        return {
                            'domain': {
                                'unit_booking_starting_id': [('batch_id', '=', rec.batch_id.id),
                                                             ('id', 'not in', currently_added_files),
                                                             ('state', '=', 'print'),
                                                             ('added_in_platter', '=', False)]
                            }
                        }

    @api.onchange('units_booking_id')
    def on_change_status(self):
        lines = []
        for rec in self.filtered(
                lambda self: self.units_booking_id.id not in self.open_file_qr_line_ids.mapped('units_booking_id.id')):
            if rec.units_booking_id:
                val = {'units_booking_id': rec.units_booking_id.id,
                       'phase_id': rec.units_booking_id.phase_id.id,
                       'society_id': rec.units_booking_id.society_id.id,
                       'sector_id': rec.units_booking_id.sector_id.id,
                       'category_id': rec.units_booking_id.category_id.id,
                       'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                       'batch_id': rec.units_booking_id.batch_id.id,
                       }
                lines.append((0, 0, val))
                if not rec.platter_id:
                    if self.allotment_id and not self.unit_booking_cancellation_id and not self.issuance_id:
                        rec.open_file_qr_line_ids = lines
                    elif self.issuance_id and self.allotment_id and not self.unit_booking_cancellation_id:
                        rec.open_file_qr_line_ids = lines
                    elif self.allotment_id and self.unit_booking_cancellation_id and not self.issuance_id:
                        rec.open_file_qr_line_ids = lines
                else:
                    rec.open_file_qr_line_ids = lines
            rec.units_booking_id = False
        self.units_booking_id = False

    def proceed_to_qr(self):
        price = 0
        for rec in self.open_file_qr_line_ids:
            batch_assignments = self.env['open.file.assignment'].search([('batch_id', '=', self.batch_id.id)])
            for assignment in batch_assignments:
                for line in assignment.open_file_assignment_line_ids.filtered(
                        lambda l: l.category_id == rec.units_booking_id.category_id and l.unit_category_type_id == rec.units_booking_id.unit_category_type_id):
                    all_booking_files = self.env['units.booking'].search([('batch_id', '=', self.batch_id.id),
                                                                          ('number', '>=',
                                                                           line.unit_booking_starting_id.number),
                                                                          ('number', '<=',
                                                                           line.unit_booking_ending_id.number),
                                                                          ('prefix_id', 'in',
                                                                           [line.unit_booking_starting_id.prefix_id.id,
                                                                            line.unit_booking_ending_id.prefix_id.id])
                                                                          ])
                    if rec.units_booking_id.id in all_booking_files.ids:
                        price = line.unit_price
            if not self.platter_id:
                if self.allotment_id and not self.unit_booking_cancellation_id and not self.issuance_id:
                    if rec.units_booking_id not in self.allotment_id.unit_booking_allotment_line_ids.mapped(
                            'units_booking_id'):
                        self.allotment_id.unit_booking_allotment_line_ids = [(0, 0, {
                            'units_booking_id': rec.units_booking_id.id,
                            'phase_id': rec.units_booking_id.phase_id.id,
                            'society_id': rec.units_booking_id.society_id.id,
                            'sector_id': rec.units_booking_id.sector_id.id,
                            'category_id': rec.units_booking_id.category_id.id,
                            'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                            'batch_id': rec.units_booking_id.batch_id.id,
                            'price': price,
                        })]
                elif self.issuance_id and self.allotment_id and not self.unit_booking_cancellation_id:
                    if rec.units_booking_id not in self.issuance_id.unit_booking_issuance_line_ids.mapped(
                            'units_booking_id'):
                        self.issuance_id.unit_booking_issuance_line_ids = [(0, 0, {
                            'units_booking_id': rec.units_booking_id.id,
                            'phase_id': rec.units_booking_id.phase_id.id,
                            'society_id': rec.units_booking_id.society_id.id,
                            'sector_id': rec.units_booking_id.sector_id.id,
                            'category_id': rec.units_booking_id.category_id.id,
                            'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                            'batch_id': rec.units_booking_id.batch_id.id
                        })]
                elif self.allotment_id and self.unit_booking_cancellation_id and not self.issuance_id:
                    if rec.units_booking_id not in \
                            self.unit_booking_cancellation_id.unit_booking_cancellation_line_ids.mapped(
                                'units_booking_id'):
                        self.unit_booking_cancellation_id.unit_booking_cancellation_line_ids = [(0, 0, {
                            'units_booking_id': rec.units_booking_id.id,
                        })]
            else:
                if self.allotment_id and not self.unit_booking_cancellation_id and not self.issuance_id:
                    if rec.units_booking_id not in self.allotment_id.unit_booking_allotment_line_ids.mapped(
                            'units_booking_id'):
                        self.allotment_id.unit_booking_allotment_line_ids = [(0, 0, {
                            'units_booking_id': rec.units_booking_id.id,
                            'phase_id': rec.units_booking_id.phase_id.id,
                            'society_id': rec.units_booking_id.society_id.id,
                            'sector_id': rec.units_booking_id.sector_id.id,
                            'category_id': rec.units_booking_id.category_id.id,
                            'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                            'batch_id': rec.units_booking_id.batch_id.id,
                            'price': price,
                        })]

                else:
                    if (len(self.platter_id.platter_line_ids) + self.no_of_units) > self.platter_id.platter_size:
                        raise ValidationError('Cannot Add Files more than Platter Size')
                    if rec.units_booking_id not in self.platter_id.platter_line_ids.mapped('units_booking_id'):
                        self.platter_id.platter_line_ids = [(0, 0, {
                            'units_booking_id': rec.units_booking_id.id,
                            'phase_id': rec.units_booking_id.phase_id.id,
                            'society_id': rec.units_booking_id.society_id.id,
                            'sector_id': rec.units_booking_id.sector_id.id,
                            'category_id': rec.units_booking_id.category_id.id,
                            'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                            'batch_id': rec.units_booking_id.batch_id.id,
                            'price': price,
                        })]
                        rec.units_booking_id.added_in_platter = True


class OpenFileQRReadingLine(models.TransientModel):
    _name = 'open.file.qr.reading.line'
    _description = 'Open File Qr Reading Line'

    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    batch_id = fields.Many2one('unit.batch.generation')
    open_file_qr_id = fields.Many2one('open.file.qr.reading')
