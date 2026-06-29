from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class FileAssignmentSelection(models.TransientModel):
    _name = 'file.assignment.selection'
    _description = 'File Assignment Selection'

    assignment_id = fields.Many2one('open.file.assignment')
    file_assignment_line_ids = fields.One2many('file.assignment.selection.line', 'file_assignment_id')

    def create_jv(self, record):
        if self.env.company.unit_booking_journal_id:
            if not self.env.company.unit_booking_journal_id.default_debit_account_id:
                raise ValidationError(_("Please select debit account in selected journal"))
            if not self.env.company.unit_booking_journal_id.default_credit_account_id:
                raise ValidationError(_("Please select credit account in selected journal"))
            move = {
                'date': fields.Date.today(),
                'journal_id': self.env.company.unit_booking_journal_id.id,
                'company_id': self.env.company.id,
                'move_type': 'entry',
                'state': 'draft',
                'ref': record.sequence_number + '- ' + record.name,
                'units_booking_id': record.id,
                'line_ids': [(0, 0, {
                    'account_id': self.env.company.unit_booking_journal_id.default_credit_account_id.id,
                    'debit': record.initial_payment}),
                             (0, 0, {
                                 'account_id': self.env.company.unit_booking_journal_id.default_debit_account_id.id,
                                 'credit': record.initial_payment
                             })]
            }
            move_id = self.env['account.move'].create(move)

            move_id.action_post()
            record.jv_id = False
        else:
            raise ValidationError(_('Please Select Journal in configuration'))

    def undo_assignment(self):
        unit_booking_record = self.env['units.booking']
        undo_assignment_history = self.env['undo.assignment.history']
        if not self.file_assignment_line_ids:
            raise ValidationError(_('No record found'))
        record = self.file_assignment_line_ids.filtered(lambda is_check: is_check.is_check)
        if not record:
            raise ValidationError(_('Please select at least one line'))
        for rec in self:
            for recs in record:

                data = unit_booking_record.search([('number', '>=', int(recs.unit_booking_starting_id.number)),
                                                   ('number', '<=', int(recs.unit_booking_ending_id.number)),
                                                   ('state', '=', 'assignment'),
                                                   ('prefix_id', '=', rec.assignment_id.prefix_id.id),
                                                   ('batch_id', '=', rec.assignment_id.batch_id.id)])
                allotted_file = unit_booking_record.search([
                    ('number', '>=', int(recs.unit_booking_starting_id.number)),
                    ('number', '<=', int(recs.unit_booking_ending_id.number)),
                    ('state', 'in', ['print', 'allotment', 'issued', 'file_created']),
                    ('prefix_id', '=', rec.assignment_id.prefix_id.id),
                    ('batch_id', '=', rec.assignment_id.batch_id.id)])
                receipt_data = data.filtered(
                    lambda printing: printing.is_receipt_printed or printing.is_qr_printed or printing.is_ledger_printed)
                if receipt_data:
                    raise ValidationError(
                        _("Process can't be completed because some file are in one of printing process"))
                if allotted_file:
                    raise ValidationError(
                        _("Process can't be completed because some files are not in assignment state"))
                if data:
                    for record in data:
                        self.create_jv(record)
                        record.write({
                            'booking_date': False,
                            'starting_date': False,
                            'sector_id': False,
                            'category_id': False,
                            'unit_category_type_id': False,
                            'predefine_plan_id': False,
                            'interval_id': False,
                            'total_installment': 0,
                            # 'plan_description': recs.predefine_plan_id.name,
                            'plan_type': False,
                            'payment_type': False,
                            'sale_amount': 0.00,
                            'ttl_sale_amount': 0.00,
                            'net_sale_amount': 0.00,
                            'initial_payment': 0.00,
                            'balance_amount': 0.00,
                            'balloting_amount': 0.00,
                            "processing_fee": 0.00,
                            'payment_states': 'draft',
                            'state': 'open',
                            'is_assigned': False,
                            'history_ids': [(0, 0, {
                                'state': 'open',
                                'print_state': '',
                                'date': fields.Date.today(),
                            })]
                        })
                        record.unit_booking_plan_ids.unlink()
                else:
                    raise ValidationError(_("No Record Found"))
                recs.open_file_assignment_line_id.is_undo_assignment = True
                recs.open_file_assignment_line_id.undo_date = fields.Date.today()
                undo_assignment_history.create({
                    'open_file_assignment_id': rec.assignment_id.id,
                    'unit_booking_starting_id': recs.unit_booking_starting_id.id,
                    'unit_booking_ending_id': recs.unit_booking_ending_id.id,
                    'batch_id': rec.assignment_id.batch_id.id,
                    'no_of_units': recs.no_of_units,
                    'undo_date': fields.Date.today(),
                })
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': "Undo Assignment of open file is done",
                    'img_url': '/web/static/src/img/smile.svg',
                    'type': 'rainbow_man',
                }
            }


class FileAssignmentSelectionLine(models.TransientModel):
    _name = 'file.assignment.selection.line'
    _description = 'File Assignment Selection Line'

    open_file_assignment_line_id = fields.Many2one("open.file.assignment.line")
    sector_id = fields.Many2one('sector')
    category_id = fields.Many2one('plot.category', string='Category')
    unit_category_type_id = fields.Many2one('unit.category.type')
    batch_id = fields.Many2one('unit.batch.generation')
    unit_booking_starting_id = fields.Many2one('units.booking')
    unit_booking_ending_id = fields.Many2one('units.booking')
    file_assignment_id = fields.Many2one('file.assignment.selection')
    predefine_plan_id = fields.Many2one('predefine.plan')

    # numerical fields
    unit_price = fields.Float()
    no_of_units = fields.Integer()
    # boolean fields
    is_check = fields.Boolean(default=False)
