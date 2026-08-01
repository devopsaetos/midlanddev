# -*- coding: utf-8 -*-

from odoo.addons.ks_dashboard_ninja.common_lib.ks_utils import get_aggregate, get_orderby
from odoo.addons.ks_dashboard_ninja.models.ks_item_source import _ORDER_BY_SELECTION, ITEM_TYPE_METADATA, \
    COMMON_FIELD_TYPE_AGGREGATE_MAP, BASIC_AGGREGATE_FUNCTIONS

from odoo import models, fields, api

_OPERATION_FIELD_TYPES = ['int', 'float', 'monetary']

class KsModelFields(models.Model):
    _name = 'ks.model.fields'
    _description = 'Common Model for Model and Fields Selection'
    _rec_name = 'field_description'

    field_description = fields.Char(required=True)
    item_source_id = fields.Many2one('ks.item.source')
    aggregate_function_id = fields.Many2one('ks.aggregate.function', required=True, ondelete='cascade')

    # todo later: check for cascade if we can delete date filters, check if need to make required from form view
    field_id = fields.Many2one('ir.model.fields', required=True, ondelete='cascade')

    field_domain = fields.Json(compute="_compute_field_domains")
    aggregate_function_domain = fields.Json(compute="_compute_field_domains")

    def reset_records(self):
        for rec in self:
            rec.field_description = rec.field_id.field_description if rec.field_id else ''
            rec.aggregate_function_id = False

    @api.depends('field_id')
    def _compute_field_domains(self):
        for record in self:
            if record.item_source_id and record.item_source_id.model_id:
                record.field_domain = [
                    ('model_id', '=', record.item_source_id.model_id.id), ('name', 'not in', ['sequence']),
                    ('store', '=', True), ('ttype', 'in', list(COMMON_FIELD_TYPE_AGGREGATE_MAP.keys()))
                ]
            else:
                record.field_domain = [(0, "=", 1)]  # Always false domain

            # Domain for aggregate function selection based on field type
            if record.item_source_id and record.item_source_id.type and record.field_id and record.field_id.ttype:
                metadata = ITEM_TYPE_METADATA[record.item_source_id.type]
                aggregate_map = metadata.get('field_type_aggregates_map', COMMON_FIELD_TYPE_AGGREGATE_MAP)
                record.aggregate_function_domain = [
                    ('sql_name', 'in', aggregate_map.get(record.field_id.ttype, BASIC_AGGREGATE_FUNCTIONS))
                ]
            else:
                record.aggregate_function_domain = [(0, "=", 1)]


class KsAggregate(models.Model):
    _name = 'ks.aggregate'
    _inherit = ['ks.model.fields']
    _description = 'Aggregate for Dashboard Items Configuration'
    _rec_name = 'field_description'

    code = fields.Char(size=15)
    operation = fields.Selection(
        selection=[
            ('none', 'None'), ('addition', 'Addition'), ('subtraction', 'Subtraction'),
            ('multiplication', 'Multiplication'), ('division', 'Division'), ('rounding', 'Rounding'),
        ],
        default='none', required=True, help="Operation to apply to the aggregate value"
    )
    operation_value = fields.Float(default=1.0, help="Value for operation to apply on aggregate value")
    operation_readonly_domain = fields.Json(compute="_compute_field_domains")
    show_currency = fields.Boolean()

    @api.depends('field_id')
    def _compute_field_domains(self):
        super(KsAggregate, self)._compute_field_domains()
        for record in self:
            if record.item_source_id and record.field_id and record.field_id.ttype in _OPERATION_FIELD_TYPES:
                record.operation_readonly_domain = False
            else:
                record.operation_readonly_domain = [(1, "=", 1)]

    def reset_records(self):
        super().reset_records()
        for rec in self:
            rec.show_currency = True if rec.field_id.ttype == 'monetary' else False

            if rec.item_source_id and rec.field_id and rec.field_id.ttype not in _OPERATION_FIELD_TYPES:
                rec.operation = 'none'
                rec.operation_value = 1

    @api.onchange('field_id')
    def _onchange_field_id(self):
        self.reset_records()

    def prepare_aggregates(self) -> dict:
        aggregates_data = {}

        for record in self.filtered(lambda r: r.field_id and r.aggregate_function_id):
            aggregate = get_aggregate(record.field_id.name, record.aggregate_function_id.sql_name)
            aggregates_data[aggregate] = {
                'field_description': record.field_description,
                'operation': record.operation if record.field_id.ttype in _OPERATION_FIELD_TYPES else 'none',
                'operation_value': record.operation_value,
                'code': record.code,
                'show_currency': record.show_currency,
            }

        return {
            'aggregates_data': aggregates_data,
            'aggregates': list(aggregates_data.keys()),
        }


class KsAggregateFunctions(models.Model):
    _name = 'ks.aggregate.function'
    _description = 'Aggregate Functions'

    name = fields.Char()
    sql_name = fields.Char()

class KsOrderBy(models.Model):
    _name = 'ks.orderby'
    _inherit = ['ks.model.fields']
    _description = 'Order By for Dashboard Items'
    _rec_name = 'field_id'

    ks_orderby_order = fields.Selection(selection=_ORDER_BY_SELECTION, default='ASC', required=True)
    is_groupby_field = fields.Boolean()

    def reset_records(self):
        super().reset_records()
        for rec in self:
            rec.is_groupby_field = False

    @api.onchange('field_id')
    def _onchange_field_id(self):
        self.reset_records()

    def prepare_orderby(self) -> dict:
        orderby = []

        for record in self.filtered(lambda r: r.field_id and r.aggregate_function_id):
            if record.is_groupby_field and record.item_source_id.ks_groupby_id == record.field_id:
                orderby.append(get_orderby(record.field_id.name, record.ks_orderby_order))
            else:
                aggregate = get_aggregate(record.field_id.name, record.aggregate_function_id.sql_name)
                orderby.append(get_orderby(aggregate, record.ks_orderby_order))

        return {
            'orderby': ", ".join(list(dict.fromkeys(orderby)))
        }

