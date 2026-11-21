"""Build the recall ledger that scores Heuristic Lab replays.

Links every public report in the database to later CPSC notices with the strict
model-match tier from `watchlist_linkage`, applying every archived human review and
documented earlier action. Rerun after loading new reports or notices:

    python -m scripts.replay_ledger
"""

import argparse
import csv
import gzip
import json
import re
from datetime import date
from pathlib import Path

from psycopg.rows import dict_row

from cpsc360 import db
from cpsc360.lab_replay import LEDGER_PATH
from scripts.watchlist_linkage import identifiers, link_reports, model_terms, read_overrides
from scripts.watchlist_score import EARLIER_ACTIONS, LEDGER, REVIEWS, read_json

# Reviews that decided only the strict tier, as `strict` yes/no.
STRICT_REVIEWS = ('watchlist-blind-review.csv', 'watchlist-2012-review.csv', 'watchlist-2014-review.csv',
                  'watchlist-2020-queue-review.csv', 'watchlist-historical-queue-review.csv',
                  'watchlist-historical-reachable.csv')
# A replay can run for years, so a covered model counts however long CPSC took to act.
HORIZON_DAYS = 100_000
# Battery sizes, voltages and storage sizes read like model numbers but are shared by many products.
PART_CODE = re.compile(r'(?:cr|lr|sr|ag)\d+|\d+v(?:ac|dc)|\d+(?:gb|tb|mb)')


def model_like(code):
    """A code from a report's free text counts as a model only when it reads like one.

    Text is full of "3-way", "2-burner", "Hover-1" or "1080p", which the strict tier would
    otherwise match against unrelated notices that use the same words.
    """
    return (len(re.findall(r'[a-z]', code)) >= 2 and len(re.findall(r'\d', code)) >= 2
            and not PART_CODE.fullmatch(code))


def weak_match(report, reason):
    """Whether every code a strict link matched is too generic to name the reported model.

    That is a code from the report's text that doesn't read like a model, or a model of two or
    three digits, such as "790", the prefix Sears puts on every Kenmore range Electrolux makes.
    """
    # `link_reports` writes the reason as "[org] <matched codes> <product words> <hazard words>".
    words = reason.split()
    if words[:1] == ['org']:
        words = words[1:]
    matched = set(words[0].split(',')) if words else set()
    text = identifiers(' '.join((report['product_description'] or '', report['incident_description'] or '')))
    codes, numeric, named = model_terms({**report, 'product_description': '', 'incident_description': ''})

    def weak(code):
        if code.isdigit() and len(code) <= 3:
            return True
        return code in text and code not in codes | numeric | named and not model_like(code)
    return bool(matched) and all(weak(code) for code in matched)


def reviews():
    verdicts = read_overrides(REVIEWS)
    public_on = {}
    for name in STRICT_REVIEWS:
        with LEDGER.with_name(name).open(encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                pair = row['report_no'], row['notice_no']
                verdict = 'strict' if row['strict'] == 'yes' else 'none'
                if (verdicts.get(pair) in ('strict', 'both')) != (verdict == 'strict') and pair in verdicts:
                    raise ValueError(f'Conflicting reviews for {pair}')
                verdicts.setdefault(pair, verdict)
                if row.get('first_public_action'):
                    public_on[pair] = date.fromisoformat(row['first_public_action'])
    return verdicts, public_on


def build(reports, notices, verdicts, public_on, earlier):
    candidates = []
    links = link_reports(reports, notices, verdicts, candidates=candidates, horizon=HORIZON_DAYS)
    published = {r['report_no']: r['publication_date'] for r in reports}
    by_report = {r['report_no']: r for r in reports}
    for candidate in candidates:
        pair = candidate['report_no'], candidate['notice_no']
        if candidate['strict'] and pair not in verdicts and weak_match(by_report[pair[0]], candidate['reason']):
            links[pair[0]].strict.pop(pair[1], None)
    for action in earlier:
        if action['report_no'] in links and date.fromisoformat(action['date']) <= published[action['report_no']]:
            links[action['report_no']].strict.clear()
    by_number = {str(n['RecallNumber']): n for n in notices}
    pairs = []
    for report_no, link in sorted(links.items()):
        for notice_no in sorted(link.strict):
            announced = date.fromisoformat(by_number[notice_no]['RecallDate'][:10])
            # A public warning before the notice ends the chance to catch the report early.
            known = min(announced, public_on.get((report_no, notice_no), announced))
            if known > published[report_no]:
                pairs.append([report_no, notice_no, known.isoformat()])
    used = {notice_no for _, notice_no, _ in pairs}
    return {
        'method': 'watchlist-linkage strict tier with archived reviews',
        'snapshot_last': max(published.values()).isoformat(),
        'notices': {no: {'announced': by_number[no]['RecallDate'][:10], 'title': by_number[no]['Title'],
                         'url': by_number[no]['URL']} for no in sorted(used)},
        'links': pairs,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=LEDGER_PATH)
    args = parser.parse_args(argv)
    with db.connect() as conn:
        conn.row_factory = dict_row
        reports = conn.execute('''
            SELECT report_no, publication_date, manufacturer_name, brand, model, product_type,
                   product_description, incident_description
              FROM source.incident ORDER BY publication_date, report_no
        ''').fetchall()
    verdicts, public_on = reviews()
    with EARLIER_ACTIONS.open(encoding='utf-8') as stream:
        earlier = list(csv.DictReader(stream))
    ledger = build(reports, read_json(LEDGER), verdicts, public_on, earlier)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(json.dumps(ledger, separators=(',', ':')).encode(), mtime=0))
    print(f"{len(ledger['links'])} links to {len(ledger['notices'])} notices → {args.output}")


if __name__ == '__main__':
    main()
