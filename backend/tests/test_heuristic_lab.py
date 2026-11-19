from datetime import date
import json

import pytest

from cpsc360 import heuristic_lab as lab


def test_run_respects_availability_and_preserves_evidence():
    request = lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=lab.CANDIDATE)
    run = lab.replay(request)
    assert run == lab.replay(request)
    assert run.end == date(2025, 4, 15)
    assert [report.id for report in run.starting_reports] == ['L04-1', 'L01-1']
    report_ids = {decision.report.id for case in run.candidate.cases for decision in case.decisions}
    assert 'L06-1' in report_ids
    assert 'L06-2' not in report_ids
    assert 'L07-1' not in report_ids
    mixer = run.candidate.cases[0]
    assert mixer.id == 'L01'
    assert mixer.first_alert_delay == 0
    assert mixer.decisions[0].report.id == 'L01-2'
    assert mixer.decisions[0].report.available_on == date(2025, 2, 2)
    assert any('L01-1, L01-2' in reason for reason in mixer.decisions[0].reasons)


def test_default_comparison_counts_cases_and_alert_workload_independently():
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=lab.CANDIDATE))
    assert run.baseline.metrics.model_dump() == dict(caught=2, missed=2, extra=1, alerts=3, median_delay_days=2.5)
    assert run.candidate.metrics.model_dump() == dict(caught=3, missed=1, extra=1, alerts=6, median_delay_days=0)
    assert [case.id for case in run.candidate.cases if case.expected_alert and case.first_alert_delay is None] == ['L02']


def test_latest_start_clamps_to_end_of_june_and_reveals_later_cases():
    request = lab.RunInput(start=date(2025, 3, 31), baseline=lab.BASELINE, candidate=lab.CANDIDATE)
    run = lab.replay(request)
    assert run.end == date(2025, 6, 30)
    assert [case.id for case in run.candidate.cases] == ['L06', 'L07', 'L08']


def test_valid_advice_is_replayed_on_independent_cases():
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=lab.CANDIDATE))
    raw = json.dumps({
        'rules': {**lab.CANDIDATE.model_dump(), 'minimum_count': 3},
        'reasoning': 'Reduce alerts on cosmetic complaints.',
        'case_ids': ['L05'],
    })
    assert '"H03"' not in lab.advice_messages(run)[1]['content']
    advice = lab.score_advice(raw, 'stub-model', run)
    assert advice.current.extra == 2
    assert advice.proposed.extra == 1
    assert advice.proposed.missed > advice.current.missed


@pytest.mark.parametrize('rules, case_ids', [
    ({'minimum_count': 3, 'window_days': 10}, ['L05']),
    ({'minimum_count': 3}, ['H03']),
    ({'minimum_count': 1}, ['L05']),
])
def test_advice_rejects_multiple_changes_unknown_evidence_and_invalid_config(rules, case_ids):
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=lab.CANDIDATE))
    raw = json.dumps({'rules': {**lab.CANDIDATE.model_dump(), **rules},
                      'reasoning': 'Change count.', 'case_ids': case_ids})
    with pytest.raises(ValueError):
        lab.score_advice(raw, 'stub-model', run)


def triage_rule(name, action, value, *conditions, trigger='arrival'):
    from cpsc360.lab_rules import Rule

    return Rule.model_validate({'name': name, 'match': 'all', 'trigger': trigger,
                                'conditions': conditions, 'action': {'kind': action, 'value': value}})


def test_triage_combines_facts_and_applies_exclusions_and_disposition_order():
    narrative = {'kind': 'text', 'field': 'narrative', 'operator': 'contains_any', 'value': 'fire'}
    hospitalized = {'kind': 'flag', 'field': 'hospitalized', 'state': 'yes'}
    follow_up = {'kind': 'flag', 'field': 'contact_available', 'state': 'no'}
    triage = [
        triage_rule('Route fire', 'route', 'Intake', narrative),
        triage_rule('Consider investigation', 'disposition', 'Investigate', hospitalized),
        triage_rule('No contact', 'suppress', 'disposition: Investigate', follow_up),
        triage_rule('Manual follow-up', 'disposition', 'Follow up', hospitalized, follow_up),
        triage_rule('Fallback', 'disposition', 'Archive', hospitalized),
    ]
    rules = lab.CANDIDATE.model_copy(update={'use_signals': False, 'triage': triage})
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    heater = next(case for case in run.candidate.cases if case.id == 'L02').decisions[0]
    assert [(match.action.value, match.applied) for match in heater.triage] == [
        ('Intake', True), ('Investigate', False), ('disposition: Investigate', True),
        ('Follow up', True), ('Archive', False),
    ]
    assert not heater.reasons


def test_pattern_reads_prior_reports_and_end_checks_can_match_without_new_arrival():
    triage = [
        triage_rule('Model repeat', 'tag', 'Repeat',
                    {'kind': 'count', 'group': 'make_model', 'window_days': 365, 'threshold': 2}),
        triage_rule('Review stale entry', 'disposition', 'Review removal',
                    {'kind': 'flag', 'field': 'on_watchlist', 'state': 'yes'},
                    {'kind': 'quiet', 'group': 'product', 'days': 90}, trigger='end'),
    ]
    rules = lab.CANDIDATE.model_copy(update={'triage': triage})
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    assert run.candidate.cases[0].decisions[0].triage[0].evidence == ['2 matching reports in 365 days (L01-1, L01-2)']
    assert [decision.report.id for decision in run.candidate.end_checks] == ['L04-1']


def test_keyword_score_and_sample_are_deterministic_and_unknown_is_not_false():
    triage = [
        triage_rule('Score', 'priority', 'higher', {'kind': 'score', 'terms': 'fire, burned, fire, er', 'operator': 'eq', 'threshold': 2}),
        triage_rule('Archive sample', 'audit', 'spot check', {'kind': 'sample', 'percent': 100}),
        triage_rule('Explicit no', 'tag', 'No sample', {'kind': 'flag', 'field': 'sample_available', 'state': 'no'}),
    ]
    rules = lab.CANDIDATE.model_copy(update={'triage': triage})
    request = lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules)
    run = lab.replay(request)
    assert run == lab.replay(request)
    mixer = run.candidate.cases[0].decisions
    assert [match.rule for match in mixer[0].triage] == ['Archive sample']
    assert [match.rule for match in mixer[1].triage] == ['Score', 'Archive sample']


def test_end_checks_keep_earlier_report_facts_and_cite_only_matching_phrases():
    triage = [
        triage_rule('Review after quiet period', 'route', 'Intake',
                    {'kind': 'flag', 'field': 'public_attention', 'state': 'yes'},
                    {'kind': 'quiet', 'group': 'product', 'days': 30},
                    {'kind': 'text', 'field': 'narrative', 'operator': 'contains_any', 'value': 'smoke, fire'},
                    trigger='end'),
    ]
    rules = lab.CANDIDATE.model_copy(update={'triage': triage})
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    [check] = run.candidate.end_checks
    assert check.report.id == 'L01-2'
    assert check.triage[0].evidence[-1] == 'narrative: contains any smoke'
