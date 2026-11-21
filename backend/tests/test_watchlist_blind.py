from datetime import date, timedelta

from scripts.watchlist_blind import choose, training_fold
from scripts.watchlist_blind_results import score


def test_ranked_backlog_uses_only_earned_slots_and_one_review_per_model():
    first = date(2018,1,7)
    nxt = first + timedelta(days=7)
    # The first week's high-scoring reports must wait for an incumbent review slot.
    weeks = [(first,[('a',('maker','model'),1.0,10,0,0),('b',('maker','model'),0.9,9,0,0)]),
             (nxt,[('c',('x','y'),0.1,0,1,0),('d',('x','z'),0.2,1,1,0)])]
    assert choose(weeks[:1],(0,1,0,0,7)) == {}
    assert choose(weeks,(0,1,0,0,7)) == {'a':nxt,'d':nxt}
    assert set(choose(weeks,(0,1,0,0,0))) == {'c','d'}


def test_earlier_warning_prevents_credit_for_a_later_formal_recall():
    pubs = {'a':'2018-03-01'}
    notices = {'notice':date(2018,5,31)}
    reviews = [{'strict':'yes','report_no':'a','notice_no':'notice','first_public_action':'2018-03-10'}]
    assert score({'a':'2018-03-10'},reviews,pubs,notices)['notices'] == []
    assert score({'a':'2018-03-09'},reviews,pubs,notices)['notices'] == ['notice']

def test_shared_recall_removes_the_entire_training_report():
    rows = {2020: [{'report_no': rid} for rid in ('shared', 'other', 'negative')],
            2022: [{'report_no': 'holdout'}]}
    labels = {2020: [('shared', 'A'), ('shared', 'B'), ('other', 'C')], 2022: [('holdout', 'A')]}
    training, positives = training_fold(rows, labels, 2022)
    assert training == {2020: [{'report_no': 'other'}, {'report_no': 'negative'}]}
    assert positives == {2020: [('other', 'C')]}
