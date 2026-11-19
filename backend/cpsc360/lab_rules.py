"""Configurable triage rules for synthetic reports."""

from datetime import date, timedelta
from hashlib import sha256
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CaseActionKind = Literal['nfa', 'watchlist', 'idi', 'compliance', 'compliance_other', 'standards_work',
                         'ipt_discussion', 'reject', 'forward']
LegacyActionKind = Literal['tag', 'route', 'copy', 'escalate', 'priority', 'disposition', 'suppress', 'audit']
Group = Literal['product', 'hazard', 'product_hazard', 'manufacturer', 'make_model', 'manufacturer_hazard']
TextField = Literal['narrative', 'product', 'hazard', 'manufacturer', 'model', 'jurisdiction', 'body_area', 'retailer']
NumberField = Literal['age', 'tbsa', 'burn_depth', 'people_injured']
FlagField = Literal['injury', 'hospitalized', 'death', 'contact_available', 'sample_available',
                    'missing_detail', 'intended_use', 'duplicate', 'recalled', 'public_attention',
                    'reviewer_disagreement', 'active_case', 'unbranded', 'on_watchlist']

# Synthetic observations attached to particular fixture reports. Omitted values are unknown.
FACTS = {
    'L01-1': {'manufacturer': 'Aster', 'model': 'M7'},
    'L01-2': {'manufacturer': 'Aster', 'model': 'M7', 'public_attention': True},
    'L01-3': {'manufacturer': 'Aster', 'model': 'M7', 'burn_depth': 2, 'body_area': 'hand', 'tbsa': 3,
              'contact_available': True, 'sample_available': True, 'missing_detail': True},
    'L02-1': {'manufacturer': 'Northline', 'model': 'H2', 'burn_depth': 3, 'hospitalized': True,
              'age': 72, 'tbsa': 12, 'body_area': 'forearm', 'contact_available': False, 'sample_available': True},
    'L03-1': {'manufacturer': 'Loam', 'model': 'K4', 'age': 4, 'burn_depth': 2, 'tbsa': 6,
              'intended_use': True, 'contact_available': True, 'sample_available': True, 'missing_detail': True},
    'L03-2': {'manufacturer': 'Loam', 'model': 'K4', 'recalled': True, 'reviewer_disagreement': True},
    'L04-1': {'jurisdiction': 'CPSC', 'burn_depth': 0, 'on_watchlist': True},
    'L05-2': {'duplicate': True, 'active_case': True},
    'L06-1': {'manufacturer': 'Redwood', 'model': 'D9', 'retailer': 'Marketplace', 'unbranded': True},
    'L06-2': {'manufacturer': 'Redwood', 'model': 'D9', 'retailer': 'Marketplace', 'unbranded': True},
    'L07-1': {'jurisdiction': 'Unassigned'},
    'L08-1': {'manufacturer': 'Juniper', 'model': 'S4', 'people_injured': 2},
    'L08-2': {'manufacturer': 'Juniper', 'model': 'S4'},
}


