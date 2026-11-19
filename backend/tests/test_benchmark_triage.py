from datetime import date

from scripts.benchmark_triage import collect, expected_events
from cpsc360.heuristic_lab import Report
from cpsc360.lab_rules import CaseAction, Rule


def test_forward_labels_exclude_same_day_and_purge_split_boundary():
    def report(id, day, admitted=False):
        return Report(id=id, available_on=date.fromisoformat(day), product='Mixer', product_key='1',
                      manufacturer_key='maker', injury=admitted, hazard=None, narrative='',
                      facts={'hospitalized': admitted})

    reports = [report('embargo', '2023-12-31'), report('first', '2024-01-01'),
               report('second', '2024-01-02'), report('admission', '2024-03-31', True),
               report('same day', '2024-03-31'), report('censored', '2026-11-01')]
    rule = Rule[CaseAction](name='pair', match='all', action={'kind': 'watchlist'},
                            conditions=[{'kind': 'count', 'group': 'manufacturer',
                                         'window_days': 2, 'threshold': 2}])
    hits, events, periods = collect(reports, [rule])
    assert periods == [set(), {'first', 'second', 'same day'}]
    assert hits == [{'first', 'second', 'same day'}]
    assert set(events) == {'first', 'second'}
    assert len(set(events.values())) == 1
    assert abs(expected_events(periods[1], events, 1) - 2 / 3) < 1e-10
