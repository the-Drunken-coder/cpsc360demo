"""Score the preregistered watchlist against public CPSC actions and export a review queue."""

import argparse
import csv
import gzip
import hashlib
import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from psycopg.rows import dict_row

from cpsc360 import db
from cpsc360.derive import manufacturer_key, product_model_key
from scripts.watchlist_linkage import link_reports, read_overrides
from scripts.watchlist_rules import END, START, flag_reports

LEDGER = Path(__file__).resolve().parents[1] / 'tests/fixtures/cpsc-notices.json.gz'
REVIEWS = LEDGER.with_name('watchlist-adjudications.csv')
REPORTS = LEDGER.with_name('watchlist-reports.json.gz')
EARLIER_ACTIONS = LEDGER.with_name('watchlist-earlier-actions.csv')
LOOKBACK = START - timedelta(days=90)
SNAPSHOT_END = END + timedelta(days=365)
RULES = ('admission', 'mechanism', 'specific', 'repair')
AUDIT_SEED = 20


def read_json(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def load_reports(path):
    if path:
        rows = read_json(path)
        for row in rows:
            row['publication_date'] = date.fromisoformat(row['publication_date'])
    else:
        with db.connect() as conn:
            conn.row_factory = dict_row
            bounds = conn.execute('SELECT MIN(publication_date) AS first, MAX(publication_date) AS last '
                                  'FROM source.incident').fetchone()
            if not bounds['first'] or bounds['first'] > LOOKBACK or bounds['last'] < SNAPSHOT_END:
                raise ValueError('Reports database does not cover the specified snapshot')
            rows = conn.execute('''
                SELECT i.*, coalesce(s.is_injury, false) AS is_injury
                FROM source.incident i LEFT JOIN source.severity_level s ON s.label = i.severity
                WHERE i.publication_date BETWEEN %s AND %s
                ORDER BY i.publication_date, i.report_no
            ''', (LOOKBACK, END)).fetchall()
    for row in rows:
        row['manufacturer_key'] = manufacturer_key(row['manufacturer_name'])
        row['model_key'] = product_model_key(row['model'], row['brand'], row['manufacturer_name'])
    return [r for r in rows if LOOKBACK <= r['publication_date'] <= END]


def metrics(report_ids, links, rates):
    size = len(report_ids)
    result = {'flags': size, 'already_recalled': sum(bool(links[i].prior) for i in report_ids)}
    for tier in ('strict', 'loose'):
        matches = [getattr(links[i], tier) for i in report_ids if not links[i].prior and getattr(links[i], tier)]
        positives = len(matches)
        precision = positives / size if size else None
        expected = size * rates[tier]
        result[tier] = {
            'positives': positives, 'precision': precision, 'expected_random_hits': expected,
            'lift': positives / expected if expected else None,
            'distinct_notices': len({number for linked in matches for number in linked}),
            'median_lead_days': statistics.median(min(linked.values()) for linked in matches) if matches else None,
        }
    return result


def write_jsonl(path, rows):
    with path.open('w', encoding='utf-8') as stream:
        for row in rows:
            print(json.dumps(row, default=str, ensure_ascii=False), file=stream)


def score(rows, notices, overrides, output, earlier_actions=()):
    flags = flag_reports(rows)
    holdout = [row for row in rows if START <= row['publication_date'] <= END]
    ids = {row['report_no'] for row in holdout}
    if not ids or len(ids) != len(holdout) or ids != flags.keys():
        raise ValueError('Each holdout report must have exactly one rule decision')
    candidates = []
    links = link_reports(holdout, notices, overrides, candidates)
    if ids != links.keys():
        raise ValueError('Every holdout report requires a linkage decision')
    # The recall API skips some public warnings. A documented earlier warning can
    # disqualify a later recall, but can never add a future hit to the fixed ledger.
    publication = {r['report_no']: r['publication_date'] for r in holdout}
    for action in earlier_actions:
        rid = action['report_no']
        if date.fromisoformat(action['date']) > publication[rid]:
            raise ValueError(f'Prior action postdates report {rid}')
        links[rid].prior.add(action['notice_no'])
        links[rid].strict.clear()
        links[rid].loose.clear()
    rates = {tier: sum(bool(getattr(link, tier)) and not link.prior for link in links.values()) / len(ids)
             for tier in ('strict', 'loose')}
    combined = {i for i in ids if flags[i]}
    queues = {'all_reports': ids, 'combo': combined}
    queues.update({rule: {i for i in ids if rule in flags[i]} for rule in RULES})
    summary = {name: metrics(queue, links, rates) for name, queue in queues.items()}
    summary['coverage'] = {
        'caught': summary['combo']['strict']['distinct_notices'],
        'reachable': summary['all_reports']['strict']['distinct_notices'],
    }
    fields = ('report_no', 'publication_date', 'manufacturer_name', 'model', 'brand', 'serial_number',
              'product_type', 'product_description', 'incident_description', 'severity',
              'purchase_date', 'date_manufactured', 'manufacturer_date_code', 'retailer', 'company_comments')
    evidence = {}
    for row in holdout:
        i = row['report_no']
        link = links[i]
        evidence[i] = {
            **{f: row.get(f) for f in fields}, 'flags': sorted(flags[i]),
            'strict': {} if link.prior else link.strict, 'loose': {} if link.prior else link.loose,
            'prior': sorted(link.prior),
        }
    negatives = sorted(i for i in combined if not evidence[i]['strict'] and not evidence[i]['loose'])
    sample = sorted(negatives, key=lambda i: hashlib.sha256(f'{AUDIT_SEED}:{i}'.encode()).digest())[:20]
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / 'reports.jsonl', (evidence[i] for i in sorted(ids)))
    write_jsonl(output / 'candidates.jsonl', candidates)
    write_jsonl(output / 'strict-positive-reports.jsonl', (evidence[i] for i in sorted(ids) if evidence[i]['strict']))
    write_jsonl(output / 'false-positive-sample.jsonl', (evidence[i] for i in sample))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--reports', type=Path, help='Alternative input reports in JSON or gzipped JSON.')
    source.add_argument('--database', action='store_true', help='Load reports from the local SaferProducts database.')
    parser.add_argument('--notices', type=Path, default=LEDGER)
    parser.add_argument('--overrides', type=Path, help='Adjudicated report/notice pair verdicts. Defaults to the archived reviews for the standard replay.')
    parser.add_argument('--earlier-actions', type=Path, help='Documented earlier actions absent from the API archive.')
    parser.add_argument('--ledger-only', action='store_true', help='Restrict prior exclusions to the notice ledger as well.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    notices = read_json(args.notices)
    if args.notices == LEDGER and len(notices) != 4788:
        raise ValueError('Unexpected notice ledger size')
    standard = args.reports is None and args.notices == LEDGER
    reviews = args.overrides or (REVIEWS if standard else None)
    earlier_path = args.earlier_actions or (EARLIER_ACTIONS if standard else None)
    earlier = []
    if earlier_path and not args.ledger_only:
        with earlier_path.open(encoding='utf-8') as stream:
            earlier = list(csv.DictReader(stream))
    rows = load_reports(None if args.database else args.reports or REPORTS)
    summary = score(rows, notices, read_overrides(reviews), args.output, earlier)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
