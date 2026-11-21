"""Score any report ranker, rules or a trained model, on catching CPSC recalls early under a review budget.

A system gives reports a score, and a report with none abstains. Each publication week, the top
`budget` scored reports are flagged when the week closes. A recall wave is caught when a flagged report
is linked to one of its notices before CPSC acted (the strict recall ledger). The main number
is caught waves at a fixed budget, next to what random flags at the same weekly rate catch.

A report with no recall is unknown, not wrong: CPSC misses hazards, and recent reports may be
recalled later. Precision against recalls is only a floor. Reviews in `benchmark-reviews.csv`
judge whether a sample of unrecalled flags should have been escalated, which gives an
estimated precision and shows how often recall labels miss real hazards.
"""

import csv
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from math import isfinite, sqrt
from pathlib import Path
from statistics import median
from typing import Literal, NamedTuple

from pydantic import BaseModel

from . import lab_public, lab_replay, lab_rules

Split = Literal['train', 'dev', 'test']
SPLITS: dict[Split, tuple[date, date]] = {
    'train': (date(2011, 6, 1), date(2018, 12, 31)),
    'dev': (date(2019, 1, 1), date(2022, 6, 30)),
    'test': (date(2022, 7, 1), date(2025, 10, 31)),
}
BUDGET = 3
LEAD_CAP_DAYS = 365
# Recalls often come a year or more after the first report, so unrecalled recent reports stay open.
CENSOR_DAYS = 548
REVIEWS_PATH = Path(__file__).with_name('benchmark-reviews.csv')

Verdict = Literal['escalate', 'dismiss']
# Why a report was sent to review: a flag with no recall, a recalled flag or a random report as hidden controls,
# or a human check of an AI verdict.
Sample = Literal['flag', 'recalled', 'random', 'check']
Label = Literal['recalled', 'missed_hazard', 'not_hazard', 'unknown']


class Review(NamedTuple):
    report_no: str
    verdict: Verdict
    reviewer: str  # "human" or "ai:<model>"
    sample: Sample
    note: str


class Truth(NamedTuple):
    published: date
    # (notice number, last day a flag still counts as early) for each recall that lists this report's model.
    links: tuple[tuple[str, date], ...]
    censored: bool
    verdict: Verdict | None

    @property
    def label(self) -> Label:
        if self.links:
            return 'recalled'
        return {'escalate': 'missed_hazard', 'dismiss': 'not_hazard', None: 'unknown'}[self.verdict]


def week_end(day: date) -> date:
    """Flags are decided when the publication week (Monday to Sunday) closes."""
    return day + timedelta(days=6 - day.weekday())


def read_reviews(path: Path = REVIEWS_PATH) -> list[Review]:
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        return [Review(row['report_no'], row['verdict'], row['reviewer'], row['sample'], row['note'])
                for row in csv.DictReader(stream)]


