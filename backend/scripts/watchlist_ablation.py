"""Diagnostic replay: remove individual conditions from the original specific-report rule."""
import argparse
import json
from pathlib import Path

from cpsc360.derive import product_model_key
from scripts.watchlist_climb import development, measure
from scripts.watchlist_family_signals import signals
from scripts.watchlist_rules import FAILURE, ID_IN_TEXT, MODEL_IN_TEXT, NEAR, identifier
from scripts.watchlist_score import REPORTS, read_json


def compare(rows):
    source = {x['report_no']:x for x in read_json(REPORTS)}
    queues = {k:set() for k in ('specific', 'drop serial', 'drop injury', 'drop both', 'product and failure only')}
    for r in rows:
        rid = r['report_no']
        story = ' '.join((r['incident_description'] or '').lower().replace('’', "'").split())
        text = story + ' ' + (r['product_description'] or '').lower()
        model = product_model_key(r['model'], r['brand'],r['manufacturer_name']) or any(
            identifier(m[1]) for m in MODEL_IN_TEXT.finditer(text))
        serial = identifier(r['serial_number']) or any(identifier(m[1]) for m in ID_IN_TEXT.finditer(text))
        injury = source[rid]['is_injury'] or NEAR.search(story)
        if signals(r):
            queues['product and failure only'].add(rid)
        if not (model and FAILURE.search(story)):
            continue
        queues['drop both'].add(rid)
        if serial:
            queues['drop injury'].add(rid)
        if injury:
            queues['drop serial'].add(rid)
        if serial and injury:
            queues['specific'].add(rid)
    assert queues['specific'] == {x['report_no'] for x in rows if 'specific' in x['flags']}
    return {k:measure(rows,v) for k,v in queues.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path)
    rows = [json.loads(s) for s in parser.parse_args().reports.read_text().splitlines()]
    for label,group in [('all',rows),('validation',[r for r in rows if not development(r)])]:
        print(json.dumps({'group':label,**compare(group)}))
