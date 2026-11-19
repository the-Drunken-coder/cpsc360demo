from datetime import date

import pytest
from pydantic import ValidationError

from cpsc360 import heuristic_lab as lab, lab_public, lab_rules


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
    assert [case.id for case in run.candidate.cases] == ['L09', 'L06', 'L07', 'L08']


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


@pytest.mark.parametrize('start', ['2025-01-01', '2025-01-15', '2025-03-31'])
def test_death_rule_recommends_idi_for_a_report_with_a_recorded_death(start):
    body = case_run_input([{'kind': 'idi'}])
    body['start'] = start
    body['candidate']['triage'][0]['conditions'][0]['field'] = 'death'
    run = lab.replay(lab.RunInput[lab_rules.CaseAction].model_validate(body))

    matched = [
        (decision.report, match)
        for case in run.candidate.cases
        for decision in case.decisions
        for match in decision.triage
        if match.applied
    ]
    [(report, match)] = matched
    assert report.facts['death'] is True
    assert match.action.kind == 'idi'
    assert match.evidence == ['death: yes']


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


def public_row(**overrides):
    return {
        'report_no': 'PUBLIC-1', 'publication_date': date(2025, 2, 1), 'current_sha256': 'source-hash',
        'product_code': '123', 'product_type': 'Dressers', 'product_description': 'Test dresser',
        'incident_description': 'A report describes a tip-over.', 'hazards': ['tip_over'],
        'manufacturer_name': 'Test manufacturer', 'manufacturer_key': 'testmanufacturer', 'brand': None,
        'model': None, 'retailer': None, 'victim_age': 7,
        'severity': 'Death', 'severity_rank': 9, 'is_injury': True,
        **overrides,
    }


def test_public_rule_inputs_preserve_source_identity_and_distinguish_unknown_severity():
    row = public_row()
    report = lab_public.to_report(row)
    assert report.id == 'PUBLIC-1'
    assert report.source_sha256 == 'source-hash'
    assert report.available_on == row['publication_date']
    assert report.hazards == ['Tip-over']
    assert report.facts == {'manufacturer': 'Test manufacturer', 'age': 7, 'death': True}

    unknown = lab_public.to_report({**row, 'severity': 'Unspecified', 'severity_rank': 0, 'is_injury': False})
    assert unknown.injury is None
    assert 'death' not in unknown.facts
    assert 'hospitalized' not in unknown.facts


def test_public_model_placeholders_are_unknown_and_do_not_form_clusters():
    reports = (
        lab_public.to_report(public_row(report_no='EARLIER', publication_date=date(2025, 1, 14), model='N/A')),
        lab_public.to_report(public_row(report_no='ARRIVAL', publication_date=date(2025, 1, 16), model='N/A')),
    )
    rules = lab.Rules(triage=[
        triage_rule('Known model cluster', 'idi', None,
                    {'kind': 'count', 'group': 'make_model', 'window_days': 30, 'threshold': 2}),
        triage_rule('Unknown model', 'watchlist', None,
                    {'kind': 'text', 'field': 'model', 'operator': 'unknown'}),
    ])
    result = lab.evaluate((lab.Case(id='DRESSER', title='Dresser', reports=reports),),
                          rules, date(2025, 1, 15), date(2025, 4, 15))
    [match] = result.cases[0].decisions[0].triage
    assert match.rule == 'Unknown model'
    assert match.evidence == ['model is unknown']


def test_blank_public_text_matches_unknown_and_skips_negative_checks():
    report = lab_public.to_report(public_row(product_type='', product_description='  ', incident_description=''))
    rules = lab.Rules(triage=[
        triage_rule('No fire keywords', 'nfa', None,
                    {'kind': 'score', 'terms': 'fire', 'operator': 'eq', 'threshold': 0}),
        triage_rule('Explicitly lacks fire', 'idi', None, *[
            {'kind': 'text', 'field': field, 'operator': 'contains_none', 'value': 'fire'}
            for field in ('product', 'narrative')
        ]),
        triage_rule('Missing text', 'watchlist', None, *[
            {'kind': 'text', 'field': field, 'operator': 'unknown'} for field in ('product', 'narrative')
        ]),
    ])
    known = lab_public.to_report(public_row(report_no='PUBLIC-2', incident_description='The drawer jammed.'))
    cases = (lab.Case(id=report.id, title=report.id, reports=(report,)),
             lab.Case(id=known.id, title=known.id, reports=(known,)))
    result = lab.evaluate(cases, rules, date(2025, 1, 15), date(2025, 4, 15))
    [match] = result.cases[0].decisions[0].triage
    assert match.rule == 'Missing text'
    assert match.evidence == ['product is unknown', 'narrative is unknown']
    assert [item.rule for item in result.cases[1].decisions[0].triage if item.applied] == ['No fire keywords']


def test_shared_hazard_count_deduplicates_reports_with_multiple_matching_tags():
    rule = triage_rule('Investigate repeat hazards', 'idi', None,
                       {'kind': 'count', 'group': 'product_hazard', 'window_days': 30, 'threshold': 2})
    reports = (
        lab.Report(id='EARLIER', available_on=date(2025, 1, 14), product='Mixer', hazard=None,
                   hazards=['Fire', 'Overheating'], injury=False, narrative='First report'),
        lab.Report(id='ARRIVAL', available_on=date(2025, 1, 16), product='Mixer', hazard=None,
                   hazards=['Fire', 'Overheating', 'Burn'], injury=False, narrative='Second report'),
    )
    result = lab.evaluate((lab.Case(id='MIXER', title='Mixer', reports=reports),),
                          lab.Rules(triage=[rule]), date(2025, 1, 15), date(2025, 4, 15))
    [decision] = result.cases[0].decisions
    assert decision.triage[0].evidence == ['2 matching reports in 30 days (EARLIER, ARRIVAL)']


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
