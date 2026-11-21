"""Acquisition age and corroboration in public incident reports, developed on 2020–25.

The three two-year development cohorts respectively had 20, 17 and 31 distinct
subsequent strict recalls among reports published within 180 days of purchase,
versus 1, 4 and 5 for products owned over four years. Narratives mentioning
independent reviews of the same problem preceded 1, 2 and 4 distinct actions
among only 60, 71 and 114 reports. Historical labels have incomplete retrieval.
Never use manufacturer responses, later reports or adjudications as predictors.
"""
import re
from datetime import date

REVIEWS = re.compile(
    r'(?:reviews?|searched|searching).{0,65}(?:similar|same)|'
    r'(?:similar|same).{0,65}reviews?|'
    r'(?:many|several|other|multiple) (?:reports|injuries|incidents|reviews|complaints)'
)
SALES = re.compile(r'stop(?:ped)? selling|removed from (?:sale|store)|taken off the market')
STANDARD = re.compile(r'\b(?:16 cfr|astm|mandatory standard|child[ -]resistan\w*|childproof)\b')
MOVEMENT = re.compile(r'tipped over|choked|came off|broke off|fell off|detached|collapsed|broke apart|came apart')
TESTED = re.compile(r'fire (?:investigator|marshal|inspector)|(?:engineer|electrician|fire department).{0,100}(?:found|determined|traced|caused)')
OLD_ACTION = re.compile(r'(?:already|been|was|recently) recalled|in the recall|part of (?:a|the) recall')


def evidence(row):
    """Return an integer ranking score. Higher values indicate more priority."""
    story = ' '.join((row.get('incident_description') or '').lower().split())
    score = 0
    if row.get('purchase_date') and row.get('publication_date'):
        age = (date.fromisoformat(str(row['publication_date'])[:10]) -
               date.fromisoformat(str(row['purchase_date'])[:10])).days
        if 0 <= age <= 180:
            score += 3
        elif 180 < age <= 365:
            score += 2
        elif age > 4 * 365:
            score -= 2
    if REVIEWS.search(story):
        score += 4
    if SALES.search(story) or STANDARD.search(story):
        score += 3
    if TESTED.search(story):
        score += 2
    if MOVEMENT.search(story):
        score += 2
    if OLD_ACTION.search(story):
        score -= 4
    return score
