# -*- coding: utf-8 -*-

import ast
import base64
import binascii
import io
import os

import pandas as pd
from odoo.addons.ks_dashboard_ninja.common_lib.ks_utils import get_orderby, am_format_read_group_data, \
    replace_new_id, list_format_read_group_data, card_format_read_group_data, split_field_name, format_raw_value
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import SQL

from odoo import models, fields, api, _

SQL_AGGREGATE_FUNCTIONS = ['count', 'count_distinct', 'sum', 'avg', 'min', 'max']

BASIC_AGGREGATE_FUNCTIONS = ['count', 'count_distinct']

NUMERIC_FIELD_TYPE_AGGREGATE_MAP = {
    'integer': SQL_AGGREGATE_FUNCTIONS,
    'float': SQL_AGGREGATE_FUNCTIONS,
    'monetary': SQL_AGGREGATE_FUNCTIONS,
    'text': BASIC_AGGREGATE_FUNCTIONS,
    'char': BASIC_AGGREGATE_FUNCTIONS,
    'selection': BASIC_AGGREGATE_FUNCTIONS,
    'boolean': BASIC_AGGREGATE_FUNCTIONS,
    'many2one': BASIC_AGGREGATE_FUNCTIONS,
    'html': BASIC_AGGREGATE_FUNCTIONS,
    'date': BASIC_AGGREGATE_FUNCTIONS,
    'datetime': BASIC_AGGREGATE_FUNCTIONS,
}

COMMON_FIELD_TYPE_AGGREGATE_MAP = {
    'integer': SQL_AGGREGATE_FUNCTIONS,
    'float': SQL_AGGREGATE_FUNCTIONS,
    'monetary': SQL_AGGREGATE_FUNCTIONS,
    'text': ['count', 'count_distinct', 'min', 'max'],
    'char': ['count', 'count_distinct', 'min', 'max'],
    'selection': ['count', 'count_distinct', 'min', 'max'],
    'boolean': ['count', 'count_distinct', 'bool_and', 'bool_or'],
    'many2one': BASIC_AGGREGATE_FUNCTIONS,
    'html': BASIC_AGGREGATE_FUNCTIONS,
    'date': ['count', 'count_distinct', 'min', 'max'],
    'datetime': ['count', 'count_distinct', 'min', 'max'],
}

ITEM_TYPE_METADATA = {
    'card': {
        'name': 'Card', 'type': 'card', 'card_format': True, 'is_formula_supported': True,
    },
    'xy_chart': {
        'name': 'XY Chart', 'type': 'xy_chart', 'available_types': [('bar', 'Bar'), ('line', 'Line')],
        'is_am_chart': True, 'is_group': True, 'field_type_aggregates_map': NUMERIC_FIELD_TYPE_AGGREGATE_MAP,
        'is_formula_supported': True,
    },
    'grouped_list': {
        'name': 'Grouped List View', 'type': 'grouped_list', 'is_grouped_list': True, 'is_group': True,
        'total_length_needed': True, 'is_list_chart': True, 'is_formula_supported': True,
    },
}


GRANULARITY_SELECTION = [
    ('hour', 'Hour'), ('day', 'Day'), ('week', 'Week'), ('month', 'Month'), ('quarter', 'Quarter'),
    ('year', 'Year'), ('year_number', 'Year Number'), ('quarter_number', 'Quarter Number'),
    ('month_number', 'Month Number'), ('iso_week_number', 'ISO Week Number'), ('day_of_year', 'Day of Year'),
    ('day_of_month', 'Day of Month'), ('day_of_week', 'Day of Week'), ('hour_number', 'Hour Number'),
    ('minute_number', 'Minute Number'), ('second_number', 'Second Number'),
]

_ORDER_BY_SELECTION = [('ASC', 'Ascending'), ('DESC', 'Descending')]
GROUPS_LIMIT = 100