class Config(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TextCondition(Config):
    kind: Literal['text']
    field: TextField
    operator: Literal['contains_any', 'contains_all', 'equals_any', 'contains_none', 'unknown']
    value: str = Field(default='', max_length=400)

    @model_validator(mode='after')
    def require_phrases(self):
        if self.operator != 'unknown' and not terms(self.value):
            raise ValueError('Enter at least one phrase.')
        return self


class NumberCondition(Config):
    kind: Literal['number']
    field: NumberField
    operator: Literal['gte', 'gt', 'lte', 'lt', 'eq', 'unknown']
    value: float = Field(default=0, ge=0, le=120)


class FlagCondition(Config):
    kind: Literal['flag']
    field: FlagField
    state: Literal['yes', 'no', 'unknown']


class CountCondition(Config):
    kind: Literal['count']
    group: Group
    window_days: int = Field(ge=1, le=366)
    threshold: int = Field(ge=0, le=100)
    filter: Literal['all', 'injury', 'hospitalized'] = 'all'
    operator: Literal['gte', 'lte'] = 'gte'
    measure: Literal['reports', 'manufacturers'] = 'reports'


class ScoreCondition(Config):
    kind: Literal['score']
    terms: str = Field(min_length=1, max_length=400)
    operator: Literal['gte', 'eq']
    threshold: int = Field(ge=0, le=40)

    @field_validator('terms')
    @classmethod
    def require_keywords(cls, value):
        if not terms(value):
            raise ValueError('Enter at least one keyword.')
        return value


class QuietCondition(Config):
    kind: Literal['quiet']
    group: Group
    days: int = Field(ge=1, le=366)


class SampleCondition(Config):
    kind: Literal['sample']
    percent: int = Field(ge=1, le=100)


Condition = Annotated[TextCondition | NumberCondition | FlagCondition | CountCondition | ScoreCondition | SampleCondition | QuietCondition,
                      Field(discriminator='kind')]


class CaseAction(Config):
    kind: CaseActionKind


class LegacyAction(Config):
    kind: LegacyActionKind
    value: str = Field(min_length=1, max_length=80)

    @model_validator(mode='after')
    def validate_target(self):
        targets = {'tag', 'route', 'copy', 'escalate', 'priority', 'disposition', 'audit'}
        if self.kind == 'suppress':
            kind, delimiter, value = self.value.partition(':')
            if kind.casefold() not in targets or (delimiter and not value.strip()):
                raise ValueError('Choose a valid action or action:value to suppress.')
        return self


Action = Annotated[CaseAction | LegacyAction, Field(discriminator='kind')]


class Rule[ActionT: Action](Config):
    name: str = Field(min_length=1, max_length=80)
    match: Literal['all', 'any']
    trigger: Literal['arrival', 'end'] = 'arrival'
    conditions: list[Condition] = Field(min_length=1, max_length=12)
    action: ActionT

    @model_validator(mode='after')
    def validate_trigger(self):
        if self.trigger != 'end' and any(isinstance(condition, QuietCondition) for condition in self.conditions):
            raise ValueError('Evaluate quiet-period checks at the end of the replay.')
        return self


class Match(BaseModel):
    rule: str
    action: Action
    evidence: list[str]
    applied: bool = True


def report_facts(report) -> dict:
    return {**report.facts, **report.model_dump(exclude={'facts'})}


def terms(value: str) -> list[str]:
    return list(dict.fromkeys(term.strip().casefold() for term in value.split(',') if term.strip()))


def group_key(facts: dict, group: Group) -> tuple:
    fields = {'product_hazard': ('product', 'hazard'), 'make_model': ('manufacturer', 'model'),
              'manufacturer_hazard': ('manufacturer', 'hazard')}.get(group, (group,))
    return tuple(facts.get(field) for field in fields)


def matches(condition: Condition, facts: dict, previous: list[dict], day: date) -> str | None:
    if isinstance(condition, TextCondition):
        value = facts.get(condition.field)
        if condition.operator == 'unknown':
            return f'{condition.field} is unknown' if value is None else None
        phrases = terms(condition.value)
        if value is None or not phrases:
            return None
        value = value.casefold()
        found = [phrase for phrase in phrases if phrase in value]
        matched = {
            'contains_any': bool(found), 'contains_all': len(found) == len(phrases),
            'contains_none': not found, 'equals_any': value in phrases,
        }[condition.operator]
        if not matched:
            return None
        evidence = phrases if condition.operator == 'contains_none' else [value] if condition.operator == 'equals_any' else found
        return f'{condition.field}: {condition.operator.replace("_", " ")} {", ".join(evidence)}'
    if isinstance(condition, NumberCondition):
        value = facts.get(condition.field)
        if condition.operator == 'unknown':
            return f'{condition.field} is unknown' if value is None else None
        if value is None:
            return None
        matched = {'gte': value >= condition.value, 'gt': value > condition.value,
                   'lte': value <= condition.value, 'lt': value < condition.value, 'eq': value == condition.value}
        return f'{condition.field}: {value:g}' if matched[condition.operator] else None
    if isinstance(condition, FlagCondition):
        value = facts.get(condition.field)
        state = 'unknown' if value is None else 'yes' if value else 'no'
        return f'{condition.field.replace("_", " ")}: {state}' if state == condition.state else None
    if isinstance(condition, ScoreCondition):
        narrative = facts['narrative'].casefold()
        found = [term for term in terms(condition.terms) if re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', narrative)]
        matched = len(found) >= condition.threshold if condition.operator == 'gte' else len(found) == condition.threshold
        return f'Keyword score {len(found)} ({", ".join(found) or "no matches"})' if matched else None
    if isinstance(condition, SampleCondition):
        bucket = int.from_bytes(sha256(facts['id'].encode()).digest()[:8]) % 100
        return f'In deterministic {condition.percent}% sample' if bucket < condition.percent else None
    key = group_key(facts, condition.group)
    if None in key:
        return None
    if isinstance(condition, QuietCondition):
        last = max((item['available_on'] for item in previous if group_key(item, condition.group) == key), default=None)
        if last is None:
            return None
        elapsed = (day - last).days
        return f'{elapsed} days since the latest matching report ({last})' if elapsed >= condition.days else None
    cutoff = day - timedelta(days=condition.window_days - 1)
    items = [item for item in previous if item['available_on'] >= cutoff
           and group_key(item, condition.group) == key
           and (condition.filter == 'all' or item.get(condition.filter) is True)]
    ids = [item['id'] for item in items]
    count = len(ids) if condition.measure == 'reports' else len({item['manufacturer'] for item in items if item.get('manufacturer')})
    matched = count >= condition.threshold if condition.operator == 'gte' else count <= condition.threshold
    return f'{count} matching {condition.measure} in {condition.window_days} days ({", ".join(ids) or "none"})' if matched else None


def apply_rules(rules: list[Rule], facts: dict, previous: list[dict], day: date,
                trigger: Literal['arrival', 'end'] = 'arrival') -> list[Match]:
    result = []
    for rule in rules:
        if rule.trigger != trigger:
            continue
        evidence = [reason for condition in rule.conditions if (reason := matches(condition, facts, previous, day))]
        if evidence and (rule.match == 'any' or len(evidence) == len(rule.conditions)):
            result.append(Match(rule=rule.name, action=rule.action, evidence=evidence))
    suppressed = {':'.join(part.strip() for part in item.action.value.casefold().split(':', 1))
                  for item in result if isinstance(item.action, LegacyAction) and item.action.kind == 'suppress'}
    disposition_chosen = False
    for item in result:
        action = item.action
        if isinstance(action, LegacyAction) and action.kind != 'suppress':
            if action.kind in suppressed or f'{action.kind}:{action.value.casefold()}' in suppressed:
                item.applied = False
        if item.applied and (isinstance(action, CaseAction) or action.kind == 'disposition'):
            item.applied = not disposition_chosen
            disposition_chosen = True
    return result
