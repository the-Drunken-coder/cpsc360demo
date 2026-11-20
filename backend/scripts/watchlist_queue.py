"""Budgeted weekly public-report queue. Uses publication-time report fields only."""
import hashlib
import re
from collections import defaultdict
from datetime import date, timedelta

from cpsc360.derive import manufacturer_key, product_model_key
from scripts.watchlist_family_signals import signals
from scripts.watchlist_prior_patterns import prior_patterns


def _matches(r, include_expansion):
    story = ' '.join((r['incident_description'] or '').lower().split())
    context = ' '.join((r['product_type'] or '', r['product_description'] or '', story)).lower()
    model = product_model_key(r['model'],r['brand'],r['manufacturer_name']) or re.search(
        r'\bmodel\s*(?:number|no\.?|#)?\s*[:#]?\s*(?=[a-z0-9-]*\d)[a-z0-9-]{4,}',story)
    old = signals(r)
    patterns = {name for name in old if model}
    if include_expansion:
        patterns.update(prior_patterns(r))
        for name, product, failure in COMPONENTS:
            if product.search(context) and failure.search(story):
                patterns.add(name)
    if not patterns:
        return None
    score = 2 * bool(model) + min(2,len(patterns)) + bool(old and model)
    if re.search(r'\b(?:similar|different|another|other model)\b.{0,50}recall', story):
        score += 1
    if re.search(r'(?:my|this) (?:unit|product|model) (?:is|was|has been) (?:already )?recalled|after the recall repair',story):
        score -= 3
    return score, frozenset(patterns)


# Reported component + observed failure. No manufacturer or model allowlist.
COMPONENTS = [(name, re.compile(product), re.compile(failure)) for name, product, failure in (
    ('contaminated dispensed food', r'ice maker|ice bucket|refrigerator|food processor',
     r'(plastic|metal|shard|fragment).{0,65}(ice|food|drink)|(ice|food|drink).{0,65}(shard|fragment|pieces of plastic)'),
    ('failed mobile control', r'tractor|snowmobile|scooter|bicycle|bike|utility vehicle',
     r'(brake|braking|fork|steerer|brake pedal|bellcrank).{0,45}(fail|broke|shear|snapp|fractur)'),
    ('unintended heat control', r'stove|range|cooktop|burner',
     r'(knob|control|burner).{0,75}(brush|lean|bump|barely touch|accidental|too eas|turns itself on)|(brush|lean|bump|barely touch).{0,60}(knob|burner)'),
    ('child exposed to small part',r'infant|month.old|toddler|baby|stroller toy',
     r'(head|wheel|bead|bell|piece|button).{0,45}(came off|fell off|detach|broke off)|chok(?:ed|ing)|not breathing'),
    ('broken support',r'chair|stool|furniture strap|anti.tip|dresser|wall.mount|wall decor',
     r'(leg|strap|anchor|mount|bracket).{0,50}(broke|snapped|came loose|pulled out)|fell (?:off|from) the wall'),
    ('steam leak at connection',r'steamer|steam cleaner|pressure cooker',
     r'(steam|hot water).{0,70}(escape|leak|spray).{0,65}(trigger|handle|housing|joint|connection)'),
    ('released exercise load',r'dumb[b]?ell|adjustable weight',
     r'(weight|plate).{0,35}(fell|detach|slipped|dropped)'),
)]


def schedule(rows, *, expanded=True, cooldown=30, adaptive=True, priority=0, rarity=1):
    """On Sundays, spend review slots earned by incumbent flags, carrying unused slots forward."""
    weeks = defaultdict(list)
    for r in rows:
        day = date.fromisoformat(str(r['publication_date'])[:10])
        weeks[day + timedelta(days=6-day.weekday())].append(r)
    last = {}
    seen = defaultdict(list)
    selected = {}
    balance = 0
    for sunday, batch in sorted(weeks.items()):
        old_queue = {r['report_no'] for r in batch if product_model_key(r['model'],r['brand'],r['manufacturer_name']) and signals(r)}
        balance = (balance + 45 * len(old_queue)) if adaptive else min(134,balance + len(batch))
        ranked = []
        current = []
        for r in batch:
            evidence = _matches(r,expanded)
            if evidence is None:
                continue
            score, names = evidence
            # Prefer failure patterns that generate fewer reports across makers.
            frequency = min(sum((sunday - when).days <= 180 for when in seen[n]) for n in names)
            score -= rarity * frequency.bit_length()
            current.extend(names)
            if r['report_no'] in old_queue:
                score += priority
            rid = r['report_no']
            keys = [(manufacturer_key(r['manufacturer_name']),n) for n in sorted(names)]
            ranked.append((-score,hashlib.sha256(rid.encode()).digest(),rid,keys))
        for n in current:
            seen[n].append(sunday)
        for _,__,rid,keys in sorted(ranked):
            if balance < 45:
                break
            if all(k in last and (sunday-last[k]).days < cooldown for k in keys):
                continue
            selected[rid] = sunday
            last.update(dict.fromkeys(keys,sunday))
            balance -= 45
    return selected


def review_queue(rows):
    return set(schedule(rows))
