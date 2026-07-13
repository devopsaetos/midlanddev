# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import dateutil.parser
from dateutil.relativedelta import relativedelta


class MaintenanceCharges(models.Model):
    _name = 'maintenance.charges'
    # 'tools.mixin' removed - it was provided by 'axiom_payment_report', which is
    # not available in this addons tree (dependency commented out in __manifest__.py).
    # 'mail.thread'/'mail.activity.mixin' added explicitly (matching the convention used
    # everywhere else in this project, e.g. change_unit_type.py) so tracking=True fields
    # and the <chatter/> widget in the form view keep working.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'Maintenance Charges'

    name = fields.Char(tracking=True)
    file_id = fields.Many2one('file')
    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]")
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")
    sector_ids = fields.Many2many('sector')

    date_from = fields.Date(tracking=True)
    date_to = fields.Date(tracking=True)
    applicable_from = fields.Selection([
        ('1st_ins', 'First Installment'),
        ('last_ins', 'Last Installment'),
    ], default="last_ins", tracking=True)

    maintenance_charges_line_ids = fields.One2many('maintenance.charges.line', 'maintenance_charges_id')

    @api.onchange('society_id', 'phase_id')
    def _phase_domain(self):
        return {
            'domain': {
                'phase_id': [('is_society', '!=', True), ('society_id', '=', self.society_id.id)],
                'sector_ids': [('phase_id', '=', self.phase_id.id)],
            }
        }

    # New code
    # ******************************* New Correct Code **********************************************************
    @api.model
    def maintenance_charges_invoices(self):
        date = self.env.ref('maintenance_charges.ir_cron_maintenance_charges').till_date or fields.Date.today()
        today_date = fields.Date.today()
        month_first_date = date.replace(day=1)
        file = self.env['file']
        for recs in self.search([('society_id.company_id', '=', self.env.company.id)]):
            for rec in recs.maintenance_charges_line_ids:
                files = file.search([('society_id', '=', recs.society_id.id),
                                     ('phase_id', '=', recs.phase_id.id),
                                     ('file_status', '!=', 'draft'),
                                     ('category_id', '=', rec.category_id.id),
                                     ('unit_class_id', '=', rec.unit_class_id.id),
                                     ('membership_id', '!=', False)])
                if recs.sector_ids:
                    files = file.search(
                        [('society_id', '=', recs.society_id.id), ('phase_id', '=', recs.phase_id.id), ('sector_id', 'in', recs.sector_ids.ids),
                         ('file_status', '!=', 'draft'),
                         ('category_id', '=', rec.category_id.id), ('unit_class_id', '=', rec.unit_class_id.id), ('membership_id', '!=', False)])
                print("TOTAL FILES >>>>>>>>>>>> ", len(files))
                for file_rec in files:
                    monthly_invoice_created = False
                    existing_invoice = self.env['account.move'].search([
                        ('file_ids', '=', file_rec.id),
                        ('partner_id', '=', file_rec.membership_id.id),
                        ('property_invoice_type', '=', 'maintenance_charges'),
                        ('invoice_date', '>=', month_first_date),
                        ('invoice_date', '<', month_first_date + relativedelta(months=1)),
                    ], limit=1)
                    exemption_obj = self.env['maintenance.exemption.history'].search([('file_id', '=', file_rec.id), ('exemption_state', '=', 'active'), ('product_id.id', '=', 103), ('from_date', '<=', today_date), ('to_date', '>=', today_date)])

                    if existing_invoice:
                        print(f"Invoice already exists for {file_rec.name} in {month_first_date.strftime('%B')}. Skipping...")
                        continue
                    if file_rec.maintenance_history_ids:
                        installment_number = file_rec.maintenance_history_ids[-1].installment_number + 1
                        for history in file_rec.maintenance_history_ids:
                            if history.date.month == date.month and history.date.year == date.year:
                                monthly_invoice_created = True
                    else:
                        installment_number = 1
                    if rec.maintenance_charges_type_id.unit_type == 'marla' \
                            and not monthly_invoice_created \
                            and file_rec.category_id == rec.category_id and file_rec.unit_class_id == rec.unit_class_id:
                        if round(file_rec.unit_category_type_id.area_marla) in range(rec.from_no, rec.to_no + 1):
                            if date >= recs.date_from and date <= recs.date_to:
                                for line in rec.maintenance_charges_type_id.maintenance_charges_type_line_ids:
                                    if line.product_id.id == 103:
                                        amount = False
                                        if exemption_obj:
                                            if exemption_obj.exemption_type == 'percentage' and exemption_obj.exemption_percent:
                                                amount = line.amount / 100 * (100 -exemption_obj.exemption_percent)
                                            elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'partial' and exemption_obj.exemption_amount:
                                                amount = line.amount - exemption_obj.exemption_amount
                                            elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'full':
                                                amount = 0.0
                                        else:
                                            amount = line.amount
                                        if exemption_obj and exemption_obj.exemption_nature == 'full':
                                            pass
                                        else:
                                            prod = [(0, 0, {
                                                'product_id': line.product_id.id,
                                                'name': line.product_id.name,
                                                'account_id': line.product_id.property_account_income_id.id,
                                                'price_unit': amount
                                            })]
                                            invoice = self.env['account.move'].create({
                                                'partner_id': file_rec.membership_id.id,
                                                # 'branch_id': self.env.branch.id,  # res.branch not available in this project
                                                'move_type': 'out_invoice',
                                                'maintenance_charges_id': recs.id,
                                                'invoice_date': month_first_date,
                                                'journal_id': self.env.company.account_journal_id.id,
                                                'invoice_line_ids': prod,
                                                'property_invoice_type': 'maintenance_charges',
                                            })
                                            invoice.file_ids = file_rec.id
                                            invoice.action_post()
                                            print("FILE ID:>>>>>>>", file_rec.id)
                                            print("INVOICE ID:>>>>>>>", invoice.id)

                                            file_rec.maintenance_history_ids.create({
                                                'date': month_first_date,
                                                'installment_number': installment_number,
                                                'amount': invoice.amount_total,
                                                'invoice_created': True,
                                                'invoice_id': invoice.id,
                                                'amount_paid': invoice.amount_total - invoice.amount_residual,
                                                'residual': invoice.amount_residual,
                                                'payment_status': invoice.payment_state,
                                                'file_id': file_rec.id
                                            })

    @api.model
    def society_charges_invoices(self):
        date = self.env.ref('maintenance_charges.ir_cron_society_charges').till_date or fields.Date.today()
        today_date = fields.Date.today()
        month_first_date = date.replace(day=1)
        file = self.env['file']
        for recs in self.search([('society_id.company_id', '=', self.env.company.id)]):
            for rec in recs.maintenance_charges_line_ids:
                files = file.search([('society_id', '=', recs.society_id.id),
                                     ('phase_id', '=', recs.phase_id.id),
                                     ('file_status', '!=', 'draft'),
                                     ('category_id', '=', rec.category_id.id),
                                     ('unit_class_id', '=', rec.unit_class_id.id),
                                     ('membership_id', '!=', False)])
                if recs.sector_ids:
                    files = file.search(
                        [('society_id', '=', recs.society_id.id), ('phase_id', '=', recs.phase_id.id), ('sector_id', 'in', recs.sector_ids.ids),
                         ('file_status', '!=', 'draft'),
                         ('category_id', '=', rec.category_id.id), ('unit_class_id', '=', rec.unit_class_id.id), ('membership_id', '!=', False)])
                print("TOTAL FILES >>>>>>>>>>>> ", len(files))
                for file_rec in files:
                    monthly_invoice_created = False
                    existing_invoice = self.env['account.move'].search([
                        ('file_ids', '=', file_rec.id),
                        ('partner_id', '=', file_rec.membership_id.id),
                        ('property_invoice_type', '=', 'society_charges'),
                        ('state', '=', 'posted'),
                        ('invoice_date', '>=', month_first_date),
                        ('invoice_date', '<', month_first_date + relativedelta(months=1)),
                    ], limit=1)
                    exemption_obj = self.env['maintenance.exemption.history'].search([('file_id', '=', file_rec.id), ('exemption_state', '=', 'active'), ('product_id.id', '=', 22943), ('from_date', '<=', today_date), ('to_date', '>=', today_date)])

                    if existing_invoice:
                        print(f"Invoice already exists for {file_rec.name} in {month_first_date.strftime('%B')}. Skipping...")
                        continue
                    if file_rec.maintenance_history_ids:
                        installment_number = file_rec.maintenance_history_ids[-1].installment_number + 1
                        for history in file_rec.maintenance_history_ids:
                            if history.date.month == date.month and history.date.year == date.year:
                                monthly_invoice_created = True
                    else:
                        installment_number = 1
                    if rec.maintenance_charges_type_id.unit_type == 'marla' \
                            and not monthly_invoice_created \
                            and file_rec.category_id == rec.category_id and file_rec.unit_class_id == rec.unit_class_id:
                        if round(file_rec.unit_category_type_id.area_marla) in range(rec.from_no, rec.to_no + 1):
                            if date >= recs.date_from and date <= recs.date_to:
                                for line in rec.maintenance_charges_type_id.maintenance_charges_type_line_ids:
                                    if line.product_id.id == 22943:
                                        amount = False
                                        if exemption_obj:
                                            if exemption_obj.exemption_type == 'percentage' and exemption_obj.exemption_percent:
                                                amount = line.amount / 100 * (100 - exemption_obj.exemption_percent)
                                            elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'partial' and exemption_obj.exemption_amount:
                                                amount = line.amount - exemption_obj.exemption_amount
                                            elif exemption_obj.exemption_type == 'fixed_amount' and exemption_obj.exemption_nature == 'full':
                                                amount = 0.0
                                        else:
                                            amount = line.amount
                                        if exemption_obj and exemption_obj.exemption_nature == 'full':
                                            pass
                                        else:
                                            prod = [(0, 0, {
                                                'product_id': line.product_id.id,
                                                'name': line.product_id.name,
                                                'account_id': line.product_id.property_account_income_id.id,
                                                'price_unit': amount
                                            })]
                                            invoice = self.env['account.move'].create({
                                                'partner_id': file_rec.membership_id.id,
                                                # 'branch_id': self.env.branch.id,  # res.branch not available in this project
                                                'move_type': 'out_invoice',
                                                'maintenance_charges_id': recs.id,
                                                'invoice_date': month_first_date,
                                                'journal_id': self.env.company.account_journal_id.id,
                                                'invoice_line_ids': prod,
                                                'property_invoice_type': 'society_charges',
                                            })
                                            invoice.file_ids = file_rec.id
                                            invoice.action_post()
                                            print("FILE ID:>>>>>>>", file_rec.id)
                                            print("INVOICE ID:>>>>>>>", invoice.id)

                                            file_rec.maintenance_history_ids.create({
                                                'date': month_first_date,
                                                'installment_number': installment_number,
                                                'amount': invoice.amount_total,
                                                'invoice_created': True,
                                                'invoice_id': invoice.id,
                                                'amount_paid': invoice.amount_total - invoice.amount_residual,
                                                'residual': invoice.amount_residual,
                                                'payment_status': invoice.payment_state,
                                                'file_id': file_rec.id
                                            })

    # @api.model
    # def society_charges_invoices(self):
    #     print('server charges invoices')
    #     date = self.env.ref('maintenance_charges.ir_cron_society_charges').till_date or fields.Date.today()
    #     month_first_date = date.replace(day=1)
    #     file = self.env['file']
    #     for recs in self.search([('society_id.company_id', '=', self.env.company.id)]):
    #         for rec in recs.maintenance_charges_line_ids:
    #             files = file.search([('society_id', '=', recs.society_id.id),
    #                                  ('phase_id', '=', recs.phase_id.id),
    #                                  ('file_status', '!=', 'draft'),
    #                                  ('category_id', '=', rec.category_id.id),
    #                                  ('unit_class_id', '=', rec.unit_class_id.id),
    #                                  ('membership_id', '!=', False)])
    #             if recs.sector_id:
    #                 files = file.search(
    #                     [('society_id', '=', recs.society_id.id), ('phase_id', '=', recs.phase_id.id), ('sector_id', '=', recs.sector_id.id), ('file_status', '!=', 'draft'),
    #                      ('category_id', '=', rec.category_id.id), ('unit_class_id', '=', rec.unit_class_id.id), ('membership_id', '!=', False)])
    #             print("TOTAL FILES >>>>>>>>>>>> ", len(files))
    #             for file_rec in files:
    #                 society_monthly_invoice_created = False
    #                 existing_invoice = self.env['account.move'].search([
    #                     ('file_ids', '=', file_rec.id),
    #                     ('partner_id', '=', file_rec.membership_id.id),
    #                     ('property_invoice_type', '=', 'society_charges'),
    #                     ('invoice_date', '>=', month_first_date),
    #                     ('invoice_date', '<', month_first_date + relativedelta(months=1)),
    #                 ], limit=1)
    #                 if existing_invoice:
    #                     print(f"Invoice already exists for {file_rec.name} in {month_first_date.strftime('%B')}. Skipping...")
    #                     continue
    #                 if file_rec.maintenance_history_ids:
    #                     installment_number = file_rec.maintenance_history_ids[-1].installment_number + 1
    #                     for history in file_rec.maintenance_history_ids:
    #                         if history.date.month == date.month and history.date.year == date.year:
    #                             society_monthly_invoice_created = True
    #                 else:
    #                     installment_number = 1
    #                 if (rec.maintenance_charges_type_id.unit_type == 'marla' and not society_monthly_invoice_created and file_rec.category_id == rec.category_id and
    #                         file_rec.unit_class_id
    #                         ==
    #                         rec.unit_class_id):
    #                     if round(file_rec.unit_category_type_id.area_marla) in range(rec.from_no, rec.to_no + 1):
    #                         if date >= recs.date_from and date <= recs.date_to:
    #                             for line in rec.maintenance_charges_type_id.maintenance_charges_type_line_ids:
    #                                 if line.product_id.name == 'Service Charges':
    #                                     if file_rec.service_charge:
    #                                         print('hasdfsjskdfhskj')
    #                                         prod = [(0, 0, {
    #                                             'product_id': line.product_id.id,
    #                                             'name': line.product_id.name,
    #                                             'account_id': line.product_id.property_account_income_id.id,
    #                                             'price_unit': line.amount
    #                                         })]
    #                                         invoice = self.env['account.move'].create({
    #                                             'partner_id': file_rec.membership_id.id,
    #                                             'branch_id': self.env.branch.id,
    #                                             'move_type': 'out_invoice',
    #                                             'maintenance_charges_id': recs.id,
    #                                             'invoice_date': month_first_date,
    #                                             'journal_id': self.env.company.account_journal_id.id,
    #                                             'invoice_line_ids': prod,
    #                                             'property_invoice_type': 'society_charges',
    #                                         })
    #                                         invoice.file_ids = file_rec.id
    #                                         invoice.action_post()
    #                                         print("FILE ID:>>>>>>>", file_rec.id)
    #                                         print("INVOICE ID:>>>>>>>", invoice.id)
    #
    #                                         file_rec.maintenance_history_ids.create({
    #                                             'date': month_first_date,
    #                                             'installment_number': installment_number,
    #                                             'amount': invoice.amount_total,
    #                                             'invoice_created': True,
    #                                             'invoice_id': invoice.id,
    #                                             'amount_paid': invoice.amount_total - invoice.amount_residual,
    #                                             'residual': invoice.amount_residual,
    #                                             'payment_status': invoice.payment_state,
    #                                             'file_id': file_rec.id
    #                                         })


