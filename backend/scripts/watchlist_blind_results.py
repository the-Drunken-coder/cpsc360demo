"""Score locked review lists against verified model links in the independent cohorts."""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

from scripts.watchlist_historical_check import load_cohort
from scripts.watchlist_score import LEDGER, read_json


def score(dates, reviews, publications, notices):
    hits = []
    for r in reviews:
        rid, notice = r['report_no'], r['notice_no']
        if r['strict'] != 'yes' or rid not in dates or rid not in publications:
            continue
        pub = date.fromisoformat(publications[rid])
        announcement = notices[notice]
        considered = date.fromisoformat(dates[rid])
        first = date.fromisoformat(r['first_public_action']) if r.get('first_public_action') else announcement
        if 1 <= (announcement-pub).days <= 365 and considered < min(first,announcement):
            hits.append({'report':rid,'notice':notice,'days':(announcement-considered).days})
    return {'reviews':len(dates),'reports':len({x['report'] for x in hits}),
            'notices':sorted({x['notice'] for x in hits}),'hits':hits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schedules',type=Path)
    args = parser.parse_args()
    notices = {n['RecallNumber']:date.fromisoformat(n['RecallDate'][:10]) for n in read_json(LEDGER)}
    for y in (2012,2014,2016,2018):
        filename = f'watchlist-{y}-review.csv' if y in (2012,2014) else 'watchlist-blind-review.csv'
        with LEDGER.with_name(filename).open() as f:
            reviews = list(csv.DictReader(f))
        pubs = {r['report_no']:r['publication_date'] for r in load_cohort(y)}
        schedules = json.loads((args.schedules / f'{y}.json').read_text())
        reachable = score(pubs, reviews, pubs, notices)['notices']
        print(json.dumps({
            'start_year': y,
            'publications': len(pubs),
            'verified_reachable': reachable,
            'queues': {k: score(v, reviews, pubs, notices) for k, v in schedules.items()},
        }))


if __name__ == '__main__':
    main()
