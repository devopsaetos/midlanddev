from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PlotMergerExt(models.TransientModel):
    _inherit = 'plot.merger'

    visibility_check = fields.Boolean(default=False)
    membership_source_id = fields.Many2one('res.member', string='Member From')
    membership_target_id = fields.Many2one('res.member', string='Member To')
    # member_cnic = fields.Char()
    cnic = fields.Char()
    tar_member_cnic = fields.Char()
    merger_type = fields.Selection(
        string='Merger Type',
        selection=[('same_member', 'Same Member'),
                   ('member_to_member', 'Member To Member')],
        required=False, default='same_member')
    waive_merger_application = fields.Selection(
        string='Waive Fee ?',
        selection=[('yes', 'Yes'),
                   ('no', 'No')],
        default="no", required=False, track_visility='always')
    appointment_date = fields.Date(string='Application Date')
    notes = fields.Text(string='Remarks')

    def search_file_related_record(self):
        self.file_merger_line.unlink()

        # Initialize the domain with file status conditions
        domain = [('file_status', 'not in', ['cancel', 'merged_and_cancel'])]
        cnic_domain = []
        if self.cnic:
            cnic_domain.append(('membership_id.cnic', '=', self.cnic))
        if self.tar_member_cnic:
            cnic_domain.append(('membership_id.cnic', '=', self.tar_member_cnic))
        if cnic_domain:
            if len(cnic_domain) > 1:
                domain += ['|'] + cnic_domain
            else:
                domain += cnic_domain
        membership_domain = []
        if self.membership_source_id:
            membership_domain.append(('membership_id', '=', self.membership_source_id.id))
        if self.membership_target_id:
            membership_domain.append(('membership_id', '=', self.membership_target_id.id))
        if membership_domain:
            if len(membership_domain) > 1:
                domain += ['|'] + membership_domain
            else:
                domain += membership_domain

        file_line_records = self.env['file'].search(domain)
        for rec in file_line_records:
            self.file_merger_line.create({
                'file_id': rec.id,
                'file_merger_id': self.id,
            })
        return {
            'context': self.env.context,
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def initiate_merjer(self):
        if not self.membership_source_id and not self.cnic:
            raise ValidationError(_("Please select the member first"))

        merger_vals = {}
        if self.membership_source_id and not self.membership_target_id:
            merger_vals.update({
                'membership_id': self.membership_source_id.id,
                'merger_status': 'process'
            })

        elif self.membership_source_id and self.membership_target_id:
            merger_vals.update({
                'membership_id': self.membership_source_id.id,
                'membership_merge_to_id': self.membership_target_id.id,
                'merger_request': True,
                'merger_status': 'process'
            })

        elif self.cnic and not self.tar_member_cnic:
            member_record = self.env['res.member'].search([('cnic', '=', self.cnic)], limit=1)
            merger_vals.update({
                'membership_id': member_record.id,
                'merger_status': 'process'
            })

        elif self.cnic and self.tar_member_cnic:
            member_record = self.env['res.member'].search([('cnic', '=', self.cnic)], limit=1)
            tar_member_record = self.env['res.member'].search([('cnic', '=', self.tar_member_cnic)], limit=1)
            merger_vals.update({
                'membership_id': member_record.id,
                'membership_merge_to_id': tar_member_record.id,
                'merger_request': True,
                'merger_status': 'process'
            })
        merger_vals.update({
            'waive_merger_application': self.waive_merger_application,
            'appointment_date': self.appointment_date,
            'notes': self.notes
        })
        if merger_vals:
            merger_lines = []
            for line in self.file_merger_line:
                merger_lines.append((0, 0, {
                    'membership_id': line.membership_id.id,
                    'file_id': line.file_id.id,
                    'state': line.state,
                    'source': line.source,
                    'target': line.target,
                    'total_sale_amount': line.total_sale_amount,
                    'ttl_invoiced_amount': line.ttl_invoiced_amount,
                    'amount_received': line.amount_received,
                    'amount_remaining': line.amount_remaining,
                }))
            merger_request_vals = {
                'membership_id': self.membership_id.id,
                'file_id': self.file_id.id,
                'visibility_check': self.visibility_check,
                # 'file_payment_history_id': self.file_payment_history_id,
                'plan_description': self.plan_description,
                'payment_states': self.payment_states,
                'interval_id': self.interval_id.id,
                'total_installment': self.total_installment,
                'starting_date': self.starting_date,
                'sale_amount': self.sale_amount,
                'factor_amount': self.factor_amount,
                'ttl_sale_amount': self.ttl_sale_amount,
                'discount_type': self.discount_type,
                'discount_amount': self.discount_amount,
                'net_sale_amount': self.net_sale_amount,
                'balance_amount': self.balance_amount,
                'installment_created': self.installment_created,
                'initial_payment': self.initial_payment,
                'membership_source_id': self.membership_source_id.id,
                'membership_target_id': self.membership_target_id.id,
                'cnic': self.cnic,
                'tar_member_cnic': self.tar_member_cnic,
                'merger_type': self.merger_type,
                'waive_merger_application': self.waive_merger_application,
                'appointment_date': self.appointment_date,
                'notes': self.notes,
                'file_merger_request_line': merger_lines,
                'state': 'submitted'
            }
            merger_request = self.env['file.merger.request'].sudo().create(merger_request_vals)
            if merger_request:
                merger_vals.update({'file_merger_request_id': merger_request.id})
            merger_application = self.env['plot.merger.application'].with_context(active_id=False).create(merger_vals)
            if merger_application:
                for source in self.file_merger_line:
                    if source.source:
                        line_vals = {
                            'file_merger_application_id': merger_application.id,
                            'file_id': source.file_id.id,
                        }
                        self.env['source.merger'].create(line_vals)

                    if source.target:
                        line_vals = {
                            'plot_target_application_id': merger_application.id,
                            'file_id': source.file_id.id,
                        }
                        self.env['target.merger'].create(line_vals)
                return {
                    'name': 'Merger Request',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'file.merger.request',
                    'res_id': merger_request.id
                }


class PlotMergerLineExt(models.TransientModel):
    _inherit = 'plot.merger.line'

    source = fields.Boolean(string='Source')
    target = fields.Boolean(string='Target')
    total_sale_amount = fields.Float(string='Sale Amount', related='file_id.ttl_sale_amount')
    ttl_invoiced_amount = fields.Float(compute="_compute_file_detail", store=True, string='Invoiced Amount')
    amount_received = fields.Float('Received', compute="_compute_file_detail", store=True)
    amount_remaining = fields.Float('Remaining', compute="_compute_file_detail", store=True)

    def open_payment_plan(self):
        self.file_merger_id.visibility_check = True
        for rec in self.search([('state', '=', 'close')]):
            rec.state = 'open'
        self.file_merger_id.file_id = self.file_id
        self.state = 'close'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'file',
            'view_mode': 'form',
            'res_id': self.file_id.id,
            'target': 'current',
            # 'type': 'ir.actions.do_nothing'
        }

    @api.depends('file_id')
    def _compute_file_detail(self):
        for line in self:
            if line.file_id:
                # assignment of active installment plan line
                if line.file_id.manual_installment_plan_ids:
                    installment_plan = line.file_id.manual_installment_plan_ids
                elif line.file_id.installment_plan_ids:
                    installment_plan = line.file_id.installment_plan_ids
                else:
                    raise ValidationError(_('File installment plan is not created %s' % line.file_id.tracking_id))
                invoices = installment_plan.filtered(lambda l: l.invoice_created)
                line.ttl_invoiced_amount = sum(inv.amount for inv in invoices)
                line.amount_received = sum(inv.amount_paid for inv in invoices)
                line.amount_remaining = sum(inv.residual for inv in invoices)
            else:
                self.ttl_invoiced_amount = 0.0
                self.amount_received = 0.0
                self.amount_remaining = 0.0