ITEM_FRONTEND_DATA_STRUCTURE = {
    'sources': [], 'errors': [], 'groupby_data_values': [], 'model_data': {}, 'formula_sources': []
}

# List of all models defined in ks_dashboard_ninja module
KS_DASHBOARD_NINJA_MODELS = [
    'ks.item.source', 'ks_dashboard_ninja.item', 'ks_dashboard_ninja.item_goal', 'ks.dashboard.csv.group.by',
    'ks.dashboard.csv.new', 'ks.dashboard.group.by', 'ks.dashboard.new', 'ks_dashboard_ninja.item_action',
    'ks_dashboard_item.multiplier', 'ks.date.filter', 'ks.item.date.fields', 'ks.model.fields', 'ks.aggregate',
    'ks.aggregate.function', 'ks.orderby', 'ks.number.format', 'ks.number.format.line', 'ks_to.do.headers',
    'ks_to.do.description', 'ks_dashboard_ninja.board', 'ks_dashboard_ninja.board_defined_filters',
    'ks_dashboard_ninja.board_custom_filters', 'ks_dashboard_ninja.favourite_filters', 'ks_dashboard_ninja.arti_int',
    'ks_dashboard_ninja.import', 'ks_ninja_dashboard.item_action', 'ks_dashboard_ninja.fetch_key',
    'ks_dashboard_ninja.board_template', 'ks_dashboard_ninja.child_board', 'ks_dashboard_ninja.grid_stack_layouts',
    'ks_dashboard_ninja.ai_dashboard', 'ks_dashboard_ninja.kpi_mail',
]

# List of specific models that need to be excluded (non-pattern based exclusions)
EXCLUDED_MODELS = [
    # base_import% models
    'base_import.mapping', 'base_import.import',
    # web_editor.% models
    'web_editor.assets',
    # web_tour.% models
    'web_tour.tour', 'web_tour.tour.step',
    # mail.thread models
    'mail.thread', 'mail.thread.phone', 'mail.thread.main.attachment', 'mail.thread.cc', 'mail.thread.blacklist',
]


