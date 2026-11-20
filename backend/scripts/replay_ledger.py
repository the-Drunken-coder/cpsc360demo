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
from datetime import date
from pathlib import Path

from psycopg.rows import dict_row

from cpsc360 import db
from cpsc360.lab_replay import LEDGER_PATH
from scripts.watchlist_linkage import link_reports, read_overrides
from scripts.watchlist_score import EARLIER_ACTIONS, LEDGER, REVIEWS, read_json

# Reviews that decided only the strict tier, as `strict` yes/no.
STRICT_REVIEWS = ('watchlist-blind-review.csv', 'watchlist-2012-review.csv', 'watchlist-2014-review.csv',
                  'watchlist-2020-queue-review.csv', 'watchlist-historical-queue-review.csv',
                  'watchlist-historical-reachable.csv')
# A replay can run for years, so a covered model counts however long CPSC took to act.
HORIZON_DAYS = 100_000


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
    links = link_reports(reports, notices, verdicts, horizon=HORIZON_DAYS)
    published = {r['report_no']: r['publication_date'] for r in reports}
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
