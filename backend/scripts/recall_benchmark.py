"""Command line for the recall benchmark in `cpsc360.recall_benchmark`.

Run from backend:
  python -m scripts.recall_benchmark score --split dev --rules rules.json      # or --scores scores.csv
  python -m scripts.recall_benchmark review --split dev --rules rules.json     # AI reviews a sample of unrecalled flags
  python -m scripts.recall_benchmark check                                     # you review AI-reviewed reports blind
  python -m scripts.recall_benchmark reviewers                                 # how AI and human verdicts agree
  python -m scripts.recall_benchmark export --out reports.jsonl.gz --labels-as-of 2019-01-01
  python -m scripts.recall_benchmark ml-baseline --split dev --out dev-scores.csv

A scores file is CSV with columns report_no,score. Higher is more urgent; zero or missing is never flagged.
"""

import argparse
import csv
import gzip
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

from psycopg.rows import dict_row
from pydantic import TypeAdapter

from cpsc360 import db, lab_public, lab_replay, lab_rules, recall_benchmark as bench

REVIEW_MODEL = 'sonnet'
REVIEW_BATCH = 10
REVIEW_ATTEMPTS = 3  # the reviewer occasionally drops a report from a batch
NARRATIVE_CHARS = 2000
ESCALATE_FROM = 4
RUBRIC = """You triage consumer product incident reports from SaferProducts.gov as a CPSC compliance analyst.
CPSC receives thousands of these a year and can open recall investigations on only a small fraction, so most
reports that describe a real injury still do not warrant one. Rate each report from 1 to 5:

5: A clear defect or design flaw in an identified product (brand and model or equivalent) caused or nearly
   caused death, serious injury, fire, or harm to a child, under normal use, and other units likely share it.
4: A credible defect in an identified product with a serious hazard, but less certain to be systemic.
3: A possible product problem, but the cause is ambiguous, the hazard is minor, or the product is hard to identify.
2: Most likely misuse, wear, an installation or service problem, or a one-off failure.
1: No product safety issue: a quality, price or service complaint, or a hazard the product did not cause.

Judge only from the report text. Ignore anything you know about later recalls of this brand or product.
Give a one-sentence reason for each rating."""
VERDICT_SCHEMA = json.dumps({
    'type': 'object', 'required': ['ratings'],
    'properties': {'ratings': {'type': 'array', 'items': {
        'type': 'object', 'required': ['id', 'rating', 'reason'],
        'properties': {'id': {'type': 'string'}, 'rating': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                       'reason': {'type': 'string'}},
    }}},
})


def connect():
    conn = db.connect()
    conn.row_factory = dict_row
    return conn


def scores_for(conn, args) -> dict[str, float]:
    if args.rules:
        rules = TypeAdapter(list[lab_rules.Rule[lab_rules.CaseAction]]).validate_json(Path(args.rules).read_text())
        return bench.rule_scores(conn, rules, args.split)
    with open(args.scores, newline='', encoding='utf-8') as stream:
        return {row['report_no']: float(row['score']) for row in csv.DictReader(stream)}


def report_rows(conn, report_nos: list[str]) -> dict[str, dict]:
    return {row['report_no']: row for row in conn.execute('''
        SELECT report_no, publication_date, product_type, product_description, product_code, incident_description,
               severity, victim_age, manufacturer_name, brand, model, retailer
          FROM source.incident WHERE report_no = ANY(%s)
    ''', (report_nos,))}


def describe(row: dict) -> str:
    fields = [('Product', row['product_type'] or row['product_description']), ('Description', row['product_description']),
              ('Brand', row['brand']), ('Manufacturer', row['manufacturer_name']), ('Model', row['model']),
              ('Retailer', row['retailer']), ('Severity', row['severity']), ('Victim age', row['victim_age'])]
    lines = [f'{name}: {value}' for name, value in fields if value not in (None, '')]
    narrative = ' '.join((row['incident_description'] or '').split())[:NARRATIVE_CHARS]
    return '\n'.join([*lines, f'Narrative: {narrative}'])


