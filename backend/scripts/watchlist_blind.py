"""Compare learned and narrative evidence at the incumbent queue's review volume."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from itertools import product
from datetime import date, timedelta
from pathlib import Path

from scripts.watchlist_historical_check import load_cohort, reviewed_pairs, score_queue
from scripts.watchlist_queue_replay import incumbent
from scripts.watchlist_score import LEDGER, read_json
from scripts.watchlist_queue import protect_first_schedule, schedule
from cpsc360.derive import manufacturer_key, product_model_key
from scripts.watchlist_learned import fit_predict
from scripts.watchlist_evidence import evidence

LOCK = LEDGER.with_name('watchlist-unseen-selection.json')


def sources(modern):
    """Only the specified development periods can supply training labels."""
    rows = {}
    labels = {}
    for year, files in [(2020,['watchlist-2020-queue-review.csv']),
                        (2022,['watchlist-historical-queue-review.csv','watchlist-historical-reachable.csv'])]:
        rows[year] = load_cohort(year)
        labels[year] = reviewed_pairs([LEDGER.with_name(f) for f in files])
    rows[2024] = [json.loads(line) for line in modern.read_text().splitlines()]
    if not all('2024-01-01' <= r['publication_date'] <= '2025-11-04' for r in rows[2024]):
        raise ValueError('Expected the original 2024–25 cohort')
    labels[2024] = [(r['report_no'],n) for r in rows[2024] for n in r['strict']]
    return rows, labels


def prepare(rows, learned):
    # Percentiles and recurrence counts use only reports available by the weekly meeting.
    weeks = defaultdict(list)
    for r in rows:
        day = date.fromisoformat(str(r['publication_date'])[:10])
        weeks[day+timedelta(days=6-day.weekday())].append(r)
    prior = defaultdict(list)
    history = Counter()
    count = 0
    result = []
    for day, batch in sorted(weeks.items()):
        current = []
        for r in batch:
            rid = r['report_no']
            maker = manufacturer_key(r['manufacturer_name'])
            model = product_model_key(r['model'],r['brand'],r['manufacturer_name'])
            key = maker, model
            prior_recent = sum((day-d).days<=120 for d in prior[key]) if model else 0
            current.append((rid,key,learned[rid],float(evidence(r)),int(incumbent(r)),prior_recent))
        for rid,key,score,ev,old,repeats in current:
            history[round(score,4)] += 1
            if key[1]:
                prior[key].append(day)
        count += len(batch)
        cumulative = 0
        percentiles = {}
        for value,n in sorted(history.items()):
            cumulative += n
            percentiles[value] = cumulative/count
        result.append((day,[(rid,key,percentiles[round(sc,4)],ev,old,repeats) for rid,key,sc,ev,old,repeats in current]))
    return result


def choose(weeks, weights):
    w_ml,w_evidence,w_repeat,w_old,lookback = weights
    backlog,last,selected = [],{},{}
    for day,batch in weeks:
        slots = sum(x[4] for x in batch)
        backlog = [(d,x) for d,x in backlog if (day-d).days<=lookback]
        backlog.extend((day,x) for x in batch)
        ranked = []
        for d,(rid,key,ml,ev,old,repeats) in backlog:
            if rid in selected:
                continue
            if key[1] and key in last and (day-last[key]).days<120:
                continue
            strength = w_ml*ml**8 + w_evidence*ev + w_repeat*min(2,repeats) + w_old*old
            ranked.append((-strength,hashlib.sha256(rid.encode()).digest(),rid,key))
        for _,__,rid,key in sorted(ranked):
            if not slots:
                break
            if key[1] and key in last and (day-last[key]).days<120:
                continue
            selected[rid] = day
            last[key] = day
            slots -= 1
    return selected


def train_scores(rows, labels, test):
    train = [r for y in rows for r in rows[y]]
    positive = {rid for pairs in labels.values() for rid,_ in pairs}
    return fit_predict(train, positive, test)


def comparison(rows, selected, notices, labels):
    pub = {r['report_no']:date.fromisoformat(str(r['publication_date'])[:10]) for r in rows}
    old = {r['report_no']:pub[r['report_no']] for r in rows if incumbent(r)}
    return {k: score_queue(d,pub,notices,labels) for k,d in [('old',old),('challenger',selected)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['fit','blind'])
    p.add_argument('--output',type=Path, required=True)
    p.add_argument('--modern', type=Path, required=True, help='2024–25 reports.jsonl from watchlist_score')
    a = p.parse_args()
    rows,labels = sources(a.modern)
    notices = {n['RecallNumber']:date.fromisoformat(n['RecallDate'][:10]) for n in read_json(LEDGER)}
    if a.mode=='fit':
        prepared = {}
        for y in rows:
            pred = train_scores({t:v for t,v in rows.items() if t!=y},{t:v for t,v in labels.items() if t!=y},rows[y])
            prepared[y] = prepare(rows[y],pred)
        pubs = {y:{r['report_no']:date.fromisoformat(str(r['publication_date'])[:10]) for r in cohort} for y,cohort in rows.items()}
        old_hits = {y:comparison(rows[y],{},notices,labels[y])['old']['distinct_notices'] for y in rows}
        best = None
        trials = []
        for weights in product((0,4), (0,1), (0,1,3), (0,2,5,8,12,16), (7,28)):
            if not any(weights[:4]):
                continue
            gain = []
            for y,data in prepared.items():
                sel = choose(data,weights)
                result = score_queue(sel, pubs[y], notices, labels[y])
                gain.append(result['distinct_notices']-old_hits[y])
            # The incumbent mechanism list was authored from 2024-25 cases.
            # Protect at least 75% of its in-sample notices, then favor transfer
            # in BOTH earlier development blocks over maximizing in-sample yield.
            floor_met = old_hits[2024]+gain[2] >= .75*old_hits[2024]
            rank = (floor_met, min(gain[:2]), sum(gain[:2]), gain[2],-sum(bool(i) for i in weights[:4]))
            trials.append(dict(weights=weights,gain=gain))
            if best is None or rank>best[0]:
                best = rank,weights,gain
        a.output.write_text(json.dumps(dict(weights=best[1],development_gain=best[2],trials=len(trials)),indent=2)+'\n')
        return
    weights = json.loads(LOCK.read_text())['weights']
    for y in (2012,2016,2018,2014):
        test = load_cohort(y)
        selected = choose(prepare(test,train_scores(rows,labels,test)),weights)
        old = {r['report_no']:date.fromisoformat(str(r['publication_date'])[:10]) for r in test if incumbent(r)}
        a.output.mkdir(exist_ok=True,parents=True)
        queues = {'old':old,'weekly':schedule(test),'challenger':selected}
        if y == 2012:
            queues['protect_first'] = protect_first_schedule(test)
        (a.output/f'{y}.json').write_text(json.dumps(queues,default=str,sort_keys=True))


if __name__ == '__main__':
    main()
