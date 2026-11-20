"""Fit on development manufacturers, then replay locked choices on unseen manufacturers."""
import argparse
import hashlib
import json
import re
import statistics
from collections import defaultdict
from datetime import date
from itertools import groupby
from pathlib import Path

from cpsc360.derive import manufacturer_key, product_model_key, tag_hazards
from scripts.watchlist_family_signals import signals
from scripts.watchlist_precedent import precedent_signals
from scripts.watchlist_rules import FAILURE
from scripts.watchlist_score import LEDGER, REPORTS, read_json


def maker(row):
    return manufacturer_key(row['manufacturer_name'])


def development(row):
    digest = hashlib.sha256(('watch-v2:' + maker(row)).encode()).digest()
    return int.from_bytes(digest[:4], 'big') % 3 != 0


def candidates(rows, history, notices):
    by_id = {r['report_no']: r for r in rows}
    out = precedent_signals(rows, notices)
    prior_model = {}
    observations = defaultdict(list)
    for day, group in groupby(sorted(history, key=lambda r: r['publication_date']), lambda r: r['publication_date']):
        ordinal = date.fromisoformat(day).toordinal()
        updates = []
        for r in group:
            rid = r['report_no']
            model = product_model_key(r['model'], r['brand'], r['manufacturer_name'])
            key = (maker(r), model)
            text = ' '.join((r['incident_description'] or '').lower().split())
            hazards = tag_hazards(text)
            hazard_keys = [(maker(r), r['product_type'], h) for h in hazards]
            if rid in by_id:
                active = out[rid]
                families = signals(r)
                active.update(families)
                if families:
                    active.add('any product-specific failure')
                if families and model:
                    active.add('identified model with product-specific failure')
                identified = bool(model) or bool(r['serial_number'])
                if identified and re.search(r'(shield|guard|barrier|restraint|brake|latch|lock|alarm|detector).{0,45}(failed|did not|broke|came off|released|missing|loose)', text):
                    active.add('protective component failed')
                if identified and re.search(r'((batter(y|ies)|magnet|small part|bell|bead).{0,55}(swallow|chok|ingest|came loose|dislodg)|swallow.{0,45}(battery|magnet|bead))',text):
                    active.add('accessible small component')
                if re.search(r'(steam|pressure|hose|liquid|lid|fitting).{0,55}(flew off|explod|spray|propell|burst|eject|scald)',text):
                    active.add('energy released from pressure')
                if identified and re.search(r'(tipp?ed over|trapped under|wedg(ed|ing)|fell (through|out of)|pinned under)',text) and re.search(r'infant|toddler|my child|my baby|month.old',text):
                    active.add('child fell out or became trapped')
                active.update('original ' + f for f in by_id[rid]['flags'])
                if model and hazards and ordinal - prior_model.get(key, 0) <= 180:
                    active.add('repeat model with hazard')
                if model and any(len({m for d, m in observations[k] if d >= ordinal-90 and m != model}) >= 2 for k in hazard_keys):
                    active.add('third related model within 90 days')
                if re.search(r'(similar|same|another|other|previous|outside|except|excluded|not (?:part|included|covered)).{0,65}recall|recall.{0,65}(similar|same issue|different|not included|not covered)', text):
                    active.add('related recall mentioned')
                if re.search(r'(inves\w+|fire department|fire marshal|fire investigator).{0,120}(origin|cause|battery|determined|located)', text):
                    active.add('fire investigation')
                if model and re.search(r'reviews?.{0,90}(same|similar)|(same|similar).{0,90}reviews?',text):
                    active.add('other reviews describe recurrence')
                if model and re.search(r'child.resistant|mandatory standard|battery compartment|safety standard',text):
                    active.add('model and safety standard')
                if model and re.search(r'plugged in|overnight|charg(?:ing|er)',text) and re.search(r'exploded|caught fire|caught on fire|went up in flames',text):
                    active.add('identified model ignites under power')
                if model and FAILURE.search(text) and 'Injury' in (r['severity'] or '') and 'No Injury' not in r['severity']:
                    active.add('model failure and injury')
            if model:
                updates.append((key,hazard_keys))
        for key,hazard_keys in updates:
            prior_model[key] = ordinal
            for k in hazard_keys:
                observations[k].append((ordinal,key[1]))
    return out


def measure(rows, selected):
    r = [x for x in rows if x['report_no'] in selected]
    matches = [x for x in r if x['strict']]
    reachable = {n for x in rows for n in x['strict']}
    caught = {n for x in matches for n in x['strict']}
    return dict(reports=len(rows), flags=len(r), strict=len(matches), loose=sum(bool(x['loose']) for x in r),
                notices=len(caught), reachable=len(reachable), prior=sum(bool(x['prior']) for x in r),
                median_days=statistics.median(min(x['strict'].values()) for x in matches) if matches else None)


def climb(rows, features, price, minimum_makers=1):
    pools = defaultdict(set)
    for rid, names in features.items():
        for name in names:
            pools[name].add(rid)
    # The transfer candidate admits only predicates that caught strict outcomes
    # at multiple development manufacturers, even before combining predicates.
    supported = defaultdict(set)
    for r in rows:
        if r['strict']:
            for name in features[r['report_no']]:
                supported[name].add(maker(r))
    pools = {name:ids for name,ids in pools.items() if len(supported[name]) >= minimum_makers}
    base_size = sum(bool(x['flags']) for x in rows)
    selected = set()
    steps = []
    def assess(names):
        ids = set().union(*(pools[n] for n in names))
        m = measure(rows, ids)
        # Value distinct recalls first, charge one recall's value for every price reviews.
        return (price*m['notices']-len(ids), m['strict'], -len(names)), m
    while True:
        score, _ = assess(selected)
        best = None
        for name in sorted(pools):
            trial = selected ^ {name}
            value, stats = assess(trial)
            if stats['flags'] <= base_size and value > score:
                best = name,trial,stats
                score = value
        if best is None:
            return dict(rules=sorted(selected), steps=steps)
        name, selected, stats = best
        steps.append(dict(toggled=name, **stats))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['fit','evaluate'])
    p.add_argument('reports',type=Path,help='reports.jsonl emitted by watchlist_score')
    p.add_argument('selection',type=Path)
    a = p.parse_args()
    rows = [json.loads(line) for line in a.reports.read_text().splitlines()]
    dev = [r for r in rows if development(r)]
    history = read_json(REPORTS)
    ledger = read_json(LEDGER)
    if a.mode == 'fit':
        features = candidates(dev, [r for r in history if development(r)], ledger)
        winners = {str(price):climb(dev, features, price) for price in (10,30)}
        winners['transfer'] = climb(dev, features, 20, minimum_makers=3)
        a.selection.write_text(json.dumps(winners, indent=2)+'\n')
        return
    winners = json.loads(a.selection.read_text())
    dev_notices = {n for r in dev for n in r['strict']}
    # Exclude entire manufacturers sharing a strict target notice with training.
    test = [r for r in rows if not development(r)]
    shared = {maker(r) for r in test if r['strict'].keys() & dev_notices}
    novel = [r for r in test if maker(r) not in shared]
    f = candidates(rows, history, ledger)
    for group,pop in [('development',dev),('validation',novel),('all retrospective',rows)]:
        queues = {'original':{r['report_no'] for r in pop if r['flags']}}
        queues.update({k:{i for i,terms in f.items() if terms.intersection(w['rules'])} for k,w in winners.items()})
        print(json.dumps(dict(group=group,**{k:measure(pop,ids) for k,ids in queues.items()})))
    print('Overlapping manufacturers excluded from validation:', sorted(shared))


if __name__ == '__main__':
    main()