def ai_review(rows: list[tuple[dict, bench.Sample]], model: str) -> list[bench.Review]:
    """Rate a batch with the rubric. Ratings of ESCALATE_FROM or more escalate, and the note keeps the rating."""
    prompt = '\n\n'.join(f'Report {row["report_no"]}\n{describe(row)}' for row, _ in rows)
    # An empty working directory and no settings, tools or MCP servers keep the reviewer to the rubric.
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run(
            ['claude', '-p', '--model', model, '--system-prompt', RUBRIC, '--tools', '', '--strict-mcp-config',
             '--setting-sources', '', '--disable-slash-commands', '--no-session-persistence',
             '--output-format', 'json', '--json-schema', VERDICT_SCHEMA],
            input=prompt, capture_output=True, text=True, cwd=cwd, check=True, timeout=300)
    output = json.loads(result.stdout)
    if output.get('is_error'):
        raise RuntimeError(output.get('result'))
    wanted = {row['report_no']: sample for row, sample in rows}
    # The CLI may use a small model for housekeeping, so name the reviewer after the model that wrote the most.
    resolved = max(output.get('modelUsage', {}).items(), key=lambda usage: usage[1]['outputTokens'], default=(model, None))[0]
    ratings = {item['id']: item for item in output['structured_output']['ratings'] if item['id'] in wanted}
    return [bench.Review(no, 'escalate' if item['rating'] >= ESCALATE_FROM else 'dismiss', f'ai:{resolved}', wanted[no],
                         f'{item["rating"]}/5 {item["reason"]}') for no, item in ratings.items()]


def escalation_rates(reviews: list[bench.Review]) -> dict[str, str]:
    """How often the AI escalated each kind of sampled report. Without a gap between recalled and random
    reports, its verdicts can't be trusted to mean "CPSC should have acted"."""
    ai = [review for review in reviews if review.reviewer.startswith('ai:')]
    return {kind: f'{sum(r.verdict == "escalate" for r in rows)}/{len(rows)}'
            for kind in ('recalled', 'random', 'flag') if (rows := [r for r in ai if r.sample == kind])}


def command_score(args):
    reviews = bench.read_reviews()
    with connect() as conn:
        result = bench.score(bench.truths(conn, reviews), scores_for(conn, args), args.split, args.budget)
    output = result.model_dump(mode='json', exclude=set() if args.catches else {'caught'})
    if result.precision.reviewed:
        output['precision']['ai_escalates'] = escalation_rates(reviews)
    print(json.dumps(output, indent=2))


def command_review(args):
    with connect() as conn:
        known = bench.truths(conn)
        sample = bench.review_sample(known, scores_for(conn, args), args.split, args.size, args.controls, args.seed, args.budget)
        rows = report_rows(conn, [no for no, _ in sample])
    print(f'Reviewing {len(sample)} reports with {args.model}: {dict(Counter(kind for _, kind in sample))}', file=sys.stderr)
    for start in range(0, len(sample), REVIEW_BATCH):
        batch = [(rows[no], kind) for no, kind in sample[start:start + REVIEW_BATCH]]
        reviews: list[bench.Review] = []
        for _ in range(REVIEW_ATTEMPTS):
            done = {review.report_no for review in reviews}
            if not (left := [item for item in batch if item[0]['report_no'] not in done]):
                break
            reviews += ai_review(left, args.model)
        bench.append_reviews(reviews)
        print(f'  {start + len(batch)}/{len(sample)}: {Counter(r.verdict for r in reviews)}', file=sys.stderr)


def command_check(args):
    reviews = bench.read_reviews()
    human = {review.report_no for review in reviews if review.reviewer == 'human'}
    ai = {review.report_no: review for review in reviews if review.reviewer.startswith('ai:')}
    todo = sorted(set(ai) - human)[:args.n]
    with connect() as conn:
        rows = report_rows(conn, todo)
    print(f'{len(todo)} reports. Escalate if the product itself is a hazard worth investigating. e/d/s(kip)/q(uit)\n')
    agree = total = 0
    for position, report_no in enumerate(todo, 1):
        print(f'--- {position}/{len(todo)}  {report_no}\n{describe(rows[report_no])}\n')
        answer = ''
        while answer not in ('e', 'd', 's', 'q'):
            answer = input('escalate / dismiss / skip / quit? ').strip().lower()[:1]
        if answer == 'q':
            break
        if answer == 's':
            continue
        verdict: bench.Verdict = 'escalate' if answer == 'e' else 'dismiss'
        bench.append_reviews([bench.Review(report_no, verdict, 'human', 'check', '')])
        total += 1
        agree += verdict == ai[report_no].verdict
        print(f'AI said {ai[report_no].verdict}: {ai[report_no].note}\n')
    if total:
        print(f'You agreed with the AI on {agree} of {total}.')


