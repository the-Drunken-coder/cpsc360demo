"""Fit a report-level recall ranker using product and incident concepts, not product identities."""
import math
import re
from collections import defaultdict
from datetime import date
from itertools import groupby

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

from cpsc360.derive import manufacturer_key, product_model_key


# Only these common concepts, structured product types, and counts enter the classifier.
# Maker and model strings are used exclusively to count earlier reports for the same item.
CONCEPTS = {
    'fire': r'caught (?:on )?fire|burst into flames|burned down|went up in flames|ignit\w*',
    'hot': r'overheat\w*|smok\w*|melt\w*|scorch\w*|burn\w*',
    'electrical': r'spark\w*|short circuit|shock\w*|arc(?:ed|ing)|cord|wiring',
    'mechanical': r'snapp?ed|broke|broken|fractur\w*|crack\w*|bent',
    'detachment': r'(?:fell|came|flew|popped|pulled) (?:off|apart|out)|detach\w*|separat\w*|dislodg\w*',
    'fall': r'(?:fell|fall|falling|collaps\w*|tip\w* over|toppl\w*)',
    'entrapment': r'entrapp?\w*|trapped|wedged|pinched|strangl\w*|suffocat\w*|drown\w*',
    'oral': r'chok\w*|swallow\w*|ingest\w*|mouth',
    'cut': r'cut|lacerat\w*|stitches|bled|bleeding|amputat\w*',
    'automatic': r'by itself|on its own|unattended|accidental\w*|without warning|unexpected\w*',
    'failure': r'fail\w*|defect\w*|malfunction\w*',
    'repair': r'repair\w*|warranty|replace\w*|service technician',
    'exclusions': r'not (?:included|part|covered)|outside (?:the )?(?:range|recall)|different model|similar (?:recall|model)',
    'recall': r'recall\w*|warning notice',
    'remedy': r'recall (?:repair|service|replacement)|(?:was|been|already) recalled',
    'regulatory': r'standards?|regulat\w*|illegal|banned|non.?compliant|violation',
    'listing': r'listing|marketplace|seller|online reviews|customer reviews|website',
    'children': r'child\w*|infant|baby|babies|toddler|month.old',
    'charging': r'batter\w*|charg(?:e|er|ed|ing)|lithium',
    'control': r'switch|button|knob|indicator|controller|pedal',
    'structure': r'bracket|bolt|screw|support|hinge|handle|frame|fork|joint',
    'product_design': r'opening|dimension|gap|diameter|slot|strap|guard|lock|anchor|harness',
    'particles': r'plastic|fragments?|shards?|pieces?|metal',
    'fluid': r'leak\w*|steam|pressure|spray\w*|hot water',
    'illness': r'rash|illness|nausea|headache|vomit\w*|spoiled|spoilage',
    'severe': r'hospital\w*|surgery|emergency|ambulance|death|died|unconscious',
    'documented': r'photo\w*|picture\w*|video|attached|laboratory|tested',
    'professional': r'fire department|fire marshal|investigat\w*|police|firefighter\w*',
}
PATTERNS = {key: re.compile(r'\b(?:'+p+r')\b') for key,p in CONCEPTS.items()}
TYPE_STOP = set('or and for other elsewhere classified unspecified specified not products equipment related powered'.split())


def features(rows):
    recent = defaultdict(list)
    out = {}
    ordered = sorted(rows, key=lambda r:str(r['publication_date']))
    for datestr, batch in groupby(ordered, key=lambda r:str(r['publication_date'])[:10]):
        day = date.fromisoformat(datestr).toordinal()
        updates = []
        for row in batch:
            rid = row['report_no']
            story = ' '.join((row['incident_description'] or '').lower().split())
            model = product_model_key(row['model'],row['brand'],row['manufacturer_name'])
            key = manufacturer_key(row['manufacturer_name']), model
            tags = [t for t,p in PATTERNS.items() if p.search(story)]
            category = set(re.findall('[a-z]{3,}', (row['product_type'] or '').lower())) - TYPE_STOP
            v = {f'inc/{t}': 1 for t in tags}
            v.update({f'type/{w}': 1 for w in category})
            v.update({f'pair/{w}/{t}': 1 for t in tags for w in category})
            v['model supplied'] = bool(model)
            v['model in text'] = bool(re.search(r'\bmodel\s*(?:number|#)?\s*[:#]?\s*(?=[a-z0-9-]*\d)[a-z0-9-]{3,}',story))
            v['narrative length'] = min(4, math.log1p(len(story))/2)
            if model:
                for horizon in (30,180):
                    previous = sum(1 for d in recent[key] if d >= day-horizon)
                    if previous:
                        v[f'previous/{horizon}'] = min(3, math.log1p(previous))
                updates.append(key)
            out[rid] = v
        for key in updates:
            recent[key].append(day)
    return out


def fit_predict(train_rows, positive_report_ids, rows):
    """Return scores relative to other reports; balanced fitting does not calibrate probabilities."""
    train = features(train_rows)
    test = features(rows)
    ids = set(positive_report_ids)
    vectorizer = DictVectorizer()
    matrix = vectorizer.fit_transform(train.values())
    model = LogisticRegression(class_weight='balanced', C=0.08, max_iter=400, solver='lbfgs',random_state=0)
    model.fit(matrix, [rid in ids for rid in train])
    return dict(zip(test,model.decision_function(vectorizer.transform(test.values())),strict=True))
