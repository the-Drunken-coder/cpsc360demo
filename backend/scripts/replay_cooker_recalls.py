"""Replay pressure-release signals and compare them with manually checked recall evidence.

From backend run PYTHONPATH=. python scripts/replay_cooker_recalls.py [--alerts].
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta

from psycopg.rows import dict_row

from cpsc360 import db, lab_public, lab_rules as rules


def cooker_rule(name, *conditions):
    return rules.Rule[rules.CaseAction](
        name=name, action={'kind': 'watchlist'}, match='all',
        conditions=[{'kind': 'text', 'field': 'product', 'operator': 'equals_any',
                     'value': 'Pressure Cookers or Canners'}, *conditions])


def narrative(phrases):
    return {'kind': 'text', 'field': 'narrative', 'operator': 'contains_any', 'value': phrases}


RULES = [
    cooker_rule('All cookers'),
    cooker_rule('Hospital admission', {'kind': 'flag', 'field': 'hospitalized', 'state': 'yes'}),
    cooker_rule('Lid and ejection', narrative('lid'),
                narrative('popped off,blew off,flew off,explod,spray,spew,expel,eject,erupt')),
    cooker_rule('Ejection and hot contents', narrative('explod,spray,spew,expel,eject,erupt'),
                narrative('hot water,hot liquid,hot contents,soup,broth,stew,scald')),
]

# Audit labels never enter the rules. Each report below has model and mechanism
# evidence in the snapshot. See docs/recall-early-warning.md for attribution.
CASES = {
    'Crock-Pot': (date(2020, 11, 24), set()),
    'Bella': (date(2023, 8, 10), {'20180123-B69D6-1728384'}),
    'Insignia': (date(2023, 10, 26), set()),
    'Ninja': (date(2025, 5, 1), {'20200210-472E0-2147374912', '20200221-1E546-1955848'}),
    'Ambiano': (date(2025, 10, 9), set()),
}


def replay(reports):
    history = rules.History(RULES)
    last_signal = {}
    for report in reports:
        facts = rules.report_facts(report)
        labels = {match.rule for match in rules.apply_rules(RULES, facts, history, report.available_on)}
        if labels.intersection({'Lid and ejection', 'Ejection and hot contents'}):
            labels.add('Either mechanism')
            maker = report.manufacturer_key
            if maker:
                # Multiple publications on the same date do not corroborate each other.
                prior, latest = last_signal.get(maker, (None, None))
                if latest != report.available_on:
                    prior, latest = latest, report.available_on
                if prior and latest - prior <= timedelta(days=365):
                    labels.add('Repeat mechanism at maker')
                last_signal[maker] = prior, latest
        if labels:
            yield report, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alerts', action='store_true', help='Show report IDs for manual adjudication')
    verbose = parser.parse_args().alerts
    until = date(2026, 11, 4)
    with db.connect() as conn:
        conn.row_factory = dict_row
        bounds = conn.execute('SELECT min(publication_date) first, max(publication_date) last FROM source.incident').fetchone()
        if bounds['first'] is None or bounds['first'] > date(2011, 6, 1) or bounds['last'] < until:
            raise ValueError('Load the public incident snapshot spanning June 2011 through November 4, 2026.')
        reports = (report for year in range(2011, until.year + 1)
                   for report in lab_public.load_reports(conn, date(year, 1, 1), min(date(year, 12, 31), until)))
        counts = Counter()
        first_hits = defaultdict(dict)
        for report, labels in replay(reports):
            counts.update(labels)
            if verbose:
                print(report.available_on, report.id, report.manufacturer_key, report.facts.get('model'), sorted(labels))
            for case, (day, ids) in CASES.items():
                if report.id in ids and report.available_on < day:
                    for label in labels:
                        first_hits[label].setdefault(case, (report.id, (day - report.available_on).days))
    for label in [rule.name for rule in RULES] + ['Either mechanism', 'Repeat mechanism at maker']:
        print(label, counts[label], 'reviews;', dict(first_hits[label]))


if __name__ == '__main__':
    main()
