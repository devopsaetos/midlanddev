# -*- coding: utf-8 -*-


from datetime import datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.misc import get_lang

from odoo import models, fields, api, _


class KsDateFilter(models.Model):
    _name = "ks.date.filter"
    _description = "Customized datetime filters"
    _order = "sequence ASC, id DESC"

    name = fields.Char(string="Name", required=True)
    start_at = fields.Integer(string="Start At")
    end_at = fields.Integer(string="End At")
    sequence = fields.Integer(string="Sequence")
    datetime_start = fields.Datetime(string="Time Start", required=True, default=datetime.now())
    datetime_end = fields.Datetime(string="Time End", required=True, default=datetime.now())
    time_period = fields.Selection(
        string="Time Period", required = True, default='day',
        selection=[('day', 'Day'), ('week', 'Week'), ('month', 'Month'), ('year', 'Year'), ('half-year', 'Half-Year'),
                   ('quarter', 'Quarter')]
    )
    calc_type = fields.Selection([
        ('boundary', 'Boundary-based'), ('relative', 'From Now'), ('custom', 'Fixed Range')
    ], required=True, default='boundary')

    _start_at_range_constraint = models.Constraint(
        'CHECK(start_at IS NULL OR (start_at >= -400 AND start_at <= 400))',
        'Start At value must be between -400 and 400.',
    )

    _end_at_range_constraint = models.Constraint(
        'CHECK(end_at IS NULL OR (end_at >= -400 AND end_at <= 400))',
        'End At value must be between -400 and 400.',
    )

    _start_end_order_constraint = models.Constraint(
        'check(start_at IS NULL OR end_at IS NULL OR start_at <= end_at)',
        'Start At value cannot be greater than End At value.',
    )


    @api.model
    def _to_utc(self, dt):
        """Convert aware datetime to naive UTC (for Odoo storage)."""
        return dt.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _safe_add_delta(self, base_dt, delta, raise_error=False):
        """Safely add timedelta or relativedelta to datetime with error handling."""
        # datetime arithmetic can raise OverflowError/ValueError for extreme/invalid dates, must use try-catch
        try:
            return base_dt + delta
        except (OverflowError, ValueError) as e:
            if raise_error:
                raise ValidationError(_("Date calculation failed: %s") % str(e))
            return datetime.now(pytz.utc)

    def _shift_datetime(self, base_dt, offset, tp, raise_error=False):
        """Shift a datetime based on the time period."""
        if tp == 'day':
            result = self._safe_add_delta(base_dt, timedelta(days=offset), raise_error)
        elif tp == 'week':
            result = self._safe_add_delta(base_dt, timedelta(weeks=offset), raise_error)
        elif tp == 'month':
            result = self._safe_add_delta(base_dt, relativedelta(months=offset), raise_error)
        elif tp == 'quarter':
            result = self._safe_add_delta(base_dt, relativedelta(months=offset * 3), raise_error)
        elif tp == 'half-year':
            result = self._safe_add_delta(base_dt, relativedelta(months=offset * 6), raise_error)
        elif tp == 'year':
            result = self._safe_add_delta(base_dt, relativedelta(years=offset), raise_error)
        else:
            result = base_dt

        return result

    def _get_boundary_start(self, ref_date, tp):
        """Get start of current period (day, week, month, etc.)."""
        lang = get_lang(self.env)
        week_start = (int(lang.week_start) - 1) % 7

        if tp == 'week':
            return ref_date - timedelta(days=(ref_date.weekday() - week_start) % 7)
        elif tp == 'month':
            return ref_date.replace(day=1)
        elif tp == 'quarter':
            q_month = ((ref_date.month - 1) // 3) * 3 + 1
            return ref_date.replace(month=q_month, day=1)
        elif tp == 'half-year':
            h_month = 1 if ref_date.month <= 6 else 7
            return ref_date.replace(month=h_month, day=1)
        elif tp == 'year':
            return ref_date.replace(month=1, day=1)
        return ref_date  # day

    def _get_boundary_end(self, start_dt, tp):
        """Get end of current period aligned with start."""        
        if tp == 'week':
            end = self._safe_add_delta(start_dt, timedelta(days=6))
        elif tp == 'month':
            end = self._safe_add_delta(start_dt, relativedelta(months=1, days=-1))
        elif tp == 'quarter':
            end = self._safe_add_delta(start_dt, relativedelta(months=3, days=-1))
        elif tp == 'half-year':
            end = self._safe_add_delta(start_dt, relativedelta(months=6, days=-1))
        elif tp == 'year':
            # Use relativedelta to safely get last day of year
            end = self._safe_add_delta(start_dt.replace(month=1, day=1), relativedelta(years=1, days=-1))
        else:  # day
            end = start_dt
        return end.replace(hour=23, minute=59, second=59, microsecond=999999)

    def calc_datetime(self, raise_error=False):
        """Compute date range for this record."""
        self.ensure_one()

        tp = self.time_period
        start_at, end_at = self.start_at, self.end_at
        calc_type = self.calc_type

        # Custom range → user defined
        if calc_type == 'custom':
            return self.datetime_start, self.datetime_end

        # Base datetime references
        timezone = pytz.timezone(self.env.context.get('tz') or 'UTC')
        now = datetime.now().astimezone(timezone)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Compute base start/end according to type
        if calc_type == 'relative':
            start = self._shift_datetime(now, start_at, tp, raise_error)
            end = self._shift_datetime(now, end_at, tp, raise_error)
        else:  # boundary
            base_start = self._get_boundary_start(today, tp)
            base_end = self._get_boundary_end(base_start, tp)
            start = self._shift_datetime(base_start, start_at, tp, raise_error)
            end = self._shift_datetime(base_end, end_at, tp, raise_error)


        # Ensure order and UTC conversion
        if start > end:
            start, end = end, start

        return self._to_utc(start), self._to_utc(end)

    def action_calc_datetime(self):
        """Calculate and update datetime fields. Raises ValidationError on failure."""
        start_datetime, end_datetime = self.calc_datetime(raise_error=True)
        self.write({'datetime_start': start_datetime, 'datetime_end': end_datetime})


class KsDateField(models.Model):
    _name = 'ks.item.date.fields'
    _description = 'Date Filter for Dashboard Items Configuration'

    name = fields.Char(default='Date Filter')
    item_source_id = fields.Many2one('ks.item.source')
    date_filter_id = fields.Many2one('ks.date.filter', required=True, ondelete='cascade')
    date_field_id = fields.Many2one(
        'ir.model.fields', 'ks_date_field_rel', required=True, ondelete="cascade",
        domain="[('model_id','=',model_id),('ttype','in',['date','datetime']),('store', '=', True)]"
    )
    model_id = fields.Many2one('ir.model', related='item_source_id.model_id')

    def prepare_date_domain(self):
        domain = Domain.TRUE
        for record in self.filtered(lambda r: r.date_filter_id and r.date_field_id):
            start_datetime, end_datetime = record.date_filter_id.calc_datetime()
            domain &= Domain(record.date_field_id.name, '>=', start_datetime)
            domain &= Domain(record.date_field_id.name, '<', end_datetime)

        return {'domain': domain}
