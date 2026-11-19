"""Arrival-time detectors frozen before scoring. See docs/watchlist-score.md."""
from datetime import date
from itertools import groupby
import re

from cpsc360.derive import model_key
from scripts.watchlist_mechanisms import known_mechanism

START = date(2024, 1, 1)
END = date(2025, 11, 4)
FAILURES = (
    r'explod\w*|explosion|burst|blew (?:up|off|apart)', r'eject\w*|shot out|flew (?:out|off)',
    r'separat\w*|detach\w*|came (?:off|apart)|fell (?:out|off)',
    r'shatter\w*|fractur\w*|snapp?ed|crack(?:ed|ing)|broke(?:n)?',
    r'melt(?:ed|ing)?|overheat(?:ed|ing)?|caught (?:on )?fire|ignit(?:ed|ion)',
    r'short[ -]?circuit\w*|arc(?:ed|ing)|spark(?:ed|ing)|electric shock',
    r"(?:would not|wouldn't|won't|could not|couldn't|failed to) (?:turn|shut|switch) off",
    r'(?:turned|switched) on by itself|activat\w* by itself',
)
FAILURE = re.compile(r'\b(?:' + '|'.join(FAILURES) + r')\b')
NEAR = re.compile(r'\b(?:almost|nearly|narrowly|barely missed|just missed|just in time)\b.{0,55}'
                  r'\b(?:hit|struck|burn\w*|injur\w*|hurt|cut|fell|fall\w*|crush\w*|chok\w*|escap\w*|miss\w*|kill\w*)\b')
REMEDY = re.compile(
    r'\b(?:after (?:the |a |this |that )?recall (?:repair|fix|service|replacement)|'
    r'(?:had|got) (?:the |a |my )?recall (?:repair|work|fix) (?:done|completed|performed)|'
    r'recall (?:repair|fix|work) (?:was |had been )?(?:done|completed|performed)|'
    r'(?:repaired|replaced|remedied) (?:under|per|as part of|by|for) (?:the |a |this )?recall|'
    r'(?:was |previously |been )recalled and (?:repaired|replaced)|'
    r'(?:received|installed|fitted) .{0,45}replacement.{0,45}(?:under|for|from) (?:the |a )?recall)\b')
REPEAT = re.compile(r'\b(?:again|recur\w*|re-occur\w*|still|continues? to|same (?:thing|problem|issue|failure|defect)|'
                    r'(?:issue|problem|failure) (?:returned|persist\w*)|second time)\b')
ID_IN_TEXT = re.compile(r'\b(?:serial|lot|batch|s/n)\s*(?:number|no\.?|code|#)?\s*[:#=]?\s*([a-z0-9][a-z0-9/-]{2,})')
MODEL_IN_TEXT = re.compile(r'\bmodel\s*(?:number|no\.?|#)?\s*[:#=]?\s*([a-z0-9][a-z0-9/-]{2,})')


def identifier(value):
    if not value or re.search(r'unknown|redacted|not (?:sure|available)|see (?:photo|label)', value, re.I):
        return False
    key = model_key(value)
    return bool(key and len(key) >= 3 and re.search('[0-9]', key) and len(set(key)) > 1)


def flag_reports(rows):
    """Same-day publications have no known order. History enters after the whole day."""
    history = {}
    flags = {}
    for day, group in groupby(sorted(rows, key=lambda r: r['publication_date']), key=lambda r: r['publication_date']):
        admitted = set()
        for r in group:
            key = (r['manufacturer_key'], r['model_key'])
            if all(key) and r['severity'] == 'Injury, Hospital Admission':
                admitted.add(key)
            if not START <= day <= END:
                continue
            active = set()
            if key in history and (day - history[key]).days <= 90:
                active.add('admission')
            if known_mechanism(r):
                active.add('mechanism')
            body = ' '.join((r['incident_description'] or '').lower().replace('’', "'").split())
            text = ' '.join([body, (r['product_description'] or '').lower()])
            has_model = r['model_key'] or any(identifier(m[1]) for m in MODEL_IN_TEXT.finditer(text))
            has_serial = identifier(r['serial_number']) or any(identifier(m[1]) for m in ID_IN_TEXT.finditer(text))
            if has_model and has_serial and FAILURE.search(body) and (r['is_injury'] or NEAR.search(body)):
                active.add('specific')
            if REMEDY.search(body) and REPEAT.search(body) and FAILURE.search(body):
                active.add('repair')
            flags[r['report_no']] = active
        history.update(dict.fromkeys(admitted, day))
    return flags
