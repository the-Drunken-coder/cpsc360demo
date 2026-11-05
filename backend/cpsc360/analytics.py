import math
from collections import defaultdict
from datetime import timedelta

from . import models as m
from .derive import HAZARD_LABELS
from .search import JOIN, filters_sql

CAVEAT = 'Counts of public reports by report date, not incident rates. No exposure or sales data exists. Reporting volume depends on awareness and publicity. The most recent approximately 30 days are incomplete because publication lags submission.'


def grouping(dimension):
    if dimension == 'hazard':
        return 'h.hazard', ' JOIN inference.incident_hazard h USING (report_no) '
    return ('n.' if dimension == 'manufacturer_key' else 'i.') + dimension, ''


def label(conn, dimension, key):
    if key == '__unknown__':
        return 'Not reported'
    if dimension == 'hazard':
        return HAZARD_LABELS.get(key, key)
    if dimension == 'manufacturer_key':
        row = conn.execute('SELECT display_name FROM inference.manufacturer WHERE manufacturer_key=%s', (key,)).fetchone()
        return row['display_name'] if row else key
    if dimension == 'product_code':
        row = conn.execute('SELECT product_type FROM source.incident WHERE product_code=%s AND product_type IS NOT NULL LIMIT 1', (key,)).fetchone()
        return row['product_type'] if row else key
    return key


def breakdown(conn, filters, dimension, limit):
    field, extra = grouping(dimension)
    where, args = filters_sql(filters)
    rows = conn.execute(f"SELECT coalesce({field},'__unknown__') key,count(*) count,count(*) FILTER (WHERE s.is_injury AND s.rank<>9) injury_count,count(*) FILTER (WHERE s.rank=9) death_count" + JOIN + extra + where + ' GROUP BY 1 ORDER BY count DESC,key LIMIT %s', [*args, limit]).fetchall()
    return m.Breakdown(caveat=CAVEAT, dimension=dimension, rows=[{**r, 'label': label(conn, dimension, r['key'])} for r in rows])


def trend(conn, filters, interval, group_by, top):
    where, args = filters_sql(filters)
    field, extra = ("'all'", '') if group_by == 'none' else grouping(group_by)
    rows = conn.execute(f"SELECT date_trunc(%s,i.report_date)::date period,coalesce({field},'__unknown__') key,count(*) count" + JOIN + extra + where + ' GROUP BY 1,2 ORDER BY 1,2', [interval, *args]).fetchall()
    totals = defaultdict(int)
    for r in rows:
        totals[r['key']] += r['count']
    selected = sorted(totals, key=lambda k: (-totals[k], k))[:top]
    series = defaultdict(lambda: defaultdict(int))
    for r in rows:
        key = r['key'] if r['key'] in selected else '__other__'
        series[key][r['period']] += r['count']
    periods = sorted(set(r['period'] for r in rows))
    if periods:
        end = periods[-1]
        year, month = periods[0].year, periods[0].month
        periods = []
        step = {'month': 1, 'quarter': 3, 'year': 12}[interval]
        while (period := end.replace(year=year, month=month, day=1)) <= end:
            periods.append(period)
            year, month = year + (month - 1 + step) // 12, (month - 1 + step) % 12 + 1
    newest = conn.execute('SELECT max(report_date) newest FROM source.incident').fetchone()['newest']
    return m.Trend(caveat=CAVEAT, interval=interval, incomplete_after=newest-timedelta(days=30), series=[{'key': k, 'label': 'Other' if k == '__other__' else 'All reports' if k == 'all' else label(conn, group_by, k), 'points': [{'period': p, 'count': series[k][p]} for p in periods], 'total': sum(series[k].values())} for k in [*selected, '__other__'] if k in series])


def spike_values(recent, baseline, window_days):
    expected = baseline * window_days / 365
    z = (recent - expected) / math.sqrt(max(expected, 1))
    return expected, (recent / expected if expected else float(recent)), z


def spikes(conn, dimension, window_days, min_count, limit):
    newest = conn.execute('SELECT max(report_date) newest FROM source.incident').fetchone()['newest']
    end = newest - timedelta(days=30)
    start = end - timedelta(days=window_days-1)
    baseline_end = start-timedelta(days=1)
    baseline_start = start-timedelta(days=365)
    field, extra = grouping(dimension)
    where, args = filters_sql(m.Filters(report_date_from=baseline_start, report_date_to=end))
    rows = conn.execute(f'SELECT {field} key,count(*) FILTER (WHERE i.report_date >= %s) recent,count(*) FILTER (WHERE i.report_date < %s) baseline' + JOIN + extra + where + f' GROUP BY {field}', [start, start, *args]).fetchall()
    kept = []
    for row in rows:
        expected, ratio, z = spike_values(row['recent'], row['baseline'], window_days)
        if row['recent'] >= min_count and z >= 3:
            kept.append({'key': row['key'], 'label': label(conn, dimension, row['key']), 'recent_count': row['recent'], 'expected_count': expected, 'ratio': ratio, 'z': z, 'filters': {dimension: [row['key']], 'report_date_from': start, 'report_date_to': end}})
    return m.Spikes(caveat=CAVEAT, window={'start': start, 'end': end}, baseline={'start': baseline_start, 'end': baseline_end}, rows=sorted(kept, key=lambda r: (-r['z'], r['key']))[:limit])
