"""The recall benchmark against the loaded public snapshot and the committed recall ledger."""

from datetime import date, timedelta

import pytest
from psycopg.rows import dict_row

from cpsc360 import db, lab_replay, lab_rules, recall_benchmark as bench

RYOBI_REPORT = '20230324-B2A32-2147348506'  # published 2023-04-12, listed by notice 25452 on 2025-08-28
RYOBI_RULE = lab_rules.Rule[lab_rules.CaseAction].model_validate(
    {'name': 'Pressure washer', 'match': 'all', 'action': {'kind': 'watchlist'},
     'conditions': [{'kind': 'text', 'field': 'narrative', 'operator': 'contains_any', 'value': 'pressure washer'}]})


@pytest.fixture(scope='module')
def conn():
    with db.connect() as conn:
        conn.row_factory = dict_row
        yield conn


@pytest.fixture(scope='module')
def known(conn):
    return bench.truths(conn, reviews=[])


def unrecalled_test_report(known, skip=()):
    return next(no for no, truth in sorted(known.items()) if truth.published >= date(2023, 1, 1)
                and not truth.links and not truth.censored and no not in skip)


def test_near_identical_notices_form_one_wave():
    notices = lab_replay.ledger().notices
    # Wintergreen-oil packaging notices from different firms, months apart.
    assert notices['20723'].wave == notices['20725'].wave == notices['20766'].wave
    # Samsung and LG electric ranges recalled for fire six months apart are one pattern.
    assert notices['24335'].wave == notices['25126'].wave
    # One firm's recalls of different products for different hazards stay apart.
    assert notices['25127'].wave != notices['25452'].wave
    # So do one firm's recalls of the same vehicles for different hazards.
    assert notices['20733'].wave != notices['20735'].wave


def test_a_flag_before_the_recall_catches_its_wave_with_a_capped_lead(known):
    result = bench.score(known, {RYOBI_REPORT: 1.0}, 'test')
    assert (result.flags, result.caught_waves) == (1, 1)
    [catch] = result.caught
    assert (catch.notice_no, catch.report_no) == ('25452', RYOBI_REPORT)
    assert catch.lead_days == bench.LEAD_CAP_DAYS  # the true lead from the week's close is 864 days
    assert result.precision.floor == 1.0
    assert 0 < result.random_waves < 0.1
    assert bench.score(known, {RYOBI_REPORT: 1.0}, 'dev').flags == 0


def test_each_week_flags_only_its_top_scores_within_budget(known):
    week = sorted(no for no, truth in known.items() if bench.week_end(truth.published) == date(2023, 4, 16))
    assert len(week) > bench.BUDGET + 2
    scores = {no: 1.0 for no in week} | {RYOBI_REPORT: 9.0, week[0]: 8.0, week[1]: 7.0}
    result = bench.score(known, scores, 'test', budget=3)
    assert result.flags == 3
    assert result.caught_waves == 1
    assert result.precision.recalled + result.precision.unrecalled == 3


def test_reviews_turn_unknown_flags_into_an_estimated_precision(conn, known):
    other = unrecalled_test_report(known)
    scores = {RYOBI_REPORT: 2.0, other: 1.0}
    assert bench.score(known, scores, 'test').precision.model_dump(include={'floor', 'estimate'}) == \
        {'floor': 0.5, 'estimate': None}

    ai = bench.Review(other, 'escalate', 'ai:test', 'flag', '')
    reviewed = bench.score(bench.truths(conn, [ai]), scores, 'test').precision
    assert (reviewed.reviewed, reviewed.escalate, reviewed.estimate, reviewed.floor) == (1, 1, 1.0, 0.5)
    assert bench.truths(conn, [ai])[other].label == 'missed_hazard'

    # A human verdict overrides the AI, whichever came first.
    for reviews in ([ai, bench.Review(other, 'dismiss', 'human', 'check', '')],
                    [bench.Review(other, 'dismiss', 'human', 'check', ''), ai]):
        assert bench.score(bench.truths(conn, reviews), scores, 'test').precision.estimate == 0.5


def test_review_samples_hide_controls_among_unrecalled_flags(known):
    week = sorted(no for no, truth in known.items() if date(2023, 4, 1) <= truth.published <= date(2023, 6, 30))
    scores = {no: 1.0 for no in week} | {RYOBI_REPORT: 9.0}
    sample = bench.review_sample(known, scores, 'test', size=5, controls=2)
    kinds = {kind: [no for no, k in sample if k == kind] for kind in ('flag', 'recalled', 'random')}
    assert [len(kinds['flag']), len(kinds['recalled']), len(kinds['random'])] == [5, 1, 2]
    assert kinds['recalled'] == [RYOBI_REPORT]
    assert all(not known[no].links for no in kinds['flag'])
    assert all(known[no].published >= date(2022, 7, 1) for no, _ in sample)


