"""Play the public snapshot forward one window at a time, revealing recalls as CPSC announces them.

The browser asks for consecutive windows of publication days. Each window carries the
reports published in it, which rules matched each report, and the recall notices
announced in it with the earlier replay reports they cover. Scoring hand flags happens
in the browser, so the server keeps no replay state.
"""

import gzip
import json
from collections import defaultdict
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import NamedTuple

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import heuristic_lab as lab, lab_public, lab_rules

LEDGER_PATH = Path(__file__).with_name('replay-recalls.json.gz')
MAX_WINDOW_DAYS = 62
SNIPPET_CHARS = 200


class Notice(NamedTuple):
    announced: date
    title: str
    url: str


class Ledger(NamedTuple):
    method: str
    snapshot_last: date
    notices: dict[str, Notice]
    # Notice number → (report number, last day a flag still counts as early).
    reports: dict[str, list[tuple[str, date]]]


@cache
def ledger() -> Ledger:
    """The strict-tier recall links built by `scripts.replay_ledger`."""
    with gzip.open(LEDGER_PATH, 'rt', encoding='utf-8') as stream:
        raw = json.load(stream)
    reports: dict[str, list[tuple[str, date]]] = defaultdict(list)
    for report_no, notice_no, known in raw['links']:
        reports[notice_no].append((report_no, date.fromisoformat(known) - timedelta(days=1)))
    notices = {no: Notice(date.fromisoformat(n['announced']), n['title'], n['url']) for no, n in raw['notices'].items()}
    return Ledger(raw['method'], date.fromisoformat(raw['snapshot_last']), notices, dict(reports))


class ReplayBounds(BaseModel):
    first: date
    last: date
    start: date
    end: date
    ledger_method: str
    ledger_last: date


class ReplayInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    start: date
    end: date
    since: date
    until: date
    rules: list[lab_rules.Rule[lab_rules.CaseAction]] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def validate_window(self):
        if not self.start <= self.since <= self.until <= self.end:
            raise ValueError('The window must fall inside the replay, in order.')
        if (self.until - self.since).days >= MAX_WINDOW_DAYS:
            raise ValueError(f'Request at most {MAX_WINDOW_DAYS} days at a time.')
        if any(rule.trigger != 'arrival' for rule in self.rules):
            raise ValueError('Replay evaluates rules as reports arrive. Remove end-of-replay rules.')
        return self


class ReplayReport(BaseModel):
    id: str
    published: date
    title: str
    product: str
    snippet: str
    rules: list[int] = Field(description='Positions of the matching rules in the request, in rule order.')
    evidence: list[str] = Field(description='Evidence for the first matching rule.')


class LinkedReport(BaseModel):
    id: str
    published: date
    title: str
    flag_by: date = Field(description='The last day a flag counts as early.')


class ReplayRecall(BaseModel):
    notice_no: str
    announced: date
    title: str
    url: str
    reports: list[LinkedReport] = Field(description='Covered reports published in the replay before the announcement.')


class ReplayWindow(BaseModel):
    since: date
    until: date
    reports: list[ReplayReport]
    recalls: list[ReplayRecall]


def snapshot_bounds(conn) -> tuple[date, date]:
    row = conn.execute('SELECT min(publication_date) first, max(publication_date) last FROM source.incident').fetchone()
    if row['first'] is None:
        raise HTTPException(409, 'Load the SaferProducts.gov snapshot to replay public reports.')
    return row['first'], row['last']


def bounds(conn) -> ReplayBounds:
    first, last = snapshot_bounds(conn)
    links = ledger()
    return ReplayBounds(first=first, last=last, start=max(first, lab.shift_months(last, -12)), end=last,
                        ledger_method=links.method, ledger_last=links.snapshot_last)


def title(row: dict) -> str:
    maker = (row['brand'] or row['manufacturer_name'] or '').strip()
    model = (row['model'] or '').strip()
    return ' '.join(filter(None, (maker, model))) or row['product_type'] or row['product_description'] or row['report_no']


def snippet(text: str) -> str:
    text = ' '.join(text.split())
    return text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS - 1].rstrip() + '…'


def evaluate(rows: list[dict], rules: list[lab_rules.Rule], since: date) -> list[ReplayReport]:
    history = lab_rules.History(rules)
    reports = []
    for row in rows:
        report = lab_public.to_report(row)
        facts = lab_rules.report_facts(report)
        history.add(facts)
        if report.available_on < since:
            continue
        matched = [(position, evidence) for position, rule in enumerate(rules)
                   if (evidence := lab_rules.rule_evidence(rule, facts, history, report.available_on))]
        reports.append(ReplayReport(
            id=report.id, published=report.available_on, title=title(row), product=report.product or '',
            snippet=snippet(report.narrative), rules=[position for position, _ in matched],
            evidence=matched[0][1] if matched else [],
        ))
    return reports


def recalls(conn, start: date, since: date, until: date) -> list[ReplayRecall]:
    links = ledger()
    announced = sorted((notice.announced, no) for no, notice in links.notices.items() if since <= notice.announced <= until)
    wanted = {report_no for _, no in announced for report_no, _ in links.reports[no]}
    rows = {row['report_no']: row for row in conn.execute('''
        SELECT report_no, publication_date, brand, manufacturer_name, model, product_type, product_description
          FROM source.incident WHERE report_no = ANY(%s)
    ''', (sorted(wanted),))}
    result = []
    for day, no in announced:
        reports = sorted((LinkedReport(id=report_no, published=row['publication_date'], title=title(row), flag_by=flag_by)
                          for report_no, flag_by in links.reports[no]
                          if (row := rows.get(report_no)) and start <= row['publication_date'] <= flag_by),
                         key=lambda report: (report.published, report.id))
        if reports:
            notice = links.notices[no]
            result.append(ReplayRecall(notice_no=no, announced=day, title=notice.title, url=notice.url, reports=reports))
    return result


def window(conn, request: ReplayInput) -> ReplayWindow:
    first, last = snapshot_bounds(conn)
    if not first <= request.start <= request.end <= last:
        raise HTTPException(422, f'Choose replay dates from {first} to {last}.')
    # Rolling counts look back before the window, and before the replay start, as the batch Lab does.
    lookback = max((condition.window_days for rule in request.rules for condition in rule.conditions
                    if isinstance(condition, lab_rules.CountCondition)), default=1)
    rows = lab_public.load_rows(conn, request.since - timedelta(days=lookback - 1), request.until)
    return ReplayWindow(since=request.since, until=request.until,
                        reports=evaluate(rows, request.rules, request.since),
                        recalls=recalls(conn, request.start, request.since, request.until))