class MaintenanceChargesLine(models.Model):
    _name = 'maintenance.charges.line'
    _description = 'Maintenance Charges Line'

    category_id = fields.Many2one('plot.category', string='Category')
    unit_class_id = fields.Many2one('unit.class')
    from_no = fields.Integer()
    to_no = fields.Integer()

    maintenance_charges_id = fields.Many2one('maintenance.charges')
    maintenance_charges_type_id = fields.Many2one('maintenance.charges.type')


class MaintenanceChargesHistory(models.Model):
    _name = 'maintenance.charges.history'
    _description = 'Maintenance Charges History'

    date = fields.Date(required=True)
    amount = fields.Float()
    installment_number = fields.Integer(readonly=False)
    invoice_created = fields.Boolean(default=False)
    invoice_id = fields.Many2one('account.move')
    state = fields.Char(string='Status', readonly=False, related='invoice_id.invoice_way_type')
    file_id = fields.Many2one('file')

    payment_date = fields.Date('Payment Date', store=True, compute='_payment_date', readonly=False)
    amount_paid = fields.Float('Amount Paid', store=True, compute='_invoice_id_data', readonly=False)
    residual = fields.Float('Amount Due', store=True, compute='_invoice_id_data', readonly=False)
    payment_status = fields.Selection(selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid')],
        string='Payment', store=True, readonly=False, copy=False, tracking=True,
        related='invoice_id.payment_state')
    double_check_paid_amount = fields.Boolean(compute="_double_check_paid_amount")

    @api.depends('invoice_created', 'invoice_id', 'amount_paid')
    def _payment_date(self):
        for rec in self:
            if rec.invoice_created:
                date = rec.env['account.payment'].search([
                    # ('id', 'in', rec.invoice_id.payment_ids.ids),
                    ('state', '=', 'posted'),
                    ('multi_invoice_ids.invoice_id', '=', rec.invoice_id.id)
                ], limit=1, order='id desc')

                rec.payment_date = dateutil.parser.parse(str(date.payment_date)) if date else ''
            else:
                rec.payment_date = ''

    def _double_check_paid_amount(self):
        for rec in self:
            if rec.invoice_id and rec.amount_paid != rec.invoice_id.amount_total - rec.invoice_id.amount_residual:
                rec._invoice_id_data()
            rec.double_check_paid_amount = True

    @api.depends('invoice_id', 'invoice_id.amount_residual', )
    def _invoice_id_data(self):
        for rec in self:
            rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
            rec.residual = rec.invoice_id.amount_residual

    def unlink(self):
        for rec in self:
            if rec.invoice_created:
                raise ValidationError(_('You cannot delete record when invoice is created!'))

        return super(MaintenanceChargesHistory, self).unlink()
