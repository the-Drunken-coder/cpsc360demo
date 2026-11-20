"""Compare weekly review against public actions still in the future on review day."""
import argparse
import json
from datetime import date
from pathlib import Path

from cpsc360.derive import product_model_key
from scripts.watchlist_climb import development, measure
from scripts.watchlist_family_signals import signals
from scripts.watchlist_queue import protect_first_schedule, schedule


def incumbent(r):
    return bool(product_model_key(r['model'],r['brand'],r['manufacturer_name']) and signals(r))


def replay(rows, decisions):
    adjusted = []
    for r in rows:
        day = date.fromisoformat(str(r['publication_date'])[:10])
        delay = (decisions.get(r['report_no'], day)-day).days
        announced = {n for n, lead in r['strict'].items() if lead <= delay}
        labels = {tier: {n: lead-delay for n, lead in r[tier].items() if lead > delay and not announced}
                  for tier in ('strict','loose')}
        adjusted.append({**r, **labels, 'prior': set(r['prior']) | announced})
    result = measure(adjusted, decisions)
    result['reachable'] = len({n for r in rows for n in r['strict']})
    result['caught'] = sorted({n for r in adjusted if r['report_no'] in decisions for n in r['strict']})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path)
    parser.add_argument('--tie-seed', default='', help='Change only deterministic tie ordering for a sensitivity check.')
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.reports.read_text().splitlines()]
    for name, group in [('previous validation',[r for r in rows if not development(r)]),('all',rows)]:
        old = {r['report_no']:date.fromisoformat(r['publication_date']) for r in group if incumbent(r)}
        for variant,dates in [('previous',old),('budget only',schedule(group,expanded=False,tie_seed=args.tie_seed)),('expanded',schedule(group,tie_seed=args.tie_seed)),
                              ('protect first',protect_first_schedule(group))]:
            print(name,variant,json.dumps(replay(group,dates)))

    shared = schedule(rows,tie_seed=args.tie_seed)
    cohort = [r for r in rows if not development(r)]
    print('previous validation within shared stream', json.dumps(replay(cohort,shared)))
