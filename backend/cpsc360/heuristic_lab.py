"""Deterministic replay of synthetic product reports."""

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from . import lab_rules

FIRST_DAY = date(2025, 1, 1)
LAST_START = date(2025, 3, 31)
SCENARIO = 'product-safety-v1'
EVALUATOR = 'product-rules-v2'


class Rules[ActionT: lab_rules.Action](BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    triage: list[lab_rules.Rule[ActionT]] = Field(default_factory=list, max_length=20)


BASELINE = Rules[lab_rules.CaseAction]()
CANDIDATE = Rules[lab_rules.CaseAction]()


class RunInput[ActionT: lab_rules.Action](BaseModel):
    model_config = ConfigDict(extra='forbid')

    start: date = Field(ge=FIRST_DAY, le=LAST_START)
    baseline: Rules[ActionT]
    candidate: Rules[ActionT]


class Report(BaseModel):
    id: str
    available_on: date
    product: str
    hazard: str
    injury: bool
    narrative: str
    facts: dict[str, str | bool | int | float] = Field(default_factory=dict)


class ScenarioView(BaseModel):
    version: str
    first_start: date
    last_start: date
    as_of: date
    baseline: Rules
    candidate: Rules
    reports: list[Report]


class Case(BaseModel):
    id: str
    title: str
    reports: tuple[Report, ...]


def sample_case(id: str, title: str, product: str, hazard: str,
                observations: list[tuple[int, bool, str]]) -> Case:
    return Case(id=id, title=title, reports=tuple(
        Report(id=f'{id}-{number}', available_on=FIRST_DAY + timedelta(days=day),
               product=product, hazard=hazard, injury=injury, narrative=narrative,
               facts=lab_rules.FACTS.get(f'{id}-{number}', {}))
        for number, (day, injury, narrative) in enumerate(observations, 1)
    ))


CASES = (
    sample_case('L01', 'Mixer smoke cluster', 'Countertop mixer', 'Overheating', [
        (13, False, 'Smoke rose from the speed control.'),
        (32, False, 'Smoke filled the bowl after two minutes of use.'),
        (37, True, 'The motor caught fire and burned my hand.'),
    ]),
    sample_case('L02', 'Heater fire with injury', 'Portable heater', 'Fire', [
        (40, True, 'The heater caught fire and burned my forearm.'),
    ]),
    sample_case('L03', 'Kettle breaks at handle', 'Electric kettle', 'Mechanical failure', [
        (61, True, 'The handle detached while pouring and hot water spilled onto my leg.'),
        (84, False, 'The handle came away as I lifted the kettle.'),
    ]),
    sample_case('L04', 'Fire explicitly denied', 'Bread maker', 'Fire', [
        (7, False, 'There was no fire or smoke. The display briefly went blank.'),
    ]),
    sample_case('L05', 'Routine cosmetic complaints', 'Desk fan', 'Cosmetic', [
        (55, False, 'The paint chipped around the grille.'),
        (60, False, 'The housing has a scratch near the label.'),
        (62, False, 'The outer paint is flaking. The fan works normally.'),
    ]),
    sample_case('L06', 'Later battery reports', 'Cordless drill', 'Overheating', [
        (101, False, 'The charger began emitting smoke.'),
        (112, False, 'The battery casing melted after charging.'),
    ]),
    sample_case('L07', 'Single packaging complaint', 'Toaster', 'Packaging', [
        (129, False, 'The package arrived torn and the tray was loose in the box.'),
    ]),
    sample_case('L08', 'Later scooter brake failures', 'Kick scooter', 'Mechanical failure', [
        (150, True, 'The rear brake snapped and I fell.'),
        (163, False, 'The rear brake disconnected while I was slowing down.'),
    ]),
)

class Decision(BaseModel):
    report: Report
    triage: list[lab_rules.Match] = Field(default_factory=list)


class CaseResult(BaseModel):
    id: str
    title: str
    decisions: list[Decision]


class SavedRules(Rules):
    # Version 1 snapshots include retired preset-alert settings.
    model_config = ConfigDict(extra='ignore')


class Evaluation(BaseModel):
    rules: SavedRules
    cases: list[CaseResult]
    end_checks: list[Decision] = Field(default_factory=list)


class RunResult(BaseModel):
    scenario: str
    evaluator: str
    start: date
    end: date
    starting_reports: list[Report]
    baseline: Evaluation
    candidate: Evaluation


class RunSummary(BaseModel):
    id: int
    created_at: datetime
    start: date
    end: date


class SavedRun(RunSummary):
    result: RunResult


def available_reports(as_of: date) -> list[Report]:
    return sorted(
        (report for case in CASES for report in case.reports if report.available_on <= as_of),
        key=lambda report: (report.available_on, report.id),
    )


def end_date(start: date) -> date:
    year, month = divmod(start.year * 12 + start.month - 1 + 3, 12)
    return date(year, month + 1, min(start.day, monthrange(year, month + 1)[1]))


def evaluate(cases: tuple[Case, ...], rules: Rules, start: date, end: date) -> Evaluation:
    decisions: dict[str, list[Decision]] = defaultdict(list)
    timeline = sorted(
        ((report, case.id) for case in cases for report in case.reports if report.available_on <= end),
        key=lambda item: (item[0].available_on, item[0].id),
    )
    previous = []
    for report, case_id in timeline:
        facts = lab_rules.report_facts(report)
        previous.append(facts)
        if report.available_on > start:
            decisions[case_id].append(Decision(
                report=report, triage=lab_rules.apply_rules(rules.triage, facts, previous, report.available_on),
            ))

    results = [CaseResult(id=case.id, title=case.title, decisions=decisions[case.id])
               for case in cases if case.id in decisions]
    end_checks = []
    if any(rule.trigger == 'end' for rule in rules.triage):
        for (report, _), facts in zip(timeline, previous, strict=True):
            checks = lab_rules.apply_rules(rules.triage, facts, previous, end, 'end')
            if checks:
                end_checks.append(Decision(report=report, triage=checks))
    return Evaluation(rules=SavedRules(triage=rules.triage), cases=results, end_checks=end_checks)


def replay(request: RunInput) -> RunResult:
    end = end_date(request.start)
    return RunResult(
        scenario=SCENARIO, evaluator=EVALUATOR, start=request.start, end=end,
        starting_reports=available_reports(request.start),
        baseline=evaluate(CASES, request.baseline, request.start, end),
        candidate=evaluate(CASES, request.candidate, request.start, end),
    )
