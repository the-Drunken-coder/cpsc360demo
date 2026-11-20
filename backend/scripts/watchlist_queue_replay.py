"""Compare weekly review against public actions still in the future on review day."""
import argparse
import json
from datetime import date
from pathlib import Path

from cpsc360.derive import product_model_key
from scripts.watchlist_climb import development, measure
from scripts.watchlist_family_signals import signals
from scripts.watchlist_queue import schedule


def incumbent(r):
    return bool(product_model_key(r['model'],r['brand'],r['manufacturer_name']) and signals(r))


def replay(rows, decisions):
    adjusted = []
    for r in rows:
        day = date.fromisoformat(str(r['publication_date'])[:10])
        delay = (decisions.get(r['report_no'], day)-day).days
        adjusted.append({**r, **{tier:{n:lead-delay for n,lead in r[tier].items() if lead>delay} for tier in ('strict','loose')}})
    result = measure(adjusted, decisions)
    result['reachable'] = len({n for r in rows for n in r['strict']})
    result['caught'] = sorted({n for r in adjusted if r['report_no'] in decisions for n in r['strict']})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path)
    rows = [json.loads(line) for line in parser.parse_args().reports.read_text().splitlines()]
    for name, group in [('previous validation',[r for r in rows if not development(r)]),('all',rows)]:
        old = {r['report_no']:date.fromisoformat(r['publication_date']) for r in group if incumbent(r)}
        for variant,dates in [('previous',old),('budget only',schedule(group,expanded=False)),('expanded',schedule(group))]:
            print(name,variant,json.dumps(replay(group,dates)))
