import json
import requests
from odoo import fields, models, api
from odoo.exceptions import ValidationError
from os.path import dirname, realpath


class PlotInventoryExt(models.Model):
    _inherit = 'plot.inventory'

    @api.model
    def get_inventory_details(self, **kwargs):
        domain = kwargs["domain"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]
        records = self.env['plot.inventory'].search(domain, limit=limit, offset=offset)
        files = self.env['file'].search([('inventory_id','in', records.ids),('state','=', 'available')])
        data = []
        for file in files:
            total_due = sum(self.env['account.move'].search([('file_ids', '=', file.id),
                                                         ('payment_state', '!=', 'paid'),
                                                         ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            if total_due > 0:
                maintenance_payment = {
                    'file_id': file.id,
                    'street_id': file.street_id.display_name,
                    'file_name': file.display_name,
                    'plot_id': file.inventory_id.id,
                    'inventory_id': file.inventory_id.name,
                    'membership_id': file.membership_id.display_name,
                    'sector_id': file.sector_id.display_name,
                    'category_id': file.category_id.display_name,
                    'unit_category_type_id': file.unit_category_type_id.display_name,
                    'unit_class_id': file.unit_class_id.display_name,
                    'size_id': file.size_id.display_name,
                    'plot_status': file.plot_state.replace('_',' ').title(),
                    'total_due_amount': total_due,
                    'invoice_ids': self.env['account.move'].search_read(
                        [('file_ids', '=', file.id), ('payment_state', '!=', 'paid'),
                         ('property_invoice_type', '=', 'maintenance_charges')],
                        # 'fiscal_month_id' removed: not a real field on account.move (belongs to
                        # daily.maintenance.batch in maintenance_recovery_batch; its comodel fiscal.month
                        # is not defined anywhere in this project) - pre-existing gap, kept commented not deleted
                        ['id', 'name', 'invoice_date_due', 'amount_total_signed', 'amount_residual_signed',
                         'payment_state'])
                }
                data.append(maintenance_payment)

        return data

    @api.model
    def get_invoices_and_files(self, **kwargs):
        user = kwargs['uid']
        invoices = self.env['account.move'].search([('payment_state', '!=', 'paid'),
                                                    ('file_ids.unit_class_id.name', '=', 'House'),
                                                    ('file_ids.maintenance_recovery_agent_id', '=', user),
                                                     ('property_invoice_type', '=', 'maintenance_charges')])
        # files = self.env['file'].search([('inventory_id','in', records.ids),('state','=', 'available')])
        data = []
        for rec in invoices:
            total_due = sum(self.env['account.move'].search([('file_ids', '=', rec.file_ids.id),
                                                             ('file_ids.unit_class_id.name', '=', 'House'),
                                                             ('file_ids.maintenance_recovery_agent_id', '=', user),
                                                             ('payment_state', '!=', 'paid'),
                                                             ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            if total_due > 0:
                maintenance_payment = {
                    'file_id': rec.file_ids.id,
                    'street_id': rec.file_ids.street_id.display_name,
                    'street_db_id': rec.file_ids.street_id.id,
                    'file_name': rec.file_ids.display_name,
                    'plot_id': rec.file_ids.inventory_id.id,
                    'inventory_id': rec.file_ids.inventory_id.name,
                    'membership_id': rec.file_ids.membership_id.display_name,
                    'sector_id': rec.file_ids.sector_id.display_name,
                    'sector_db_id': rec.file_ids.sector_id.id,
                    'category_id': rec.file_ids.category_id.display_name,
                    'unit_category_type_id': rec.file_ids.unit_category_type_id.display_name,
                    'unit_class_id': rec.file_ids.unit_class_id.display_name,
                    'size_id': rec.file_ids.size_id.display_name,
                    'plot_status': rec.file_ids.plot_state.replace('_',' ').title(),
                    'total_due_amount': total_due,
                    'invoice_id': rec.id,
                    'invoice_number': rec.name,
                    'invoice_date_due': str(rec.invoice_date_due),
                    'amount_total_signed': rec.amount_total_signed,
                    'amount_residual_signed': rec.amount_residual_signed,
                    'payment_state': rec.payment_state,
                    # 'invoice_month': rec.fiscal_month_id.name,  # fiscal_month_id does not exist on account.move (see note above); key kept for API shape
                    'invoice_month': False,
                    'maintenance_agent': rec.file_ids.maintenance_recovery_agent_id.name,
                    'maintenance_agent_id': rec.file_ids.maintenance_recovery_agent_id.id,
                }
                data.append(maintenance_payment)

        if data:
            #     rec.synced_to_app = True

            return json.dumps(data)

    def get_invoice_query(self, **kwargs):
        user = kwargs["uid"]
        cr = self.env.cr
        cr.execute(f"""
                    select 
                            f.id as file_id,
                            st.name as street_id,
                            st.id as street_db_id,
                            f.name as file_name,
                            inv.id as plot_id,
                            inv.name as inventory_id,
                            rp.display_name as membership_id,
                            sec.name as sector_id,
                            sec.id as sector_db_id,
                            cat.name as category_id,
                            uct.name as unit_category_type_id,
                            uc.name as unit_class_id,
                            us.name as size_id,
                            am.id as invoice_id,
                            am.name as invoice_number,
                            cast(am.invoice_date_due as VARCHAR) as invoice_date_due,
                            am.amount_total_signed as amount_total_signed,
                            am.amount_residual_signed as amount_residual_signed,
                            am.payment_state as payment_state,
                            f.maintenance_recovery_agent_id as maintenance_agent_id
                    from file f 
                    inner join account_move am on am.file_ids=f.id
                    LEFT join res_partner rp on f.membership_id = rp.id
                    LEFT JOIN society s  ON f.society_id = s.id
                    LEFT JOIN society ph  ON f.phase_id = ph.id
                    LEFT JOIN sector sec  ON f.sector_id = sec.id
                    LEFT JOIN street st  ON f.street_id = st.id
                    LEFT JOIN plot_inventory inv  ON f.inventory_id = inv.id
                    LEFT JOIN plot_category cat  ON f.category_id = cat.id
                    LEFT JOIN unit_category_type uct  ON f.unit_category_type_id = uct.id
                    LEFT JOIN unit_size us  ON f.size_id = us.id
                    LEFT JOIN unit_class uc ON f.unit_class_id = uc.id
                    where am.payment_state != 'paid' 
                    and am.property_invoice_type = 'maintenance_charges'
                    and am.file_ids in (select id from file where unit_class_id = 6)
                    and f.maintenance_recovery_agent_id = {user}
                                        """)
        result = cr.dictfetchall()
        return json.dumps(result)

    @api.model
    def search_inventory_details(self, **kwargs):
        name = kwargs["name"]
        records = self.env['plot.inventory'].search([('name', '=', name)])
        file = self.env['file'].search([('inventory_id','in', records.ids),('state','=', 'available')], limit=1)
        data = []

        if file:
            total_due = sum(self.env['account.move'].search([('file_ids', '=', file.id),
                                                         ('payment_state', '!=', 'paid'),
                                                         ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            if total_due > 0:
                maintenance_payment = {
                    'file_id': file.id,
                    'street_id': file.street_id.display_name,
                    'file_name': file.display_name,
                    'plot_id': file.inventory_id.id,
                    'inventory_id': file.inventory_id.name,
                    'membership_id': file.membership_id.display_name,
                    'sector_id': file.sector_id.display_name,
                    'category_id': file.category_id.display_name,
                    'unit_category_type_id': file.unit_category_type_id.display_name,
                    'unit_class_id': file.unit_class_id.display_name,
                    'size_id': file.size_id.display_name,
                    'plot_status': file.plot_state.replace('_',' ').title(),
                    'total_due_amount': total_due,
                    'invoice_ids': self.env['account.move'].search_read(
                        [('file_ids', '=', file.id), ('payment_state', '!=', 'paid'),
                         ('property_invoice_type', '=', 'maintenance_charges')],
                        # 'fiscal_month_id' removed: not a real field on account.move, see note above
                        ['id', 'name', 'invoice_date_due', 'amount_total_signed', 'amount_residual_signed',
                         'payment_state'])
                }
                data.append(maintenance_payment)

            return data
        else:
            return json.dumps({'error': 'No record found!'})

    @api.model
    def create_unit_type_request(self, **kwargs):
        record = self.env['unit.class'].browse(kwargs['data']['unit_class_id'])
        file = self.env['file'].search([('inventory_id','=',self.id)])
        vals = {
            'from_app': True,
            'date': fields.Date.today(),
            'society_id': file.society_id.id,
            'phase_id': file.phase_id.id,
            'sector_id': file.sector_id.id,
            'file_id': file.id,
            'tracking_id': file.tracking_id,
            'street_id': file.street_id.id,
            'inventory_id': self.id,
            'membership_id': file.membership_id.id,
            'category_id': file.category_id.id,
            'unit_category_type_id': file.unit_category_type_id.id,
            'unit_class_id': file.unit_class_id.id,
            'new_unit_class_id': record.id,
            'size_id': file.size_id.id,
        }
        old_record = self.env['change.unit.type'].search([('file_id','=',file.id)])
        if old_record:
            raise ValidationError("Record already exists against this plot.")

        unit_type_request = self.env['change.unit.type'].create(vals)
        file.state = 'inprocess'
        if unit_type_request:
            return json.dumps({'Success': "Unit Type Request created successfully", 'status': 200})
        else:
            return json.dumps({'error': "No record created.", 'status': 400})

    @api.model
    def get_streets(self,**kwargs):
        domain = kwargs["domain"]
        other_data = kwargs["other_data"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]
        records = self.env['street'].search(domain, limit=limit, offset=offset)

        data = []
        for rec in records:
            file_count = 0
            plots = self.env['plot.inventory'].search([('street_id','=',rec.id),('unit_class_id.code','=','HS')]) if 'True' in other_data else self.env['plot.inventory'].search([('street_id','=',rec.id),('unit_class_id.code','=','PLT')])
            if 'True' in other_data:
                files = self.env['file'].search([('inventory_id', 'in', plots.ids),('state','=','available')])

                # for file in files:
                total_due = sum(self.env['account.move'].search([('file_ids', 'in', files.ids),
                                                     ('payment_state', '!=', 'paid'),
                                                     ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
                if total_due > 0:
                    file_count += + 1
            else:
                files = self.env['file'].search([('inventory_id','in',plots.ids)])
            amount = sum(self.env['account.move'].search([('file_ids','in',files.ids),
                                                          ('payment_state','!=','paid'),
                                                          ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            payments = self.env['multi.invoice.payment'].search([('invoice_id.file_ids','in',files.ids),
                                                          ('state','=','posted'),
                                                          ('invoice_id.property_invoice_type', '=', 'maintenance_charges')]).mapped('payment_id')
            payment_amount_current_month = sum(payments.filtered(lambda l: l.payment_date.month == fields.Date.today().month and l.payment_date.year == fields.Date.today().year).mapped('amount'))
            streets = {
                'id': rec.id,
                'name': rec.name,
                'sector_id': rec.sector_id.name,
                'total_street_receivable': amount,
                'total_street_amount_received': payment_amount_current_month,
                'total_plots': len(plots),
                'total_files': file_count if 'True' in other_data else len(files)
            }
            data.append(streets)

        return data

    @api.model
    def search_streets(self,**kwargs):
        name = kwargs["name"]
        other_data = kwargs["other_data"]
        street = self.env['street'].search([('name', '=', name)], limit=1)
        data = []
        if street:
            file_count = 0
            plots = self.env['plot.inventory'].search([('street_id','=',street.id),('unit_class_id.code','=','HS')]) if 'True' in other_data else self.env['plot.inventory'].search([('street_id','=',street.id),('unit_class_id.code','=','PLT')])
            if 'True' in other_data:
                files = self.env['file'].search([('inventory_id', 'in', plots.ids),('state','=','available')])

                # for file in files:
                total_due = sum(self.env['account.move'].search([('file_ids', 'in', files.ids),
                                                     ('payment_state', '!=', 'paid'),
                                                     ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
                if total_due > 0:
                    file_count += + 1
            else:
                files = self.env['file'].search([('inventory_id','in',plots.ids)])
            amount = sum(self.env['account.move'].search([('file_ids','in',files.ids),
                                                          ('payment_state','!=','paid'),
                                                          ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            payments = self.env['multi.invoice.payment'].search([('invoice_id.file_ids','in',files.ids),
                                                          ('state','=','posted'),
                                                          ('invoice_id.property_invoice_type', '=', 'maintenance_charges')]).mapped('payment_id')
            payment_amount_current_month = sum(payments.filtered(lambda l: l.payment_date.month == fields.Date.today().month and l.payment_date.year == fields.Date.today().year).mapped('amount'))
            streets = {
                'id': street.id,
                'name': street.name,
                'sector_id': street.sector_id.name,
                'total_street_receivable': amount,
                'total_street_amount_received': payment_amount_current_month,
                'total_plots': len(plots),
                'total_files': file_count if 'True' in other_data else len(files)
            }
            data.append(streets)

            return data
        else:
            return json.dumps({'error': 'No record found!'})

    @api.model
    def get_sector_data(self,**kwargs):
        limit = 0
        offset = 0
        if kwargs.get("limit", limit):
            limit = int(kwargs["limit"])
        if kwargs.get("offset", offset):
            offset = int(kwargs["offset"])
        records = self.env['sector'].search([('project_type','=', 'housing_society')], limit=limit, offset=offset)

        data = []
        for rec in records:
            plots = self.env['plot.inventory'].search([('sector_id','=',rec.id),('unit_class_id.code','=','HS')])
            files = self.env['file'].search([('inventory_id', 'in', plots.ids),('state','=','available')])
            amount = sum(self.env['account.move'].search([('file_ids','in',files.ids),
                                                          ('payment_state','!=','paid'),
                                                          ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            payments = self.env['multi.invoice.payment'].search([('invoice_id.file_ids','in',files.ids),
                                                          ('state','=','posted'),
                                                          ('invoice_id.property_invoice_type', '=', 'maintenance_charges')]).mapped('payment_id')
            payment_amount_current_month = sum(payments.filtered(lambda l: l.payment_date.month == fields.Date.today().month and l.payment_date.year == fields.Date.today().year).mapped('amount'))
            sector_info = {
                'sector_id': rec.id,
                'name': rec.name,
                'total_sector_receivable': amount,
                'total_sector_amount_received': payment_amount_current_month,
                'total_plots': len(plots),
                'total_files': len(files),
            }
            data.append(sector_info)

        return json.dumps(data)

    @api.model
    def search_sector(self,**kwargs):
        name = kwargs["name"]
        sector = self.env['sector'].search([('project_type','=', 'housing_society'),('name', '=', name)], limit=1)

        if sector:
            plots = self.env['plot.inventory'].search([('sector_id','=',sector.id),('unit_class_id.code','=','HS')])
            files = self.env['file'].search([('inventory_id', 'in', plots.ids),('state','=','available')])
            amount = sum(self.env['account.move'].search([('file_ids','in',files.ids),
                                                          ('payment_state','!=','paid'),
                                                          ('property_invoice_type', '=', 'maintenance_charges')]).mapped('amount_residual_signed'))
            payments = self.env['multi.invoice.payment'].search([('invoice_id.file_ids','in',files.ids),
                                                          ('state','=','posted'),
                                                          ('invoice_id.property_invoice_type', '=', 'maintenance_charges')]).mapped('payment_id')
            payment_amount_current_month = sum(payments.filtered(lambda l: l.payment_date.month == fields.Date.today().month and l.payment_date.year == fields.Date.today().year).mapped('amount'))
            sector_info = {
                'sector_id': sector.id,
                'name': sector.name,
                'total_sector_receivable': amount,
                'total_sector_amount_received': payment_amount_current_month,
                'total_plots': len(plots),
                'total_files': len(files),
            }

            return sector_info
        else:
            return json.dumps({'error': 'No record found!'})

    @api.model
    def get_unit_types(self):
        records = self.env['unit.class'].search([('project_type','=','housing_society')])
        data = []
        for rec in records:
            type = { 'id': rec.id,
                     'name': rec.name,
                     'code': rec.code,

            }
            data.append(type)

        return json.dumps(data)