def test_training_labels_only_include_recalls_already_announced():
    assert RYOBI_REPORT not in bench.labels_as_of(date(2025, 8, 1))
    assert RYOBI_REPORT in bench.labels_as_of(date(2025, 8, 28) + timedelta(days=1))


def test_rules_score_through_the_lab_engine(conn, known):
    scores = bench.rule_scores(conn, [RYOBI_RULE], 'test')
    assert scores[RYOBI_REPORT] == 1.0
    assert all(date(2022, 7, 1) <= known[no].published <= date(2025, 10, 31) for no in scores)


def test_words_in_report_text_that_look_like_codes_do_not_link_recalls():
    # A Hampton Bay table lamp report says "3-way", like a Target floor lamp notice and a lamp socket notice.
    # An iPhone report says "256GB", like a MacBook Pro notice. A Kenmore range's "790" is the Sears
    # prefix on every Electrolux-made Kenmore, not a model.
    for report_no in ('20110519-FBDCE-2147479025', '20170224-7D0A7-2147405766', '20120807-471DC-2147465009'):
        assert all(report_no not in {linked for linked, _ in covered} for covered in lab_replay.ledger().reports.values())


def test_a_reannounced_recall_is_one_wave_measured_from_the_first_notice(known):
    # Gree recalled its dehumidifiers in 2013 and reannounced the recall in 2014 and 2016.
    notices = lab_replay.ledger().notices
    assert notices['13283'].wave == notices['14179'].wave == notices['17039'].wave
    assert notices['23034'].wave == notices['24181'].wave  # "Major Recall Expansion" of Black+Decker steamers
    # Textron's crash recall expansion shares vehicles with its fire recall, which stays its own wave with its reports.
    assert notices['25701'].wave == notices['24709'].wave != notices['24229'].wave
    assert lab_replay.ledger().reports['24229']
    # Electrolux's dual-fuel range recall only matched on "790", so it no longer joins the reannounced electric range recall.
    assert '15143' not in notices and notices['24235'].wave == '24235'
    result = bench.score(known, {'20120810-D8FCC-2147464905': 1.0}, 'train')
    assert [(catch.notice_no, catch.lead_days) for catch in result.caught] == [('13283', 361)]


def test_rules_flag_only_when_their_first_match_sends_the_report_for_review(conn):
    close = RYOBI_RULE.model_copy(update={'name': 'Close', 'action': lab_rules.CaseAction(kind='nfa')})
    assert RYOBI_REPORT not in bench.rule_scores(conn, [close, RYOBI_RULE], 'test')
    with pytest.raises(ValueError):
        bench.rule_scores(conn, [RYOBI_RULE.model_copy(update={'trigger': 'end'})], 'test')


def test_a_flag_after_the_recall_deadline_is_not_a_hit(known):
    # A Fitbit report published 2014-02-18 is flagged when its week closes on 02-23, after the 02-20 recall.
    result = bench.score(known, {'20140123-97EE8-2147447924': 1.0}, 'train')
    assert (result.flags, result.caught_waves, result.precision.floor) == (1, 0, 0.0)


def test_training_labels_wait_for_the_notice_that_lists_the_models():
    # Samsung warned about top-load washers on 2016-09-28 and listed the models in notice 17028 on 11-04.
    covered = {report_no for report_no, _ in lab_replay.ledger().reports['17028']}
    assert not covered & bench.labels_as_of(date(2016, 10, 1))
    assert covered <= bench.labels_as_of(date(2016, 11, 5))


def test_any_supplied_score_ranks_and_missing_scores_abstain(known):
    assert bench.score(known, {RYOBI_REPORT: -5.0}, 'test').caught_waves == 1


def test_estimated_precision_covers_the_same_flags_as_the_floor(conn):
    recent = '20250716-B2C19-2147329525'  # too recent for "no recall yet" to count against it
    reviewed = bench.truths(conn, [bench.Review(recent, 'dismiss', 'human', 'check', '')])
    assert reviewed[recent].censored and not reviewed[recent].links
    precision = bench.score(reviewed, {RYOBI_REPORT: 2.0, recent: 1.0}, 'test').precision
    assert (precision.floor, precision.reviewed, precision.estimate) == (1.0, 0, None)
