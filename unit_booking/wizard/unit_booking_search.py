# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UnitBookingSearch(models.TransientModel):
    _name = "unit.booking.search"
    _description = "Unit Booking Search"

    # models relational fields
    batch_id = fields.Many2one('unit.batch.generation')
    prefix_id = fields.Many2one('unit.batch.generation.line')
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    search_line_ids = fields.One2many('unit.booking.search.line', 'search_id')
    agent_id = fields.Many2one('res.partner', string="Dealer")
    sub_agent_id = fields.Many2one('res.partner', string='Sub Dealer')
    unit_booking_allotment_id = fields.Many2one('unit.booking.allotment', string='Allotment')

    # char fields
    prefix = fields.Char(string='Prefix ', related='prefix_id.prefix', store=True)
    # selection field
    transaction_type = fields.Selection([
        ('open_file', 'File Processing'),
        ('swap', 'Unit Swap'),
        ('cancel', 'Unit Cancellation'),
        ('change_amount', 'Change Amount'),
        ('duplicate_file', 'Duplicate File')])
    invoice_generated_for = fields.Selection([
        ('customer', 'Customer'),
        ('dealer', 'Dealer')])

    @api.onchange('unit_booking_allotment_id')
    def _onchange_allotment(self):
        if self.unit_booking_allotment_id:
            self.batch_id = self.unit_booking_allotment_id.unit_batch_id.id

    @api.onchange('transaction_type', 'prefix_id')
    def onchange_method(self):
        for rec in self:
            if rec.transaction_type == 'open_file':
                if rec.batch_id and not rec.prefix_id:
                    return {
                        'domain': {
                            'unit_booking_starting_id': [('file_issuance_request_created', '=', False),
                                                         ('batch_id', '=', rec.batch_id.id),
                                                         ('state', '=', 'issued')]
                        }
                    }
                if rec.prefix_id and not rec.batch_id:
                    return {
                        'domain': {
                            'unit_booking_starting_id': [('file_issuance_request_created', '=', False),
                                                         ('prefix_id', '=', rec.prefix_id.id),
                                                         ('state', '=', 'issued')]
                        }
                    }
                if rec.prefix_id and rec.batch_id:
                    return {
                        'domain': {
                            'unit_booking_starting_id': [('file_issuance_request_created', '=', False),
                                                         ('batch_id', '=', rec.batch_id.id),
                                                         ('prefix_id', '=', rec.prefix_id.id),
                                                         ('state', '=', 'issued')]
                        }
                    }
            elif rec.transaction_type == 'swap':
                if rec.unit_booking_allotment_id:
                    return {
                        'domain': {
                            'unit_booking_starting_id': [
                                ('file_issuance_request_created', '=', False),
                                ('unit_booking_allotment_id', '=', rec.unit_booking_allotment_id.id),
                                ('state', 'in', ['issued', 'allotment'])]
                        }
                    }
                else:
                    return {
                        'domain': {
                            'unit_booking_starting_id': [
                                ('file_issuance_request_created', '=', False),
                                ('state', 'in', ['issued', 'allotment'])]
                        }
                    }

    @api.onchange('unit_booking_starting_id')
    def onchange_starting_number(self):
        for rec in self:
            rec.batch_id = rec.unit_booking_starting_id.batch_id.id
            rec.prefix_id = rec.unit_booking_starting_id.prefix_id.id
            if rec.unit_booking_starting_id and rec.transaction_type == 'open_file':
                return {
                    'domain': {
                        'unit_booking_ending_id': [('number', '>=', rec.unit_booking_starting_id.number),
                                                   ('file_issuance_request_created', '=', False),
                                                   ('state', '=', 'issued')]
                    }
                }
            elif rec.unit_booking_starting_id and rec.transaction_type == 'swap':
                rec.unit_booking_allotment_id = rec.unit_booking_starting_id.unit_booking_allotment_id.id
                return {
                    'domain': {
                        'unit_booking_ending_id': [
                            ('number', '>=', rec.unit_booking_starting_id.number),
                            ('file_issuance_request_created', '=', False),
                            ('state', 'in', ['issued', 'allotment'])]
                    }
                }

    def constrains(self):
        if (not self.sub_agent_id and not self.agent_id
                and not self.unit_booking_ending_id
                and not self.unit_booking_starting_id
                and not self.prefix_id
                and not self.batch_id
                and not self.unit_booking_allotment_id):
            raise ValidationError(_("Select at least one criteria before searching"))
        if self.transaction_type == 'swap' and not self.unit_booking_allotment_id:
            raise ValidationError(_("Please select allotment when transaction is unit swap"))

    def search_related_records(self):
        self.search_line_ids = False
        if self.transaction_type == 'open_file':
            domain = [('state', '=', 'issued'), ('file_issuance_request_created', '=', False)]
        if self.transaction_type == 'swap':
            domain = [('state', '=', 'allotment'), ('file_issuance_request_created', '=', False)]
        if self.transaction_type == 'duplicate_file':
            domain = [('state', '=', 'file_created')]
        if self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))
        if self.prefix_id:
            domain.append(('prefix_id', '=', self.prefix_id.id))
        if self.unit_booking_starting_id:
            domain.append(('number', '>=', self.unit_booking_starting_id.number))
        if self.unit_booking_ending_id:
            domain.append(('number', '<=', self.unit_booking_ending_id.number))
        if self.agent_id:
            domain.append(('agent_id', '=', self.agent_id.id))
        if self.sub_agent_id:
            domain.append(('sub_agent_id', '=', self.sub_agent_id.id))
        if self.unit_booking_allotment_id:
            domain.append(('unit_booking_allotment_id', '=', self.unit_booking_allotment_id.id))
        self.constrains()
        record_set = self.env['units.booking'].search(domain)
        if record_set:
            for record in record_set:
                self.search_line_ids = [(0, 0, {
                    'units_booking_id': record.id,
                    'processing_fee': record.processing_fee,
                })]
        if not record_set:
            raise ValidationError(_('Record not found'))

        return {
            'name': _('Search'),
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def create_issuance_req(self):
        if self.transaction_type == 'open_file':
            unit_booking_ids = []
            new_created_record_list = []
            record_set_id = False
            record_set = self.env['open.file.issuance.request']
            for rec in self.search_line_ids.filtered(lambda checked: checked.is_checked):
                unit_booking_ids.append(rec.units_booking_id.id)
                record_set_id = record_set.create({
                    'units_booking_id': rec.units_booking_id.id,
                    'batch_id': rec.batch_id.id,
                    'transaction_type': self.transaction_type,
                    'processing_fee': rec.processing_fee,
                    'invoice_generated_for': self.invoice_generated_for,
                    'reset_installment_plan': rec.reset_installment_plan,
                })
                rec.units_booking_id.file_issuance_request_created = True
                new_created_record_list.append(record_set_id.id)
            # issuance req tree and form view of current issued record
            tree_view = (self.env.ref('unit_booking.open_file_issuance_request_tree').id, 'tree')
            form_view = (self.env.ref('unit_booking.open_file_issuance_request_form').id, 'form')
            if len(new_created_record_list) > 1:
                return {
                    'name': _('Open File Issuance Request'),
                    'context': self.env.context,
                    'res_model': 'open.file.issuance.request',
                    'type': 'ir.actions.act_window',
                    'views': [tree_view, form_view],
                    'view_mode': 'list,form',
                    'domain': [('units_booking_id', 'in', unit_booking_ids)],
                    'target': 'self'
                }
            else:
                return {
                    'name': _('Open File Issuance Request'),
                    'context': self.env.context,
                    'res_model': 'open.file.issuance.request',
                    'type': 'ir.actions.act_window',
                    'res_id': record_set_id.id,
                    'view_mode': 'form',
                    'target': 'self'
                }
        if self.transaction_type == 'swap':
            swap_request = self.env['unit.booking.swap.request']
            swap_request.create({
                'request_date': fields.Date.today(),
                'transaction_type': self.transaction_type,
                'unit_booking_allotment_id': self.unit_booking_allotment_id.id,
                'batch_id': self.unit_booking_allotment_id.unit_batch_id.id,
                'deal_pack_id': self.unit_booking_allotment_id.deal_pack_id.id,
                'agent_id': self.unit_booking_allotment_id.partner_id.id,
                'sub_agent_id': self.unit_booking_allotment_id.partner_subagent_id.id if self.unit_booking_allotment_id.issue_to_subagent else False,
                'swap_request_line_ids': [(0, 0, {
                    'new_units_booking_id': rec.new_units_booking_id.id,
                    'units_booking_id': rec.units_booking_id.id,
                    'society_id': rec.units_booking_id.society_id.id,
                    'phase_id': rec.units_booking_id.phase_id.id,
                    'sector_id': rec.units_booking_id.sector_id.id,
                    'category_id': rec.units_booking_id.category_id.id,
                    'unit_category_type_id': rec.units_booking_id.unit_category_type_id.id,
                    'unit_booking_allotment_id': self.unit_booking_allotment_id.id,
                    'batch_id': rec.units_booking_id.batch_id.id,
                    'is_checked': True,
                }) for rec in self.search_line_ids.filtered(lambda checked: checked.is_checked)]
            })
        if self.transaction_type == 'duplicate_file':
            record_set = self.env['open.file.duplicate']
            for rec in self.search_line_ids.filtered(lambda checked: checked.is_checked):
                record_set_id = record_set.create({
                    'units_booking_id': rec.units_booking_id.id,
                    'batch_id': rec.batch_id.id,
                    'transaction_type': self.transaction_type,
                })


class UnitBookingSearchLine(models.TransientModel):
    _name = "unit.booking.search.line"
    _description = "Unit Booking Search Line"

    new_units_booking_id = fields.Many2one('units.booking')
    units_booking_id = fields.Many2one('units.booking')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]",
                                 related='units_booking_id.society_id')
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]",
                               related='units_booking_id.phase_id')
    sector_id = fields.Many2one('sector', related='units_booking_id.sector_id')
    category_id = fields.Many2one('plot.category', string='Category', related='units_booking_id.category_id')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product',
                                            related='units_booking_id.unit_category_type_id')
    batch_id = fields.Many2one('unit.batch.generation', related='units_booking_id.batch_id')
    processing_fee = fields.Float()
    search_id = fields.Many2one('unit.booking.search')

    # boolean fields
    is_checked = fields.Boolean(default=False)

    # selection fields
    reset_installment_plan = fields.Selection([('yes', 'Yes'), ('no', 'No')])