def append_reviews(reviews: Iterable[Review], path: Path = REVIEWS_PATH) -> None:
    new = not path.exists()
    with path.open('a', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        if new:
            writer.writerow(Review._fields)
        writer.writerows(reviews)


def resolve(reviews: Iterable[Review]) -> dict[str, Verdict]:
    """One verdict per report. A human verdict overrides an AI one, and the latest wins within each kind."""
    verdicts: dict[str, tuple[bool, Verdict]] = {}
    for review in reviews:
        human = review.reviewer == 'human'
        if human or not verdicts.get(review.report_no, (False, 'dismiss'))[0]:
            verdicts[review.report_no] = (human, review.verdict)
    return {report_no: verdict for report_no, (_, verdict) in verdicts.items()}


def truths(conn, reviews: Iterable[Review] | None = None) -> dict[str, Truth]:
    """What the benchmark knows about every report in the snapshot."""
    ledger = lab_replay.ledger()
    links: dict[str, list[tuple[str, date]]] = defaultdict(list)
    for notice_no, covered in ledger.reports.items():
        for report_no, flag_by in covered:
            links[report_no].append((notice_no, flag_by))
    verdicts = resolve(read_reviews() if reviews is None else reviews)
    censor_from = ledger.snapshot_last - timedelta(days=CENSOR_DAYS)
    return {row['report_no']: Truth(row['publication_date'], tuple(sorted(links.get(row['report_no'], ()))),
                                    row['publication_date'] > censor_from, verdicts.get(row['report_no']))
            for row in conn.execute('SELECT report_no, publication_date FROM source.incident')}


def labels_as_of(day: date) -> set[str]:
    """Reports linked to a recall notice published before `day`: the only labels a model trained that day could see.

    Training on today's labels would leak: a model would learn that a model number is risky
    from a recall announced years after the reports it is scored on. The date is the notice's,
    not an earlier warning's, since the notice is what lists the exact models.
    """
    ledger = lab_replay.ledger()
    return {report_no for notice_no, covered in ledger.reports.items() if ledger.notices[notice_no].announced < day
            for report_no, _ in covered}


def in_split(known: Mapping[str, Truth], split: Split) -> dict[str, Truth]:
    first, last = SPLITS[split]
    return {report_no: truth for report_no, truth in known.items() if first <= truth.published <= last}


def flag(reports: Mapping[str, Truth], scores: Mapping[str, float], budget: int) -> dict[str, date]:
    """The top `budget` scored reports of each publication week, flagged on the week's last day.

    A report with no score abstains. Equal scores are broken by report number so a run is reproducible.
    """
    weeks: dict[date, list[tuple[float, str]]] = defaultdict(list)
    for report_no, truth in reports.items():
        if (value := scores.get(report_no)) is not None and isfinite(value):
            weeks[week_end(truth.published)].append((-value, report_no))
    return {report_no: end for end, ranked in weeks.items() for _, report_no in sorted(ranked)[:budget]}


class Catch(BaseModel):
    wave: str
    notice_no: str
    title: str
    report_no: str
    lead_days: int


class Precision(BaseModel):
    floor: float | None  # recalled flags / flags that are not too recent to judge
    recalled: int  # flags made before a recall of the report's model, the only ones that count as hits
    unrecalled: int  # flags on reports no recall covers
    censored: int  # unrecalled flags too recent for "no recall yet" to mean much
    reviewed: int
    escalate: int
    estimate: float | None  # the floor, plus the reviewed escalate rate applied to unrecalled flags old enough to judge
    low: float | None
    high: float | None


class Score(BaseModel):
    split: Split
    budget: int
    weeks: float
    flags: int
    flags_per_week: float
    reachable_waves: int
    caught_waves: int
    random_waves: float  # expected caught waves for random flags at the same count each week
    lift: float | None
    median_lead_days: int | None  # each wave's best lead, capped at LEAD_CAP_DAYS
    precision: Precision
    caught: list[Catch]


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    centre = (hits + z * z / 2) / (total + z * z)
    spread = z * sqrt(hits * (total - hits) / total + z * z / 4) / (total + z * z)
    return centre - spread, centre + spread


def score(known: Mapping[str, Truth], scores: Mapping[str, float], split: Split, budget: int = BUDGET) -> Score:
    reports = in_split(known, split)
    flagged = flag(reports, scores, budget)
    ledger = lab_replay.ledger()

    # Every (report, notice) pair a flag could have caught early, grouped by wave and week.
    eligible: dict[str, dict[date, set[str]]] = defaultdict(lambda: defaultdict(set))
    best: dict[str, Catch] = {}
    for report_no, truth in reports.items():
        end = week_end(truth.published)
        for notice_no, flag_by in truth.links:
            if end > flag_by:
                continue
            notice = ledger.notices[notice_no]
            eligible[notice.wave][end].add(report_no)
            if report_no in flagged:
                lead = min((notice.announced - end).days, LEAD_CAP_DAYS)
                if notice.wave not in best or lead > best[notice.wave].lead_days:
                    best[notice.wave] = Catch(wave=notice.wave, notice_no=notice_no, title=notice.title,
                                              report_no=report_no, lead_days=lead)

    week_sizes: dict[date, int] = defaultdict(int)
    week_flags: dict[date, int] = defaultdict(int)
    for truth in reports.values():
        week_sizes[week_end(truth.published)] += 1
    for end in flagged.values():
        week_flags[end] += 1

    def missed_by_random(end: date, hits: int) -> float:
        size, picks = week_sizes[end], week_flags[end]
        chance = 1.0
        for pick in range(picks):
            chance *= max(size - hits - pick, 0) / (size - pick)
        return chance

    random_waves = 0.0
    for weeks in eligible.values():
        missed = 1.0
        for end, covered in weeks.items():
            missed *= missed_by_random(end, len(covered))
        random_waves += 1 - missed

    leads = sorted(catch.lead_days for catch in best.values())
    first, last = SPLITS[split]
    span = ((last - first).days + 1) / 7
    return Score(
        split=split, budget=budget, weeks=round(span, 1), flags=len(flagged), flags_per_week=round(len(flagged) / span, 2),
        reachable_waves=len(eligible), caught_waves=len(best), random_waves=round(random_waves, 2),
        lift=round(len(best) / random_waves, 2) if random_waves else None,
        median_lead_days=round(median(leads)) if leads else None,
        precision=precision([(reports[report_no], end) for report_no, end in flagged.items()]),
        caught=sorted(best.values(), key=lambda catch: (-catch.lead_days, catch.wave)),
    )


def precision(flags: list[tuple[Truth, date]]) -> Precision:
    """Precision of (report, flag day) pairs. A flag after the recall deadline is a miss, like a wrong one."""
    recalled = sum(any(end <= flag_by for _, flag_by in truth.links) for truth, end in flags)
    unrecalled = [truth for truth, _ in flags if not truth.links]
    censored = sum(truth.censored for truth in unrecalled)
    judged = len(flags) - censored
    # Only reviews of flags old enough to judge count, the same cohort as the floor.
    reviewed = [truth for truth in unrecalled if truth.verdict is not None and not truth.censored]
    escalate = sum(truth.verdict == 'escalate' for truth in reviewed)
    estimate = low = high = None
    if reviewed and judged:
        rate = escalate / len(reviewed)
        low_rate, high_rate = wilson(escalate, len(reviewed))
        estimate, low, high = (round((recalled + (len(unrecalled) - censored) * r) / judged, 3)
                               for r in (rate, low_rate, high_rate))
    return Precision(floor=round(recalled / judged, 3) if judged else None, recalled=recalled, unrecalled=len(unrecalled),
                     censored=censored, reviewed=len(reviewed), escalate=escalate, estimate=estimate, low=low, high=high)


def review_sample(known: Mapping[str, Truth], scores: Mapping[str, float], split: Split, size: int, controls: int,
                  seed: int = 0, budget: int = BUDGET) -> list[tuple[str, Sample]]:
    """Unreviewed reports to send to review, shuffled so the reviewer can't tell them apart.

    `size` random unrecalled flags old enough to judge, plus `controls` recalled flags and `controls` random reports
    from the split. A useful reviewer escalates most recalled reports and few random ones, and
    those two rates are the yardstick for its verdicts on unrecalled flags.
    """
    reports = {no: truth for no, truth in in_split(known, split).items() if truth.verdict is None}
    flagged = set(flag(in_split(known, split), scores, budget))
    rng = random.Random(seed)

    def pick(pool: Iterable[str], count: int, sample: Sample) -> list[tuple[str, Sample]]:
        ordered = sorted(pool)
        return [(no, sample) for no in rng.sample(ordered, min(count, len(ordered)))]

    picked = (pick((no for no in flagged & reports.keys() if not reports[no].links and not reports[no].censored), size, 'flag')
              + pick((no for no in flagged & reports.keys() if reports[no].links), controls, 'recalled')
              + pick(reports.keys() - flagged, controls, 'random'))
    rng.shuffle(picked)
    return picked


def rule_scores(conn, rules: list[lab_rules.Rule], split: Split) -> dict[str, float]:
    """Score 1 for each report the rules flag as Replay would. Rolling counts see reports before the split."""
    if any(rule.trigger != 'arrival' for rule in rules):
        raise ValueError('The benchmark evaluates rules as reports arrive, as Replay does. Remove end-of-replay rules.')
    first, last = SPLITS[split]
    lookback = max((condition.window_days for rule in rules for condition in rule.conditions
                    if isinstance(condition, lab_rules.CountCondition)), default=1)
    rows = lab_public.load_rows(conn, first - timedelta(days=lookback - 1), last)
    return {report.id: 1.0 for report in lab_replay.evaluate(rows, rules, first) if report.flagged}
