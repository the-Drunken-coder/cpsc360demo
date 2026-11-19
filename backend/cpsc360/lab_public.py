"""Adapt the current SaferProducts.gov snapshot to the rule replay."""

from datetime import date, timedelta

from fastapi import HTTPException

from . import heuristic_lab as lab, lab_rules
from .derive import HAZARD_LABELS, product_model_key

VERSION = 'saferproducts-public-v1'
PREFERRED_START = date(2025, 1, 15)
ONE_DAY = timedelta(days=1)


def bounds(conn) -> tuple[date, date]:
    row = conn.execute('SELECT min(publication_date) first, max(publication_date) last FROM source.incident').fetchone()
    if row['first'] is None:
        raise HTTPException(409, 'Load the SaferProducts.gov snapshot to replay public reports.')
    first_start = row['first'] - ONE_DAY
    last_start = lab.shift_months(row['last'], -3)
    while lab.end_date(last_start + ONE_DAY) <= row['last']:
        last_start += ONE_DAY
    if last_start < first_start:
        raise HTTPException(409, 'The public snapshot must cover a three-month replay.')
    return first_start, last_start


def validate_start(start: date, first: date, last: date) -> None:
    if not first <= start <= last:
        raise HTTPException(422, f'Choose a start date from {first} to {last}.')


def preview(conn, start: date | None) -> lab.ScenarioView:
    first, last = bounds(conn)
    start = start if start is not None else max(first, min(PREFERRED_START, last))
    validate_start(start, first, last)
    end = lab.end_date(start)
    row = conn.execute('SELECT count(*) AS count FROM source.incident WHERE publication_date > %s AND publication_date <= %s',
                       (start, end)).fetchone()
    return lab.ScenarioView(version=VERSION, first_start=first, last_start=last, as_of=start, end=end,
                            baseline=lab.BASELINE, candidate=lab.CANDIDATE, report_count=row['count'])


def to_report(row: dict) -> lab.Report:
    facts = {}
    for field, column in (('manufacturer', 'manufacturer_name'), ('retailer', 'retailer')):
        if value := (row[column] or '').strip():
            facts[field] = value
    model_key = product_model_key(row['model'], row['brand'], row['manufacturer_name'])
    if model_key is not None:
        facts['model'] = row['model'].strip()
    if row['victim_age'] is not None:
        facts['age'] = row['victim_age']

    severity = row['severity']
    known_severity = bool(row['severity_rank'])
    if known_severity:
        facts['death'] = severity == 'Death'
        if severity not in ('Death', 'Injury, Level of care not known'):
            facts['hospitalized'] = severity == 'Injury, Hospital Admission'

    return lab.Report(
        id=row['report_no'], available_on=row['publication_date'], product=row['product_type'] or row['product_description'],
        hazard=None, hazards=[HAZARD_LABELS[key] for key in row['hazards']],
        injury=row['is_injury'] if known_severity else None, narrative=row['incident_description'], facts=facts,
        product_key=row['product_code'] or None, manufacturer_key=row['manufacturer_key'] if 'manufacturer' in facts else None,
        model_key=model_key, source_sha256=row['current_sha256'],
    )


def replay(conn, request: lab.RunInput[lab_rules.CaseAction]) -> lab.RunResult:
    first, last = bounds(conn)
    validate_start(request.start, first, last)
    end = lab.end_date(request.start)
    lookback = max((condition.window_days for rule in (*request.baseline.triage, *request.candidate.triage)
                    for condition in rule.conditions if isinstance(condition, lab_rules.CountCondition)), default=1)
    earliest = max(first + ONE_DAY, request.start + timedelta(days=2 - lookback))
    rows = conn.execute('''
        SELECT i.report_no, i.publication_date, i.current_sha256, i.product_type, i.product_description,
               i.product_code, i.incident_description, i.severity, i.victim_age, i.manufacturer_name, i.brand, i.model, i.retailer,
               s.rank AS severity_rank, s.is_injury, n.manufacturer_key,
               ARRAY(SELECT h.hazard FROM inference.incident_hazard h WHERE h.report_no = i.report_no ORDER BY h.hazard) AS hazards
          FROM source.incident i
          LEFT JOIN source.severity_level s ON s.label = i.severity
          LEFT JOIN inference.incident_norm n USING (report_no)
         WHERE i.publication_date BETWEEN %s AND %s
         ORDER BY i.publication_date, i.report_no
    ''', (earliest, end)).fetchall()
    reports = [to_report(row) for row in rows]
    cases = tuple(lab.Case(id=report.id, title=report.product, reports=(report,)) for report in reports)
    return lab.RunResult(
        scenario=VERSION, evaluator=lab.EVALUATOR, source='public', start=request.start, end=end, starting_reports=[],
        baseline=lab.evaluate(cases, request.baseline, request.start, end, check_starting_reports=False),
        candidate=lab.evaluate(cases, request.candidate, request.start, end, check_starting_reports=False),
    )
