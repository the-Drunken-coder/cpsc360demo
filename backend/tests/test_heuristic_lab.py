from datetime import date

import pytest
from pydantic import ValidationError

from cpsc360 import heuristic_lab as lab, lab_rules


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
    assert mixer.decisions[0].report.id == 'L01-2'
    assert mixer.decisions[0].report.available_on == date(2025, 2, 2)
    assert mixer.decisions[0].triage == []


def test_latest_start_clamps_to_end_of_june_and_reveals_later_cases():
    request = lab.RunInput(start=date(2025, 3, 31), baseline=lab.BASELINE, candidate=lab.CANDIDATE)
    run = lab.replay(request)
    assert run.end == date(2025, 6, 30)
    assert [case.id for case in run.candidate.cases] == ['L06', 'L07', 'L08']


def triage_rule(name, action, value, *conditions, trigger='arrival'):
    choice = {'kind': action} if value is None else {'kind': action, 'value': value}
    return lab_rules.Rule.model_validate({'name': name, 'match': 'all', 'trigger': trigger,
                                         'conditions': conditions, 'action': choice})


def case_run_input(actions):
    return {
        'start': '2025-01-15',
        'baseline': lab.BASELINE.model_dump(),
        'candidate': {
            **lab.CANDIDATE.model_dump(),
            'triage': [
                {'name': action['kind'], 'match': 'all', 'action': action,
                 'conditions': [{'kind': 'flag', 'field': 'injury', 'state': 'yes'}]}
                for action in actions
            ],
        },
    }


def test_case_actions_keep_the_first_recommendation_and_save_other_matches():
    kinds = ['idi', 'nfa', 'watchlist', 'compliance', 'compliance_other', 'standards_work',
             'ipt_discussion', 'reject', 'forward']
    request = lab.RunInput[lab_rules.CaseAction].model_validate(case_run_input([{'kind': kind} for kind in kinds]))
    run = lab.replay(request)
    saved = lab.RunResult.model_validate_json(run.model_dump_json())
    heater = next(case for case in saved.candidate.cases if case.id == 'L02').decisions[0]
    assert [match.action.model_dump() for match in heater.triage] == [{'kind': kind} for kind in kinds]
    assert [match.action.kind for match in heater.triage if match.applied] == ['idi']


@pytest.mark.parametrize('action', [
    {'kind': 'route', 'value': 'Intake'},
    {'kind': 'not_a_case_action'},
    {'kind': 'nfa', 'value': 'Custom'},
])
def test_new_runs_reject_actions_outside_the_case_catalog(action):
    with pytest.raises(ValidationError):
        lab.RunInput[lab_rules.CaseAction].model_validate(case_run_input([action]))


def test_new_runs_reject_preset_parameters_but_old_snapshots_still_load():
    body = case_run_input([{'kind': 'idi'}])
    preset = {'phrase': 'fire', 'severity': 'injury', 'window_days': 14, 'minimum_count': 3, 'use_signals': True}
    request = lab.RunInput[lab_rules.CaseAction].model_validate(body)
    run = lab.replay(request)
    body['candidate'].update(preset)
    with pytest.raises(ValidationError):
        lab.RunInput[lab_rules.CaseAction].model_validate(body)

    snapshot = run.model_dump(mode='json')
    snapshot['evaluator'] = 'product-rules-v1'
    snapshot['candidate']['rules'].update(preset)
    snapshot['candidate']['metrics'] = {'caught': 1}
    case = snapshot['candidate']['cases'][0]
    case.update(expected_alert=True, first_alert_delay=0)
    case['decisions'][0]['reasons'] = ['Old preset evidence']
    saved = lab.RunResult.model_validate(snapshot)
    assert saved.evaluator == 'product-rules-v1'
    assert saved.candidate == run.candidate
    assert set(saved.candidate.rules.model_dump()) == {'triage'}


def test_rolling_pattern_counts_only_reports_with_the_same_product_and_hazard():
    triage = [triage_rule('Product and hazard cluster', 'idi', None,
                         {'kind': 'count', 'group': 'product_hazard', 'window_days': 30, 'threshold': 2})]
    # Different hazards for the same product and the same hazard for a different product.
    cases = (
        lab.sample_case('A', 'Smoke cluster', 'Mixer', 'Overheating',
                        [(13, False, 'Smoke appeared.'), (32, False, 'More smoke.')]),
        lab.sample_case('B', 'Mixer cut', 'Mixer', 'Cut', [(20, True, 'Sharp edge.')]),
        lab.sample_case('C', 'Heater smoke', 'Heater', 'Overheating', [(24, False, 'Smoke appeared.')]),
    )
    result = lab.evaluate(cases, lab.Rules(triage=triage), date(2025, 1, 15), date(2025, 4, 15))
    [cluster, other_hazard, other_product] = [case.decisions[0] for case in result.cases]
    assert cluster.triage[0].evidence == ['2 matching reports in 30 days (A-1, A-2)']
    assert other_hazard.triage == other_product.triage == []


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
    rules = lab.Rules(triage=triage)
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    saved = lab.RunResult.model_validate_json(run.model_dump_json())
    heater = next(case for case in saved.candidate.cases if case.id == 'L02').decisions[0]
    assert [(match.action.value, match.applied) for match in heater.triage] == [
        ('Intake', True), ('Investigate', False), ('disposition: Investigate', True),
        ('Follow up', True), ('Archive', False),
    ]


def test_pattern_reads_prior_reports_and_end_checks_can_match_without_new_arrival():
    triage = [
        triage_rule('Model repeat', 'tag', 'Repeat',
                    {'kind': 'count', 'group': 'make_model', 'window_days': 365, 'threshold': 2}),
        triage_rule('Review stale entry', 'disposition', 'Review removal',
                    {'kind': 'flag', 'field': 'on_watchlist', 'state': 'yes'},
                    {'kind': 'quiet', 'group': 'product', 'days': 90}, trigger='end'),
    ]
    rules = lab.Rules(triage=triage)
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    assert run.candidate.cases[0].decisions[0].triage[0].evidence == ['2 matching reports in 365 days (L01-1, L01-2)']
    assert [decision.report.id for decision in run.candidate.end_checks] == ['L04-1']


def test_keyword_score_and_sample_are_deterministic_and_unknown_is_not_false():
    triage = [
        triage_rule('Score', 'priority', 'higher', {'kind': 'score', 'terms': 'fire, burned, fire, er', 'operator': 'eq', 'threshold': 2}),
        triage_rule('Archive sample', 'audit', 'spot check', {'kind': 'sample', 'percent': 100}),
        triage_rule('Explicit no', 'tag', 'No sample', {'kind': 'flag', 'field': 'sample_available', 'state': 'no'}),
    ]
    rules = lab.Rules(triage=triage)
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
    rules = lab.Rules(triage=triage)
    run = lab.replay(lab.RunInput(start=date(2025, 1, 15), baseline=lab.BASELINE, candidate=rules))
    [check] = run.candidate.end_checks
    assert check.report.id == 'L01-2'
    assert check.triage[0].evidence[-1] == 'narrative: contains any smoke'
