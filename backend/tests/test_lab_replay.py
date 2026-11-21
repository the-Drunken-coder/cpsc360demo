"""Replay mode through the HTTP API against the loaded public snapshot and the committed recall ledger."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from cpsc360.app import app

RYOBI_REPORT = '20230324-B2A32-2147348506'
RYOBI_NOTICE = '25452'
RANGE = {'start': '2023-04-01', 'end': '2025-09-30'}
RYOBI_RULE = {'name': 'Pressure washer', 'match': 'all', 'action': {'kind': 'watchlist'},
              'conditions': [{'kind': 'text', 'field': 'narrative', 'operator': 'contains_any', 'value': 'pressure washer'}]}


@pytest.fixture(scope='module')
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope='module')
def viewer(client):
    token = client.post('/api/session', json={'handle': 'viewer'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def window(client, headers, since, until, rules):
    response = client.post('/api/heuristic-lab/replay/window', headers=headers,
                           json={**RANGE, 'since': since, 'until': until, 'rules': rules})
    assert response.status_code == 200, response.text
    return response.json()


def test_bounds_come_from_the_snapshot(client, viewer):
    response = client.get('/api/heuristic-lab/replay', headers=viewer)
    assert response.status_code == 200, response.text
    bounds = response.json()
    assert bounds['first'] <= bounds['start'] <= bounds['end'] == bounds['last']


def test_a_rule_flag_on_arrival_catches_a_later_recall_with_its_lead(client, viewer):
    # Day 1: the report arrives on its publication day and the rule flags it.
    arrival = window(client, viewer, '2023-04-01', '2023-05-01', [RYOBI_RULE])
    report = next(r for r in arrival['reports'] if r['id'] == RYOBI_REPORT)
    assert report['published'] == '2023-04-12'
    assert report['rules'] == [0]
    assert report['title'] == 'Ryobi RY142711VNM'
    assert all(r['published'] >= '2023-04-01' for r in arrival['reports'])
    assert all(r['rules'] == [] or r['evidence'] for r in arrival['reports'])
    assert not any(recall['notice_no'] == RYOBI_NOTICE for recall in arrival['recalls'])

    # Later: the notice is revealed only in the window that contains its announcement.
    before = window(client, viewer, '2025-07-01', '2025-07-31', [RYOBI_RULE])
    assert not any(recall['notice_no'] == RYOBI_NOTICE for recall in before['recalls'])
    announced = window(client, viewer, '2025-08-01', '2025-08-31', [RYOBI_RULE])
    recall = next(r for r in announced['recalls'] if r['notice_no'] == RYOBI_NOTICE)
    assert recall['wave'] == RYOBI_NOTICE
    assert recall['announced'] == '2025-08-28'
    covered = {r['id']: r for r in recall['reports']}
    assert covered[RYOBI_REPORT]['flag_by'] == '2025-08-27'
    assert all(RANGE['start'] <= r['published'] <= r['flag_by'] for r in recall['reports'])
    lead = date.fromisoformat(recall['announced']) - date.fromisoformat(report['published'])
    assert lead.days == 869


def test_rolling_counts_see_reports_before_the_replay_start(client, viewer):
    repeat = {'name': 'Repeat model', 'match': 'all', 'action': {'kind': 'watchlist'},
              'conditions': [{'kind': 'count', 'group': 'make_model', 'window_days': 365, 'threshold': 3}]}
    first_days = window(client, viewer, '2023-04-01', '2023-04-07', [repeat])
    flagged = [r for r in first_days['reports'] if r['rules'] == [0]]
    assert flagged, 'Expected a model already reported twice in the prior year'
    shown = {r['id'] for r in first_days['reports']}
    counted = {i for r in flagged for evidence in r['evidence'] for i in evidence.rstrip(')').split(' (')[1].split(', ')}
    assert counted - shown, 'Counts should include reports published before the replay start'


def test_windows_must_stay_inside_the_replay_and_use_arrival_rules(client, viewer):
    def post(**body):
        return client.post('/api/heuristic-lab/replay/window', headers=viewer,
                           json={**RANGE, 'since': '2023-04-01', 'until': '2023-04-30', 'rules': [], **body})
    assert post(since='2023-03-01').status_code == 422
    assert post(until='2023-07-30').status_code == 422
    assert post(rules=[{**RYOBI_RULE, 'trigger': 'end'}]).status_code == 422
    assert post(start='2001-01-01').status_code == 422
