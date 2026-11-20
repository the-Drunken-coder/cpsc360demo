"""Replicate the frozen queue comparison on the earlier incident cohorts."""
import argparse
import csv
import json
from datetime import date

from psycopg.rows import dict_row

from cpsc360 import db
from cpsc360.derive import product_model_key
from scripts.watchlist_family_signals import signals
from scripts.watchlist_queue import protect_first_schedule, schedule
from scripts.watchlist_score import LEDGER, read_json

REVIEWS = LEDGER.with_name('watchlist-historical-queue-review.csv')
REACHABLE = LEDGER.with_name('watchlist-historical-reachable.csv')


def load_cohort(start_year):
    with db.connect() as conn:
        conn.row_factory = dict_row
        return conn.execute("""
            SELECT report_no, publication_date::text AS publication_date, manufacturer_name,
                   brand, model, incident_description, product_description, product_type
            FROM source.incident WHERE publication_date BETWEEN %s AND %s
            ORDER BY publication_date, report_no
        """, (date(start_year,1,1), date(start_year+1,12,31))).fetchall()


def reviewed_pairs(paths):
    decisions = {}
    for path in paths:
        with path.open() as stream:
            for row in csv.DictReader(stream):
                key = row['report_no'], row['notice_no']
                value = row['strict'] == 'yes'
                if key in decisions and decisions[key] != value:
                    raise ValueError(f'Conflicting decisions for {key}')
                decisions[key] = value
    return [key for key, yes in decisions.items() if yes]


def score_queue(review_days, publications, notices, accepted):
    hits, actions, leads = set(), set(), []
    for rid, no in accepted:
        if rid not in review_days:
            continue
        notice_day = notices[no]
        lead = (notice_day - review_days[rid]).days
        if lead > 0 and 1 <= (notice_day - publications[rid]).days <= 365:
            hits.add(rid)
            actions.add(no)
            leads.append(dict(report=rid, notice=no, days=lead))
    return dict(reviews=len(review_days), strict_reports=len(hits), distinct_notices=len(actions), links=sorted(leads,key=lambda x:(x['report'],x['notice'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-year', type=int, choices=(2020,2022), default=2022)
    parser.add_argument('--queue-audit-only', action='store_true', help='Use only decisions on the two review queues.')
    args = parser.parse_args()
    rows = load_cohort(args.start_year)
    publications = {r['report_no']: date.fromisoformat(r['publication_date']) for r in rows}
    old = {r['report_no']: publications[r['report_no']] for r in rows
           if product_model_key(r['model'],r['brand'],r['manufacturer_name']) and signals(r)}
    new = schedule(rows)
    notices = {n['RecallNumber']: date.fromisoformat(n['RecallDate'][:10]) for n in read_json(LEDGER)}
    has_denominator = args.start_year == 2022 and not args.queue_audit_only
    queue_reviews = REVIEWS if args.start_year == 2022 else LEDGER.with_name('watchlist-2020-queue-review.csv')
    accepted = reviewed_pairs([queue_reviews, REACHABLE] if has_denominator else [queue_reviews])
    result = {'reports':len(rows), 'incumbent':score_queue(old,publications,notices,accepted),
              'weekly':score_queue(new,publications,notices,accepted)}
    result['protect_first'] = score_queue(protect_first_schedule(rows), publications, notices, accepted)
    if not args.queue_audit_only:
        result['verified_reachable_notices'] = len({n for rid,n in accepted
                                                   if 1 <= (notices[n]-publications[rid]).days <= 365})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
