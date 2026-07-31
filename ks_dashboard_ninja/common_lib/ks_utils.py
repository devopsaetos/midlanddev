import json
from datetime import date, datetime

from odoo.api import NewId
from odoo.tools import float_repr
from odoo.tools.misc import format_date, format_datetime
from odoo.tools.safe_eval import safe_eval

DEFAULT_PRECISION_DIGITS = 2
DEFAULT_PAGINATION = 15
MIN_INTEGRAL_DIGITS = 3
# todo: later: make the data like source_data more robust by making the defined structure for frontend data

def map_selection_value(selections: list, value: str) -> str:
    """
    Map a selection field's technical value to its display label.

    Args:
        selections (dict): Dict of model field -> selection list,
                                 e.g. {[('draft', 'Draft'), ('done', 'Done')]}
        value (str): Technical value, e.g. 'done'

    Returns:
        str: Human-readable label if found, otherwise the original value.
    """
    return next((label for val, label in selections if val == value), value)

def apply_operation(value, operation, operation_value):
    """
    Apply an operation to a numeric value.

    Args:
        value: The numeric value to apply operation on
        operation: The operation type ('none', 'addition', 'subtraction', 'multiplication', 'division', 'rounding')
        operation_value: The value to use in the operation

    Returns:
        The result of applying the operation, or original value if not numeric or operation is 'none'
    """
    if operation == 'none':
        return value
    
    if operation == 'addition':
        return value + operation_value
    elif operation == 'subtraction':
        return value - operation_value
    elif operation == 'multiplication':
        return value * operation_value
    elif operation == 'division':
        return value / operation_value if operation_value != 0 else value
    elif operation == 'rounding':
        return round(value, int(operation_value)) if operation_value >= 0 else round(value)
    
    return value

def get_allowed_pagination(pagination):
    return pagination if pagination > 0 else DEFAULT_PAGINATION

def get_allowed_integral_digits(integral_digits):
    return integral_digits if 1 <= integral_digits <= 5 else MIN_INTEGRAL_DIGITS

def get_allowed_precision(precision_digits):
    return precision_digits if 0 <= precision_digits <= 10 else DEFAULT_PRECISION_DIGITS

def ks_format_value(key, value, source_data) -> str:
    if type(value) in (int, float):
        value = abs(value)

    if isinstance(value, tuple):
        return value[1]
    elif type(value) is datetime:
        return format_datetime(source_data['env'], value)
    elif type(value) is date:
        return format_date(source_data['env'], value)
    elif key in source_data.get('aggregates_data', {}) and type(value) in (int, float) and source_data.get(
        'number_formatting_data'):
        precision_digits = source_data['number_formatting_data'].get('precision_digits', DEFAULT_PRECISION_DIGITS)
        return float_repr(value, precision_digits)
    else:
        return str(value)

def format_raw_value(value):
    if isinstance(value, (tuple, list)):
        return value[0]
    else:
        return value

def format_key_value(key, value, source_data):
    fields_data = source_data.get('fields_data', {})
    aggregates_data = source_data.get('aggregates_data', {})
    field_name = split_field_name(key)

    if field_name in fields_data and fields_data[field_name].get('selection'):
        return field_name, map_selection_value(fields_data[field_name]['selection'], value)
    elif key in aggregates_data and aggregates_data[key].get('operation') != 'none':
        operated_value = apply_operation(
            value, aggregates_data[key]['operation'], aggregates_data[key].get('operation_value', 1)
        )
        return field_name, ks_format_value(key, operated_value, source_data)
    else:
        return field_name, ks_format_value(key, value, source_data)


def ks_format_record_data(record_data, source_data):
    raw_source_record_data = {}
    formatted_source_record_data = {}
    formula_ctx = {}
    aggregates_data = source_data.get('aggregates_data', {})

    for key, value in record_data.items():
        new_key, new_value = format_key_value(key, value, source_data)
        sequenced_aggregate = f'{source_data['sequence']}.{key}'

        if key in aggregates_data and aggregates_data[key].get('code'):
            formula_ctx[aggregates_data[key].get('code')] = value

        if key == '__extra_domain':
            formatted_source_record_data[sequenced_aggregate] = raw_source_record_data[key] = value
        elif key == source_data.get('groupby_name'):
            formatted_source_record_data['__groupby_value'] = new_value
            raw_source_record_data[key] = value
        elif isinstance(value, (datetime, date)):
            formatted_source_record_data[sequenced_aggregate] = raw_source_record_data[key] = record_data[key] = new_value
        else:
            formatted_source_record_data[sequenced_aggregate] = new_value
            raw_source_record_data[key] = value

    raw_source_record_data['__formula_ctx'] = formula_ctx

    return formatted_source_record_data, raw_source_record_data

def add_sequenced_aggregates(source_data):
    sequenced_aggregates = source_data['sequenced_aggregates']
    aggregates_data = source_data.get('aggregates_data', {})
    [sequenced_aggregates.append(f'{source_data['sequence']}.{aggregate}') for aggregate in aggregates_data.keys()]