def command_reviewers(_args):
    """How often the AI escalates each kind of sampled report, and how often you agree with it."""
    reviews = bench.read_reviews()
    human = {review.report_no: review.verdict for review in reviews if review.reviewer == 'human'}
    checked = [review for review in reviews if review.reviewer.startswith('ai:') and review.report_no in human]
    print(json.dumps({
        'ai_escalates': escalation_rates(reviews),
        'human_agrees': f'{sum(human[r.report_no] == r.verdict for r in checked)}/{len(checked)}',
        'human_escalates_ai_dismissed': sum(human[r.report_no] == 'escalate' and r.verdict == 'dismiss' for r in checked),
        'human_dismisses_ai_escalated': sum(human[r.report_no] == 'dismiss' and r.verdict == 'escalate' for r in checked),
    }, indent=2))


def split_of(day: date) -> str | None:
    return next((name for name, (first, last) in bench.SPLITS.items() if first <= day <= last), None)


def export_rows(conn, as_of: date | None):
    first, last = lab_replay.snapshot_bounds(conn)
    positive = bench.labels_as_of(as_of) if as_of else None
    for row in lab_public.load_rows(conn, first, last):
        record = {
            'report_no': row['report_no'], 'published': row['publication_date'].isoformat(),
            'split': split_of(row['publication_date']), 'product_type': row['product_type'],
            'product_description': row['product_description'], 'product_code': row['product_code'],
            'narrative': row['incident_description'], 'severity': row['severity'], 'victim_age': row['victim_age'],
            'manufacturer': row['manufacturer_name'], 'brand': row['brand'], 'model': row['model'],
            'retailer': row['retailer'], 'hazards': list(row['hazards']),
        }
        if positive is not None:
            record['recalled_as_of'] = row['report_no'] in positive
        yield record


def command_export(args):
    as_of = date.fromisoformat(args.labels_as_of) if args.labels_as_of else None
    with connect() as conn, gzip.open(args.out, 'wt', encoding='utf-8') as stream:
        count = sum(stream.write(json.dumps(record) + '\n') > 0 for record in export_rows(conn, as_of))
    print(f'Wrote {count} reports to {args.out}', file=sys.stderr)


def command_ml_baseline(args):
    """TF-IDF and logistic regression, trained on every report before the split with labels known at its start."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    first, last = bench.SPLITS[args.split]
    with connect() as conn:
        records = [r for r in export_rows(conn, first) if r['published'] <= last.isoformat()]

    def text(record):
        return ' '.join(filter(None, (record['product_type'], record['product_description'], record['brand'],
                                      record['manufacturer'], record['model'], record['severity'], record['narrative'])))

    train = [r for r in records if r['published'] < first.isoformat()]
    target = [r for r in records if r['published'] >= first.isoformat()]
    vectorizer = TfidfVectorizer(min_df=3, max_features=200_000, ngram_range=(1, 2), sublinear_tf=True)
    features = vectorizer.fit_transform(text(r) for r in train)
    model = LogisticRegression(max_iter=2000, class_weight='balanced', C=args.c)
    model.fit(features, [r['recalled_as_of'] for r in train])
    probabilities = model.predict_proba(vectorizer.transform(text(r) for r in target))[:, 1]
    with open(args.out, 'w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['report_no', 'score'])
        writer.writerows((r['report_no'], f'{p:.6f}') for r, p in zip(target, probabilities, strict=True))
    print(f'Trained on {len(train)} reports ({sum(r["recalled_as_of"] for r in train)} recalled), scored {len(target)}',
          file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(required=True)

    def ranked(name, handler):
        command = commands.add_parser(name)
        command.add_argument('--split', choices=list(bench.SPLITS), required=True)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument('--rules')
        source.add_argument('--scores')
        command.add_argument('--budget', type=int, default=bench.BUDGET)
        command.set_defaults(handler=handler)
        return command

    ranked('score', command_score).add_argument('--catches', action='store_true')
    review = ranked('review', command_review)
    review.add_argument('--size', type=int, default=40)
    review.add_argument('--controls', type=int, default=10)
    review.add_argument('--seed', type=int, default=0)
    review.add_argument('--model', default=REVIEW_MODEL)
    check = commands.add_parser('check')
    check.add_argument('--n', type=int, default=20)
    check.set_defaults(handler=command_check)
    commands.add_parser('reviewers').set_defaults(handler=command_reviewers)
    export = commands.add_parser('export')
    export.add_argument('--out', required=True)
    export.add_argument('--labels-as-of')
    export.set_defaults(handler=command_export)
    baseline = commands.add_parser('ml-baseline')
    baseline.add_argument('--split', choices=['dev', 'test'], required=True)
    baseline.add_argument('--out', required=True)
    baseline.add_argument('--c', type=float, default=1.0)
    baseline.set_defaults(handler=command_ml_baseline)
    args = parser.parse_args()
    args.handler(args)


if __name__ == '__main__':
    main()
