"""Search arrival-rule pairs under a review budget and evaluate on later publications.

Run from backend with PYTHONPATH=. python scripts/benchmark_triage.py
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations
from math import prod
import json

from psycopg.rows import dict_row

from cpsc360 import db, lab_public, lab_rules as rules

DAY = timedelta(days=1)
START = date(2020, 1, 1)
SPLIT = date(2024, 1, 1)
LAST = date(2026, 11, 4)
HORIZON = 90


def build_rules():
    candidates = []

    def add(name, *conditions):
        candidates.append(rules.Rule[rules.CaseAction](
            name=name, match='all', conditions=conditions, action={'kind': 'watchlist'}))

    for group in ('make_model', 'manufacturer_hazard', 'product_hazard', 'manufacturer'):
        for days, threshold in ((14, 2), (30, 3), (90, 5)):
            count = dict(kind='count', group=group, window_days=days, threshold=threshold)
            add(f'{group} repeats {threshold}/{days}d', count)
            add(f'{group} injury repeats {threshold}/{days}d', dict(count, filter='injury'))
    for group in ('manufacturer', 'manufacturer_hazard', 'make_model'):
        add(f'Prior admission in {group}', dict(kind='count', group=group, window_days=90,
                                                filter='hospitalized', threshold=1))
    add('Injuries across three makers', dict(kind='count', group='product_hazard', window_days=30,
                                             filter='injury', measure='manufacturers', threshold=3))
    add('Model pair in a week, at most three in a month',
        dict(kind='count', group='make_model', window_days=7, threshold=2),
        dict(kind='count', group='make_model', window_days=30, operator='lte', threshold=3))
    for name, terms in (
        ('Rescue intervention', 'cpr,resuscitated,heimlich,ambulance,unconscious'),
        ('Near miss', 'almost,nearly,just in time,narrowly,thankfully,fortunately'),
        ('Airway or immersion', 'choking,suffocation,drowning,strangulation'),
        ('Stored energy', 'explosion,exploded,shattered,ruptured,projectile'),
        ('Failed safeguard', 'shut off,turn off,safety latch,safety lock,guard failed'),
    ):
        signal = dict(kind='score', terms=terms, operator='gte', threshold=1)
        add(name, signal)
        add(name + ' with maker recurrence', signal, dict(kind='count', group='manufacturer',
                                                        threshold=3, window_days=30))
    add('Child with airway or immersion hazard', dict(kind='number', field='age', operator='lte', value=5),
        dict(kind='text', field='hazard', operator='contains_any', value='choking,suffocation,drowning'))
    return candidates


def collect(reports, candidates):
    outcomes = defaultdict(list)
    for r in reports:
        if r.facts.get('death') or r.facts.get('hospitalized'):
            outcomes[r.manufacturer_key, r.product_key].append(r.available_on)
    history = rules.History(candidates)
    hits = [set() for _ in candidates]
    events = {}
    periods = [set(), set()]
    for r in reports:
        facts = rules.report_facts(r)
        history.add(facts)
        day = r.available_on
        if day < START or day > LAST - HORIZON * DAY or (day < SPLIT <= day + HORIZON * DAY):
            continue
        if not r.manufacturer_key or not r.product_key or r.facts.get('death') or r.facts.get('hospitalized'):
            continue
        periods[day >= SPLIT].add(r.id)
        dates = outcomes[r.manufacturer_key, r.product_key]
        future = bisect_right(dates, day)
        if future < len(dates) and dates[future] <= day + HORIZON * DAY:
            events[r.id] = (r.manufacturer_key, r.product_key, dates[future])
        for rule, selected in zip(candidates, hits):
            if all(rules.matches(c, facts, history, day) for c in rule.conditions):
                selected.add(r.id)
    return hits, events, periods


def expected_events(population, events, alerts):
    """Expected distinct next events from a uniform queue of the same size."""
    sizes = Counter(events[i] for i in population.intersection(events))
    total = len(population)
    return sum(1 - prod((total - alerts - j) / (total - j) for j in range(size))
               for size in sizes.values())


def main():
    candidates = build_rules()
    with db.connect() as conn:
        conn.row_factory = dict_row
        if lab_public.bounds(conn)[0] >= START - 90 * DAY or conn.execute(
                'SELECT max(publication_date) last FROM source.incident').fetchone()['last'] < LAST:
            raise ValueError('Snapshot does not cover the benchmark dates')
        reports = lab_public.load_reports(conn, START - 90 * DAY, LAST)
    hits, events, periods = collect(reports, candidates)
    positive = set(events)
    for label, population in zip(('development', 'holdout'), periods):
        print(label, len(population), 'reports;', len(population & positive), 'positive reports;',
              len({events[i] for i in population & positive}), 'distinct next events')
    for budget in (.01, .05, .10):
        best = None
        for size in (1, 2):
            for indices in combinations(range(len(hits)), size):
                flagged = set.union(*(hits[i] for i in indices)) & periods[0]
                if not flagged or len(flagged) > budget * len(periods[0]):
                    continue
                correct = flagged & positive
                rank = (len({events[i] for i in correct}), len(correct), -len(flagged), -size)
                if best is None or rank > best[0]:
                    best = rank, indices
        if best is None:
            continue
        indices = best[1]
        print('budget', budget, json.dumps([candidates[i].model_dump() for i in indices]))
        for population in periods:
            flagged = set.union(*(hits[i] for i in indices)) & population
            correct = flagged & positive
            print('alerts / positive alerts / distinct next events', len(flagged), len(correct),
                  len({events[i] for i in correct}), 'uniform expectation',
                  round(expected_events(population, events, len(flagged)), 2))
    for rule, selected in zip(candidates, hits):
        flagged = selected & periods[1]
        print(rule.name, len(flagged), len(flagged & positive), len({events[i] for i in flagged & positive}))


if __name__ == '__main__':
    main()