def am_format_read_group_data(source_data) -> dict:
    # format record based on series formation at frontend library

    formatted_groupby_record_mapped_data = source_data['formatted_groupby_record_mapped_data']
    mapped_groupby_formula_ctx = source_data['mapped_groupby_formula_ctx']
    formatted_data = {
        'groupby_values': [], 'raw_source_records': [], 'aggregates_data': source_data.get('aggregates_data', {}),
        'groupby_name': source_data['groupby_name']
    }
    add_sequenced_aggregates(source_data)

    for i, record_data in enumerate(source_data.get('group_records', [])):
        formatted_source_record_data, raw_source_record_data = ks_format_record_data(record_data, source_data)
        index_key = f'{source_data['sequence']}.__index'
        formatted_source_record_data[index_key] = raw_source_record_data['__index'] = i
        groupby_value = formatted_source_record_data['__groupby_value']

        mapped_groupby_formula_ctx[groupby_value].update(raw_source_record_data.pop('__formula_ctx'))

        formatted_data['raw_source_records'].append(raw_source_record_data)
        formatted_groupby_record_mapped_data[groupby_value].update(formatted_source_record_data)

        formatted_data['groupby_values'].append(groupby_value)

    formatted_data['mapped_groupby_formula_ctx'] = mapped_groupby_formula_ctx

    return formatted_data


def list_format_read_group_data(source_data) -> dict:
    # format record based on row and column parsing at frontend

    mapped_groupby_formula_ctx = source_data['mapped_groupby_formula_ctx']
    formatted_data = {
        'groupby_values': [], 'fields_data': source_data['fields_data'], 'raw_source_records': [],
        'groupby_name': source_data['groupby_name'], 'aggregates_data': source_data.get('aggregates_data', {})
    }
    add_sequenced_aggregates(source_data)

    formatted_groupby_record_mapped_data = source_data['formatted_groupby_record_mapped_data']

    for i, record_data in enumerate(source_data.get('group_records', [])):
        formatted_source_record_data, raw_source_record_data = ks_format_record_data(record_data, source_data)
        index_key = f'{source_data['sequence']}.__index'
        formatted_source_record_data[index_key] = raw_source_record_data['__index'] = i
        groupby_value = formatted_source_record_data['__groupby_value']

        mapped_groupby_formula_ctx[groupby_value].update(raw_source_record_data.pop('__formula_ctx'))
        formatted_groupby_record_mapped_data[groupby_value].update(formatted_source_record_data)
        formatted_data['raw_source_records'].append(raw_source_record_data)
        formatted_data['groupby_values'].append(groupby_value)

    formatted_data['mapped_groupby_formula_ctx'] = mapped_groupby_formula_ctx

    return formatted_data

def card_format_read_group_data(source_data) -> dict:
    aggregates_data = source_data.get('aggregates_data', {})

    mapped_groupby_formula_ctx = source_data['mapped_groupby_formula_ctx']
    formatted_groupby_record_mapped_data = source_data['formatted_groupby_record_mapped_data']
    formatted_data = {
        'fields_data': source_data['fields_data'], 'aggregates_data': aggregates_data, 'formula_ctx': {},
        'groupby_values': ['__all']
    }
    add_sequenced_aggregates(source_data)

    record = source_data.get('group_records', [])

    # Card Item Type works for single record only
    record = record[0]

    formatted_source_record_data, raw_source_record_data = ks_format_record_data(record, source_data)
    mapped_groupby_formula_ctx['__all'].update(raw_source_record_data.pop('__formula_ctx'))
    formatted_groupby_record_mapped_data['__all'].update(formatted_source_record_data)
    formatted_data['mapped_groupby_formula_ctx'] = mapped_groupby_formula_ctx

    return formatted_data

def split_field_name(aggregate):
    return aggregate.split(":")[0]

def get_orderby(field_name:str, order:str, options:dict=None):
    return f'{field_name} {order}'

def get_aggregate(field_name:str, aggregate:str, options:dict=None):
    return f'{field_name}:{aggregate}'

def replace_new_id(obj):
    if isinstance(obj.get('id', False), NewId):
        obj['id'] = obj['id'].origin

def replace_company_domain(domain, company_id, company_ids):
    domain = safe_eval(domain) if isinstance(domain, str) else domain
    new_domain = []
    for condition in domain:
        if isinstance(condition, tuple) and len(condition) >= 3:
            if condition[1] in ('in', 'not in') and isinstance(condition[2], list) and '%MYCOMPANY' in condition[2]:
                new_condition = (condition[0], condition[1], [y for x in condition[2] for y in (company_ids if x == '%MYCOMPANY' else [x])])
            elif condition[2] == '%MYCOMPANY':
                new_condition = (condition[0], condition[1], company_id)
            else:
                new_condition = condition
            new_domain.append(new_condition)
        else:
            new_domain.append(condition)
    return json.dumps(new_domain)

def clean_dict_in_place(data):
    """Removes non-serializable keys from a dictionary in place."""
    for key in list(data.keys()):
        try:
            json.dumps(data[key])
        except (TypeError, OverflowError):
            del data[key]