class KsItemConfig(models.Model):
    _name = 'ks.item.source'
    _description = 'Dashboard Ninja Items Source Fields'
    _order = 'handle_sequence ASC, id ASC'
    
    _sequence_name = 'ks_item_source_sequence'

    name = fields.Char(required=True)
    #Sequence must be unique per item_id
    sequence = fields.Integer(string='Sequence', default=lambda self: self._get_default_sequence())
    handle_sequence = fields.Integer(string='Handle Sequence')
    
    _unique_sequence = models.Constraint('UNIQUE(sequence)', 'Sequence must be unique')
    
    type = fields.Selection(
        selection=lambda self: [(t, ITEM_TYPE_METADATA[t]['name']) for t in ITEM_TYPE_METADATA],
        default='card', required=True, help="Select the type of chart", readonly=True,
    )
    xy_type = fields.Selection(
        selection=ITEM_TYPE_METADATA['xy_chart']['available_types'], default='bar', required=True,
        help="Select the type of chart"
    )

    item_id = fields.Many2one('ks_dashboard_ninja.item')
    data_source = fields.Selection([('odoo', 'Odoo')], default='odoo', required=True)

    model_id = fields.Many2one('ir.model', string="Model Name", domain=lambda self: self._get_default_model_domain())
    model_name = fields.Char(related='model_id.model', string="Model Technical Name", store=True)

    @api.model
    def _get_default_model_domain(self):
        """
        Get domain for model_id field excluding ks_dashboard_ninja module models and other excluded models
        :return: Domain list
        """
        base_domain = [('access_ids', '!=', False), ('transient', '=', False)]
        # Exclude specific models
        exclusion_domain = [('model', '!=', model) for model in EXCLUDED_MODELS + KS_DASHBOARD_NINJA_MODELS]
        base_domain.extend(exclusion_domain)
        # Exclude models using ilike patterns
        base_domain.extend([('model', 'not ilike', 'ir.%')])

        return base_domain

    groups_limit = fields.Integer(default=GROUPS_LIMIT)

    _groups_limit_non_negative = models.Constraint(
        'CHECK(groups_limit >= 0)',
        'Record limit must be a non-negative number (0 or greater).',
    )

    # Filter Fields
    ks_domain = fields.Char()
    ks_having_domain = fields.Char() #todo: find a way to use this
    date_filter_field_ids = fields.One2many('ks.item.date.fields', 'item_source_id')
    user_filter_field_ids = fields.Many2many(
        'ir.model.fields', 'ks_user_fields_rel', domain="[('model_id','=',model_id),('relation','=','res.users'),('store', '=', True),('ttype', '=', 'many2one')]"
    )
    company_filter_field_ids = fields.Many2many(
        'ir.model.fields', 'ks_company_fields_rel', domain="[('model_id','=',model_id),('relation','=','res.company'),('store', '=', True),('ttype', '=', 'many2one')]"
    )

    # Aggregate and Measure Fields
    ks_aggregate_ids = fields.One2many('ks.aggregate', 'item_source_id')

    # Group By Fields
    ks_groupby_id = fields.Many2one('ir.model.fields', domain=lambda self: self._get_default_groupby_domain())
    groupby_date_granularity = fields.Selection(selection=GRANULARITY_SELECTION, default='month')
    groupby_field_ttype = fields.Selection(related='ks_groupby_id.ttype', store=True)

    @api.model
    def _get_default_groupby_domain(self):
        domain = f"""[
            ('model_id', '=', model_id), ('store', '=', True),
            ('ttype', 'in', {list(COMMON_FIELD_TYPE_AGGREGATE_MAP.keys())})
        ]"""

        return domain


    # Order By Fields
    ks_orderby_ids = fields.One2many('ks.orderby', 'item_source_id')

    # Display Data Fields
    is_bullets = fields.Boolean(default=True)
    is_area_chart = fields.Boolean()

    # Formula Fields
    # TODO: In list view the formula for the rows can be given like sum of row value or other operation
    formula_item_source_id = fields.Many2one('ks_dashboard_ninja.item')

    # For Future if we have to apply formula for other features
    apply_on = fields.Selection(
        selection=[('aggregate_result', 'Aggregate Result')], required=True, default='aggregate_result'
    )
    formula = fields.Text(help="Define custom formula using code defined in measures")

    # todo: for am charts there are many amchart features which can be made dynamic by adding fields for them like for color, labels, legends etc


    # Drill Down Action Fields
    drill_down_item_source_id = fields.Many2one('ks.item.source', string="Drill Down Source")
    drill_down_item_source_ids = fields.One2many('ks.item.source', 'drill_down_item_source_id', domain="[('type','=',type)]")
    list_view_id = fields.Many2one('ir.ui.view', domain="[('model','=',model_name),('type','=','list')]")
    form_view_id = fields.Many2one('ir.ui.view', domain="[('model','=',model_name),('type','=','form')]")

    # File Data Fields
    file = fields.Binary(attachment=False)
    filename = fields.Char()
    file_data = fields.Json()
    import_error_log = fields.Text(string='Import Error Log', readonly=True, help='Error logs from CSV/Excel import operations')


    def init(self):
        """Initialize the PostgreSQL sequence for unique sequence generation."""
        super().init()
        seq_name = SQL.identifier(self._sequence_name)
        # Check if sequence exists (compatible with all PostgreSQL versions)
        self.env.cr.execute(SQL(
            "SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = %s", self._sequence_name
        ))
        if not self.env.cr.fetchone():
            # Create sequence starting from 1 with minimum value 1
            self.env.cr.execute(SQL(
                "CREATE SEQUENCE %s INCREMENT BY 1 START WITH 1 MINVALUE 1",
                seq_name
            ))

    @api.model
    def _get_default_sequence(self):
        """Get default sequence value atomically using PostgreSQL sequence.
        This ensures uniqueness even in batch creation scenarios.
        Each call to nextval() atomically increments and returns the next value.
        Minimum value is 1.
        """
        # nextval() expects the sequence name as a string literal, not an identifier
        self.env.cr.execute(SQL("SELECT nextval(%s)", self._sequence_name))
        result = self.env.cr.fetchone()
        sequence_value = result[0] if result and result[0] is not None else 1
        
        return sequence_value

    @api.onchange('model_id', 'type')
    def _onchange_model_id(self):
        self.reset_sources()

    @api.model_create_multi
    def create(self, vals):
        records = super().create(vals)
        group_result = self.formatted_read_group(
            [('item_id', 'in', records.mapped('item_id.id'))], ['item_id'], ['id:count']
        )

        for group_data in group_result:
            if group_data.get('id:count') > 10:
                raise ValidationError(_('Maximum 10 item sources are allowed per dashboard item.'))
        return records

    def reset_sources(self):
        """Reset all source configuration fields when model_id changes.
        This ensures that when a model is changed, all related configurations
        (aggregates, groupby, orderby, domain, filters, drill down, views) are reset.
        """
        reset_values = {
            'ks_aggregate_ids': [(5, 0, 0)], 'ks_groupby_id': False,
            'ks_orderby_ids': [(5, 0, 0)], 'ks_domain': False, 'user_filter_field_ids': [(5, 0, 0)],
            'company_filter_field_ids': [(5, 0, 0)], 'date_filter_field_ids': [(5, 0, 0)],
            'drill_down_item_source_id': False, 'drill_down_item_source_ids': [(5, 0, 0)],
            'list_view_id': False, 'form_view_id': False,
        }
        for record in self:
            record.update(reset_values)

    def prepare_domain(self, options: dict = {}) -> dict:
        self.ensure_one()
        domain = Domain(options['domain']) if options.get('domain') else Domain.TRUE

        if self.ks_domain:
            domain &= Domain(ast.literal_eval(self.ks_domain))

        user_id = self.env.user.id
        for field_id in self.user_filter_field_ids:
            domain &= Domain(field_id.name, '=', user_id)

        company_ids = self.env.context.get('allowed_company_ids', [])
        for field_id in self.company_filter_field_ids:
            domain &= Domain(field_id.name, 'in', company_ids)

        date_domain_data = self.date_filter_field_ids.prepare_date_domain()
        domain &= date_domain_data.get('domain', Domain.TRUE)

        drill_down_data = options.get('drill_down_data')
        if drill_down_data and self.drill_down_item_source_id:
            current_sources_data = drill_down_data.get('current_sources_data', {})
            data = current_sources_data.get(f'{self.sequence}', {})
            domain &= Domain(data.get('domain', []))

        return {'domain': list(domain)}

    def prepare_having(self, options: dict = {}) -> dict:
        self.ensure_one()
        # having = Domain(kwargs['having']) if kwargs.get('having') else []
        # having &= Domain(ast.literal_eval(self.ks_having_domain if self.ks_having_domain else '[]'))

        return {'having': []}

    def prepare_aggregates(self, options: dict = {}) -> dict:
        if not self.ks_aggregate_ids:
            return {'error_data': {'msg': 'Please add measures'}}

        aggregates = self.ks_aggregate_ids.prepare_aggregates()
        return aggregates

    def prepare_groupby(self, options: dict = None) -> dict:
        options = options or {}
        meta_data = ITEM_TYPE_METADATA[self.type]
        is_group = meta_data.get('is_group')

        if not is_group:
            return {'groupby': []}

        groupby = []
        groupby_id = self.ks_groupby_id
        if groupby_id and groupby_id.ttype in ['date', 'datetime'] and self.groupby_date_granularity:
            groupby.append(f'{groupby_id.name}:{self.groupby_date_granularity}')
        elif groupby_id and groupby_id.ttype not in ['date', 'datetime']:
            groupby.append(f'{groupby_id.name}')
        else:
            return {'error_data': {'msg': 'Please select Group By Details'}}

        return {'groupby': groupby}

    def prepare_orderby(self, options: dict = {}) -> dict:
        orderby = self.ks_orderby_ids.prepare_orderby()
        return orderby

    def prepare_limit(self, options: dict = {}) -> dict:
        metadata = ITEM_TYPE_METADATA[self.type]
        groups_limit = self.groups_limit if self.groups_limit > 0 else None
        offset = options.get('offset', 0)
        pagination = options.get('pagination')
        
        # Calculate remaining records after offset
        remaining_records = max(0, groups_limit - offset) if groups_limit is not None else None
        
        # Early return if no records available
        if remaining_records == 0:
            return {'limit': 0}
                
        if metadata.get('is_list_chart') and remaining_records is not None and pagination is not None:
            limit = min(remaining_records, pagination)
        else:
            limit = remaining_records or pagination
                
        return {'limit': limit, 'groups_limit': groups_limit}

    def prepare_read_group_params(self, options: dict = {}) -> dict:
        domain = self.prepare_domain(options)
        having = self.prepare_having(options)
        aggregates = self.prepare_aggregates(options)
        groupby = self.prepare_groupby(options)
        orderby = self.prepare_orderby(options)
        limit = self.prepare_limit(options)


        params = {}
        for param in [groupby, aggregates, domain, having, orderby, limit]:
            params.update(param)
            if params.get('error_data'):
                break

        return params

    def validate_odoo_config(self):
        '''
        Method to validate fields on self
        :return:
        '''
        self.ensure_one()
        result = {}

        if not self.model_id:
            return {'error_data': {'msg': 'Please choose model name'}}

        return result

    # TODO: many2many should be added as a group - there are orm methods for it
    def odoo_orm(self, options: dict) -> dict:
        groupby: list[str] = options['groupby']
        aggregates: list[str] = options['aggregates']
        model: str = options['model']
        domain = options.get('domain', [])
        having = options.get('having', [])
        orderby = options.get('orderby')
        limit = options.get('limit')
        groups_limit = options.get('groups_limit')
        offset = options.get('offset', 0)
        metadata = ITEM_TYPE_METADATA[self.type]

        if limit == 0:
            return {'error_data': {'msg': "Empty Records"}}

        try:
            group_data = {
                'group_records': self.env[model].formatted_read_group(
                    Domain(domain), groupby, aggregates, having, offset, limit, orderby
                ),
            }
            groups = group_data['group_records']
            if not groups:
                group_data = {'error_data': {'msg': "Empty Records"}}
            elif metadata.get('total_length_needed'):
                if limit and len(groups) == limit:
                    total_length = limit + len(self.env[model]._read_group(domain, groupby=groupby, offset=limit))
                else:
                    total_length = len(groups) + offset

                group_data['total_length'] = groups_limit if groups_limit and groups_limit <= total_length\
                    else total_length
        except Exception as e:
            group_data = {'error_data': {'msg': "Technical Error: " + str(e)}}

        return group_data

    def prepare_odoo_source_data(self, options: dict = {}) -> dict:
        """
        Source Data  is the source of  truth for all field values required for orm methods
        Do not consider fields for the source of truth
        :param options:
        :return:
        """
        self.ensure_one()
        validation_result = self.validate_odoo_config()

        if validation_result.get('error_data'):
            return validation_result

        read_group_params = self.prepare_read_group_params(options)

        if read_group_params.get('error_data'):
            return read_group_params

        read_group_params['model'] = self.model_id.model
        read_group_params.update(options)

        source_data = self.odoo_orm(read_group_params)

        if source_data.get('error_data'):
            return source_data

        groupby: list[str] = read_group_params['groupby']
        aggregates: list[str] = read_group_params['aggregates']

        field_names = [split_field_name(value) for value in groupby + aggregates]
        attributes = ['type', 'selection']
        source_data.update(read_group_params)

        source_data.update({
            'aggregates_data': read_group_params.get('aggregates_data', {}),
            'groupby_name': groupby[0] if len(groupby) else False,
            'fields_data': self.env[read_group_params['model']].fields_get(field_names, attributes),
            'sequence': self.sequence,
        })

        return source_data

    def prepare_model_data(self) -> dict:
        # TODO: move usage of sequence to model_data
        fields = [
            'id', 'xy_type', 'is_bullets', 'is_area_chart', 'model_name', 'drill_down_item_source_id', 'sequence'
        ]
        data = self.read(fields, load=None)
        data = data[0]
        replace_new_id(data)

        return data

    def prepare_drill_down_model_data(self) -> dict:
        fields = ['id', 'sequence']
        records = self.read(fields, load=None)

        for record_data in records:
            replace_new_id(record_data)

        return records

    def format_source_data(self, source_data) -> dict:
        self.ensure_one()
        metadata = ITEM_TYPE_METADATA[self.type]

        if source_data.get('error_data'):
            return source_data

        source_data.update({'env': self.env, 'sequenced_aggregates': []})

        if metadata.get('is_am_chart'):
            formatted_source_data = am_format_read_group_data(source_data)
        elif metadata.get('is_grouped_list'):
            formatted_source_data = list_format_read_group_data(source_data)
        elif metadata.get('card_format'):
            formatted_source_data = card_format_read_group_data(source_data)
        else:
            formatted_source_data = {'error_data': {'msg': "Technical Error: Unsupported Item Type"}}

        if formatted_source_data.get('error_data'):
            return formatted_source_data

        formatted_source_data['parent_drill_down_source_sequence'] = self.drill_down_item_source_id.sequence \
            if self.drill_down_item_source_id else self.sequence
        formatted_source_data['sequenced_aggregates'] = source_data.get('sequenced_aggregates', [])
        formatted_source_data['domain'] = source_data.get('domain', [])

        if metadata.get('total_length_needed'):
            formatted_source_data['total_length'] = source_data.get('total_length', 0)

        return formatted_source_data

    def prepare_frontend_data(self, **kwargs) -> dict:
        source_data = {}
        if self.data_source == 'odoo':
            source_data = self.prepare_odoo_source_data(options=kwargs)

        return {
            'source_data': source_data,
            **self.format_source_data(source_data),
            'model_data': self.prepare_model_data()
        }

    def parse_file(self, nrows=None) -> dict:
        """
        Reads the uploaded file and returns a pandas DataFrame.
        Adding Try catch bcz file can be corrupted
        :return:
        """
        try:
            file = io.BytesIO(base64.b64decode(self.file or b''))
            if self.filename.endswith('.xls'):
                df = pd.read_excel(file, engine='xlrd', nrows=nrows)
            elif self.filename.endswith('.xlsx'):
                df = pd.read_excel(file, engine='openpyxl', nrows=nrows)
            else:
                df = pd.read_csv(file, nrows=nrows)
            return {'df': df}
        except Exception:
            return {'error_data': {'msg': "File format not supported or file is corrupted"}}

    def _sync_model(self) -> dict:
        try:
            random_suffix = binascii.hexlify(os.urandom(4)).decode()
            columns_data = self.file_data.get('columns_data', {}) if self.file_data else {}
            field_vals = [
                (0, 0, {
                    'name': column_data['name'], 'ttype': column_data.get('ttype', 'char'), 'state': 'manual',
                    'field_description': column_data.get('field_description', 'Description'),
                }) for column_data in columns_data.values()
            ]
            access_vals = [
                (0, 0, {
                    'name': f"X-Model-{random_suffix}_all_user", 'group_id': self.env.ref('base.group_user').id,
                    'perm_read': True, 'perm_write': True, 'perm_create': True, 'perm_unlink': True,
                })
            ]
            vals = {
                'name': f"X-Model-{random_suffix}", 'model': f"x_model_{random_suffix}", 'state': 'manual',
                'field_id': [(5, 0, 0), *field_vals], 'access_ids': [(5, 0, 0), *access_vals]
            }

            return {'model_id': self.env['ir.model'].sudo().create(vals)}
        except Exception as e:
            return {'error_data': {'msg': _(str(e))}}

    def action_sync_columns(self):
        self.ensure_one()
        # Clear previous error log
        self.write({'import_error_log': False})
        
        result = self.parse_file(nrows=10)

        if result.get('error_data'):
            error_msg = result['error_data'].get('msg', 'Unknown error')
            self.write({'import_error_log': f"Error during column sync: {error_msg}"})
            return

        file_data = self.file_data or {}
        df = result['df']
        columns = df.columns.tolist()
        columns_data = file_data.get('columns_data', {})
        updated_columns_data = {}

        for i in range(0, len(columns)):
            data = columns_data.get(i, {})
            data['ttype'] = data.get('type', 'char') if columns[i] == data.get('name') else 'char'
            data['field_description'] = str(columns[i][:64]).replace('_', ' ').capitalize()
            data['name'] = f'x_{columns[i].lower().replace(' ', '_')[:64]}'
            updated_columns_data[i] = data

        file_data['columns_data'] = updated_columns_data

        self.update({'file_data': file_data})

    def action_sync_model(self):
        self.ensure_one()
        # Clear previous error log
        self.write({'import_error_log': False})

        fields = [
            value['name'] for value in self.file_data.get('columns_data', {}).values()
        ] if self.file_data and self.file_data.get('columns_data') else []

        if not fields:
            self.write({'import_error_log': 'No columns found to import'})
            return

        model_data = self._sync_model()
        if model_data.get('error_data'):
            error_msg = model_data['error_data'].get('msg', 'Unknown error during model sync')
            self.write({'import_error_log': f"Model Sync Error: {error_msg}"})
            return

        model_id = model_data['model_id']
        try:
            columns = [value['field_description'] for value in self.file_data['columns_data'].values()]

            # Basic required options for execute_import (works for CSV, Excel, ODS)
            options = {
                'has_headers': True,  # Assume file has headers
                'separator': ',',  # Default CSV separator (auto-detected if wrong)
                'quoting': '"',  # Text delimiter for CSV
                'skip': 0,  # Skip rows from start
                'tracking_disable': True,  # Disable mail tracking during import
            }

            load_result = self.env['base_import.import'].create({
                'res_model': model_id.model, 'file': base64.b64decode(self.file or b''), 'file_name': self.filename,
            }).execute_import(
                columns=columns, fields=fields, options=options
            )
            
            # Check for error messages in load_result
            for msg in load_result.get('messages', []):
                if msg.get('type') == 'error':
                    self.write({'import_error_log': _(msg.get('message', ''))})
                    return
        except Exception as e:
            error_msg = f"Exception during import: {str(e)}"
            self.write({'import_error_log': error_msg})
            return

        # Clear error log on success
        self.write({'import_error_log': False})
        self.reset_sources()
        self.write({
            'file_data': {**self.file_data, 'model_name': model_id.name, 'model': model_id.model},
            'model_id': model_id.id,
        })


    def action_open_item_source(self):
        return {
            'name': _("Item Source"),
            'res_model': 'ks.item.source',
            'view_mode': 'form',
            'view_type': 'form',
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'context': {
                'form_view_ref': 'ks_dashboard_ninja.view_ks_item_source_main_form',
                'default_type': self.env.context.get('default_type', self.item_id.type),
                'default_item_id': self.env.context.get('default_item_id', self.item_id.id),
                "dialog_size": "extra-large"
            },
            'target': 'new'
        }
