from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, time
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class AllotmentRequestBatch(models.Model):
    _name = 'allotment.request.batch'
    _description = 'Allotment Request Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char("Allotment Request Number", required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))

    society_id = fields.Many2one('society', 'Society', domain="[('is_society','=',True)]", required=True)
    phase_id = fields.Many2one('society', 'Phase', domain="[('is_society','!=',True)]")

    category_id = fields.Many2one('plot.category', string='Plot Category')
    unit_category_type_id = fields.Many2one('unit.category.type', string='Product')

    sector_id = fields.Many2one('sector', string='Sector')
    street_id = fields.Many2one('street', string='Street')

    approved_date = fields.Date('Aprroved Date', readonly=True, tracking=True)
    approved_responsibe_id = fields.Many2one('res.users', 'Aprroved By', readonly=True)
    date_from = fields.Date(string='Date From', readonly=True, required=True, help="Start date",
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
                            states={'draft': [('readonly', False)]})
    date_to = fields.Date(string='Date To', readonly=True, required=True, help="End date",
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()),
                          states={'draft': [('readonly', False)]})

    issued_date = fields.Date('Issued Date', readonly=True)
    issued_responsibe_id = fields.Many2one('res.users', 'Issued By', readonly=True)

    printed_date = fields.Date('Printed Date', readonly=True)
    printed_responsibe_id = fields.Many2one('res.users', 'Printed By', readonly=True)

    canceled_date = fields.Date('Canceled Date', readonly=True)
    canceled_responsibe_id = fields.Many2one('res.users', 'Cancelled By', readonly=True)

    state = fields.Selection([
        ('draft', 'Submit'),
        ('preview', 'Review'),
        ('approve', 'Approved'),
        ('print', 'Printed'),
        ('issued', 'Issued'),
        ('cancel', 'Cancel')
    ], default='draft', tracking=True)

    allotment_request_ids = fields.One2many('allotment.request', 'batch_id', string='Files')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code("allotment.batch.sequence") or _('New')
        return super().create(vals_list)

    @api.onchange('society_id', 'phase_id', 'sector_id')
    def _inventory_domain(self):
        return {'domain': {
            'phase_id': [('society_id', '=', self.society_id.id)],
            'sector_id': [('phase_id', '=', self.phase_id.id)],
            'street_id': [('sector_id', '=', self.sector_id.id)]
        }
        }

    def _get_domain(self):
        domain = []
        if self.society_id:
            domain.append(('society_id', '=', self.society_id.id))
        elif self.phase_id:
            domain.append(('phase_id', '=', self.phase_id.id))
        elif self.category_id:
            domain.append(('category_id', '=', self.category_id.id))
        elif self.unit_category_type_id:
            domain.append(('unit_category_type_id', '=', self.unit_category_type_id.id))
        return domain

    def generate_files(self):
        # self.allotment_request_ids.unlink()
        domain = self._get_domain()
        # if self.date_from:
        #     domain.append(('date', '>=', self.date_from))
        # if self.date_to:
        #     domain.append(('date', '<=', self.date_to))

        requests = self.env['allotment.request'].search(domain)
        self.allotment_request_ids = [(6, 0, requests.ids)]

    def generate_allotment(self):
        domain = self._get_domain()
        domain.append(('state', '=', 'available_for_sale'))
        if self.sector_id:
            domain.append(('sector_id', '=', self.sector_id.id))
        if self.street_id:
            domain.append(('street_id', '=', self.street_id.id))
        inventory_ids = self.env['plot.inventory'].search(domain)
        total_available_invenotory = self.env['plot.inventory'].search_count(domain)

        for request in self.allotment_request_ids:
            if total_available_invenotory:
                for plot in inventory_ids.filtered(lambda line: line.state == 'available_for_sale'):
                    request.write({'sector_id': plot.sector_id.id, 'street_id': plot.street_id.id})
                    request.file_id.write({'sector_id': plot.sector_id.id, 'street_id': plot.street_id.id})
            else:
                break

    def action_preview(self):
        self.ensure_one()
        return self.write({'stata': 'preview'})

    def action_approve(self):
        self.ensure_one()
        return self.write({'stata': 'approve'})

    def action_print(self):
        self.ensure_one()
        return self.write({'stata': 'print'})

    def action_issue(self):
        self.ensure_one()
        return self.write({'stata': 'issued'})

    def action_cancel(self):
        self.ensure_one()
        return self.write({'stata': 'cancel'})
