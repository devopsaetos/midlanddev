from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import json


class ComparativeStatement(models.Model):
    _name = 'comparative.statement'
    _description = "Comparative Statement"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    _rec_name = 'sequence'
    sequence = fields.Char(string='Sequence', readonly=True, copy=False)
    rfq_id = fields.Many2one('requisition.order', domain=[('state', '=', 'approved')], string='RFQ Number')
    quotation_order_id = fields.Many2one('quotation.order', string='Quotation')
    creation_date = fields.Date('Creation Date', default=fields.Date.today())
    closure_date = fields.Date('Closure Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
    ], default='draft', track_visibility='always')

    comparative_statement_line_ids = fields.One2many('comparative.statement.line', 'comparative_statement_id')

    def make_approve(self):
        self.write({'state': 'approve'})


    # @api.onchange('rfq_id')
    # def rfq_selection_validation(self):
    #     return {'domain': {'rfq_id': [set(self.env['requisition.order'].search([])) - set(self.env['comparative.statement'].search([]).rfq_id)]}}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['sequence'] = self.env['ir.sequence'].next_by_code('comparative.statement') or '/'
        res = super(ComparativeStatement, self).create(vals_list)
        return res

    @api.model
    def show_comparative_statement(self, rfq_id):
        domain = [
            ('display_type', 'not in', ('line_section', 'line_note'))]
        if rfq_id:
            domain.append(('requisition_rfq_id.id', '=', rfq_id))
        quotation_line_ids = self.env['quotation.order.line'].search(domain)
        if not all(line.state == 'quotation' for line in quotation_line_ids):
            raise UserError('All Quotations against this RFQ are not approved please approve them first to create a comparative statement')
        data = quotation_line_ids.read(['product_qty','price_unit','price_total', 'product_id', 'product_uom','partner_id','order_id'])

        dataframe_lines = []
        for quot in quotation_line_ids:
            record_set = {
                'product_qty': (quot.product_qty, quot.price_unit, quot.price_total),
                'product_info':  quot.product_id.name+"("+quot.name+")" + "/" + (quot.product_uom.name or "No") + "/" + str(quot.rfq_qty) + "/" + str(quot.expected_price) ,
                'vendor_name': quot.order_id.partner_id.name + "," + str(quot.order_id.id)
            }
            dataframe_lines.append(record_set)
        dataframe = pd.DataFrame(dataframe_lines)
        dataframe_pivot = dataframe.pivot(index='product_info', columns='vendor_name', values='product_qty')
        df_change_index = dataframe_pivot.reset_index('product_info')
        df_change_index[['Product', 'Unit', 'RFQ Qty', 'Expected Price']] = df_change_index['product_info'].str.split("/", expand=True)
        df_column_drop = df_change_index.drop('product_info', axis='columns')
        df_columns = df_column_drop.columns.tolist()
        df_reorder_columns = df_columns[-4:] + df_columns[:-4]
        df_reshape = df_column_drop[df_reorder_columns]
        dataframe_json = df_reshape.to_json(orient='records')
        return dataframe_json

    @api.model
    def prepare_lines_data(self, json_data):
        df = pd.read_json(json_data)
        df_reset_indx = df.reset_index()
        lines_values = df.values.tolist()
        new_lines = []
        for line in lines_values:
            new_line = []
            for cell in line:
                if cell is None:
                    new_line.append(0)
                    new_line.append(0)
                    new_line.append(0)
                    new_line.append(0)
                elif isinstance(cell, list):
                    new_line += cell
                else:
                    new_line.append(cell)
            new_lines.append(new_line)

        json_data = json.dumps(new_lines)

        return json_data

    @api.model
    def prepare_vendor_citreia_lines(self, data):
        recod_data = json.loads(data)
        record_set_list = [int(rec['1']) for rec in recod_data if rec['1']]
        evaluation_connector = self.env['evaluation.connector'].search([('quotation_order_id', 'in', record_set_list)])
        if evaluation_connector:
            dict_record = evaluation_connector.read(['field_id', 'value', 'quotation_order_id'])
            df = pd.DataFrame(dict_record)
            df['field_id'] = [rec[1] for rec in df['field_id']]
            df['quotation_order_id'] = [rec[0] for rec in df['quotation_order_id']]
            df_pivot = df.pivot(index='field_id', columns='quotation_order_id', values='value').reset_index()
            json_records = df_pivot.to_json(orient='records')
            return json_records
        return json.dumps({})

    @api.model
    def prepare_total_qoutations(self, data):
        recod_data = json.loads(data)
        # record_set_list = [int(rec['1']) for rec in recod_data if rec['1']]
        # quotations = self.env['quotation.order'].browse(record_set_list)
        new_record = {}
        for quot in recod_data:
            new_record[quot['1']] = self.env['quotation.order'].browse(int(quot['1'])).amount_total

        return json.dumps(new_record)

    @api.model
    def approve_quotation(self, qoutation_id, comparative_statement_id):
        comparative = self.browse(comparative_statement_id)
        quotation_order = self.env['quotation.order'].browse(comparative_statement_id).id
        comparative.write({'quotation_order_id': quotation_order, 'state': 'approve'})
        quotation_id = str(quotation_order)
        return json.dumps(quotation_id)

    def show_vendor_dashboard(self):
        action_context = {'rfq_id': self.rfq_id.id, 'rfq_code': self.rfq_id.name,
                          'rfq_date': self.rfq_id.creation_date,
                          'state': self.state,
                          'comparative_statement_id': self.id
                          }
        return {
            'type': 'ir.actions.client',
            'tag': 'comparative_statement_view',
            'context': action_context,
        }


class ComparativeStatementLines(models.Model):
    _name = 'comparative.statement.line'
    _description = "Comparative Statement Line"

    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)])
    price_unit = fields.Float(string='Unit Price')
    partner_id = fields.Many2one('res.partner', string='Vendor')
    comparative_statement_id = fields.Many2one('comparative.statement', ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in progress', 'In Progress'),
    ], related='comparative_statement_id.state')

