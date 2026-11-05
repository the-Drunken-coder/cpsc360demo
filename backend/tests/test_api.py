import csv
import io
import math

import pytest
from fastapi.testclient import TestClient

from cpsc360.app import app
from cpsc360.search import connection, index


@pytest.fixture(scope='module')
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope='module')
def headers(client):
    return {handle: {'Authorization': 'Bearer '+client.post('/api/session', json={'handle': handle}).json()['token']} for handle in ['jrivera','mchen','viewer']}


@pytest.fixture
def workspace_cleanup():
    with connection() as conn:
        before = conn.execute('SELECT coalesce(max(id),0) id FROM workspace.audit_log').fetchone()['id']
    yield
    with connection() as conn:
        ids = [str(r['id']) for r in conn.execute("SELECT id FROM workspace.investigation WHERE title LIKE '[test]%'")]
        conn.execute("DELETE FROM workspace.investigation WHERE title LIKE '[test]%'")
        conn.execute("DELETE FROM workspace.saved_search WHERE name LIKE '[test]%'")
        conn.execute("DELETE FROM workspace.relation_review WHERE note LIKE '[test]%'")
        conn.execute("DELETE FROM workspace.audit_log WHERE id>%s AND ((entity='investigation' AND entity_id=ANY(%s)) OR (entity='saved_search' AND (before->>'name' LIKE '[test]%%' OR after->>'name' LIKE '[test]%%')) OR (entity='relation' AND (before->>'note' LIKE '[test]%%' OR after->>'note' LIKE '[test]%%')))", (before,ids))


def get(client, headers, path, **kwargs):
    response = client.get(path, headers=headers['jrivera'], **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def test_filter_semantics_and_relevance(client, headers):
    with connection() as conn:
        categories = [r['product_category'] for r in conn.execute('SELECT product_category,count(*) n FROM source.incident GROUP BY 1 ORDER BY n DESC LIMIT 2')]
        state = conn.execute("SELECT state,count(*) n FROM source.incident WHERE state IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 1").fetchone()['state']
        expected = conn.execute("SELECT count(*) n FROM source.incident i WHERE product_category=ANY(%s) AND state=%s AND search @@ websearch_to_tsquery('english','fire')", (categories,state)).fetchone()['n']
        order = [r['report_no'] for r in conn.execute("SELECT report_no FROM source.incident i WHERE product_category=ANY(%s) AND state=%s AND search @@ websearch_to_tsquery('english','fire') ORDER BY ts_rank_cd(search,websearch_to_tsquery('english','fire')) DESC,report_no LIMIT 50", (categories,state))]
    result = get(client, headers, '/api/incidents', params=[('q','fire'),('product_category',categories[0]),('product_category',categories[1]),('state',state)])
    assert result['total'] == expected > 0
    assert [r['report_no'] for r in result['items']] == order
    assert all(r['product_category'] in categories and r['state'] == state for r in result['items'])
    assert any('<mark>' in r['snippet'] for r in result['items'])
    union = get(client, headers, '/api/incidents?hazard=fire&hazard=burn')['total']
    assert union >= get(client, headers, '/api/incidents?hazard=fire')['total']
    assert client.get('/api/incidents?page_size=201',headers=headers['jrivera']).status_code == 422


def test_facets_export_detail_versions(client, headers):
    base = get(client,headers,'/api/incidents/facets')
    filtered = get(client,headers,'/api/incidents/facets?hazard=fire')
    assert base['hazard'] == filtered['hazard']
    item = get(client,headers,'/api/incidents?hazard=fire&page_size=1')['items'][0]
    report = item['report_no']
    detail = get(client,headers,f'/api/incidents/{report}')
    assert detail['reported']['product_description'] == item['product_description']
    assert 'raw' not in detail['source']['versions'][0]
    versions = get(client,headers,f'/api/incidents/{report}/versions')
    assert versions[0]['raw']['Report No.'] == report
    response = client.get('/api/incidents/export.csv?hazard=fire',headers=headers['jrivera'])
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 10000
    assert report in {r['Report No.'] for r in rows}


def test_related_scores(client, headers):
    with connection() as conn:
        candidate = conn.execute('SELECT i.report_no FROM source.incident i JOIN inference.incident_norm n USING(report_no) WHERE cardinality(associated_report_nos)>0 AND model_key IS NOT NULL ORDER BY i.report_date DESC,i.report_no LIMIT 1').fetchone()['report_no']
    results = get(client, headers, f'/api/incidents/{candidate}/related?limit=100')
    assert results
    assert {r['kind'] for result in results for r in result['reasons']} == {'associated_report','same_model','same_brand','same_manufacturer','same_product_type','shared_hazard','text_similarity'}
    for result in results:
        assert result['score'] == pytest.approx(min(1,sum(r['weight'] for r in result['reasons'])))
        assert result['reasons'] == sorted(result['reasons'], key=lambda r: -r['weight'])
        for reason in result['reasons']:
            if reason['kind'] == 'text_similarity':
                cosine,_ = index.pair(candidate,result['incident']['report_no'])
                assert reason['weight'] == pytest.approx(.4*cosine)
            elif reason['kind'] == 'shared_hazard':
                assert reason['weight'] == pytest.approx(.05*min(2,len(reason['hazards'])))
            else:
                assert reason['weight'] == {'associated_report':.5,'same_model':.35,'same_brand':.05,'same_manufacturer':.1,'same_product_type':.05}[reason['kind']]
    assert 'review' in results[0]
    assert 'brand' in results[0]['incident']


def test_auth_status_audit_and_summary(client, headers, workspace_cleanup):
    assert client.get('/api/incidents').status_code == 401
    assert client.get('/api/incidents',headers={'Authorization':'Bearer bad'}).status_code == 401
    assert client.post('/api/investigations',headers=headers['viewer'],json={'title':'[test] forbidden'}).status_code == 403
    ids = [r['report_no'] for r in get(client,headers,'/api/incidents?hazard=fire&page_size=2')['items']]
    response = client.post('/api/investigations', headers=headers['jrivera'], json={'title':'[test] workflow','report_nos':ids})
    assert response.status_code == 200, response.text
    inv = response.json(); path = f"/api/investigations/{inv['id']}"
    assert inv['allowed_transitions'] == ['in_review']
    assert client.patch(path,headers=headers['jrivera'],json={'status':'closed'}).status_code == 409
    assert client.patch(path,headers=headers['jrivera'],json={'status':'in_review'}).status_code == 200
    assert client.patch(path,headers=headers['jrivera'],json={'status':'escalated'}).status_code == 403
    escalated = client.patch(path,headers=headers['mchen'],json={'status':'escalated'})
    assert escalated.status_code == 200
    note = client.post(path+'/notes',headers=headers['jrivera'],json={'body':f'Inspect {ids[0]} alongside 20110101-ABCDE-0.'})
    assert note.status_code == 200
    assert ids[0] in note.json()['cited_report_nos']
    result = client.post(path+'/summary',headers=headers['jrivera'])
    assert result.status_code == 200, result.text
    snapshot = result.json()
    claims = [c for s in snapshot['sections'] for c in s['claims']]
    assert claims and all(c['citations'] and set(c['citations']) <= set(ids) for c in claims)
    assert get(client,headers,path+'/summaries')[0] == snapshot
    assert len(get(client,headers,path+'/audit')) == 7
    for report in ids:
        assert client.delete(path+'/incidents/'+report,headers=headers['jrivera']).status_code == 200
    empty = client.post(path+'/summary',headers=headers['jrivera']).json()
    assert not any(s['claims'] for s in empty['sections'])
    actions = [a['action'] for a in get(client,headers,path+'/audit')]
    assert actions.count('member.remove') == 2 and actions.count('summary.generate') == 2
    assert client.post('/api/source/sync',headers=headers['jrivera']).status_code == 403
    assert client.post('/api/source/sync',headers=headers['viewer']).status_code == 403


def test_relations_saved_search_audits(client, headers, workspace_cleanup):
    ids = [r['report_no'] for r in get(client,headers,'/api/incidents?page_size=2')['items']]
    response = client.put('/api/relations',headers=headers['jrivera'],json={'report_a':ids[0],'report_b':ids[1],'verdict':'confirmed','note':'[test] relation'})
    assert response.status_code == 200, response.text
    review = response.json()
    assert review['report_a'] < review['report_b']
    assert any(r['incident']['report_no'] == ids[1] and r['review']['verdict'] == 'confirmed' for r in get(client,headers,f'/api/incidents/{ids[0]}/related?limit=1'))
    assert client.delete('/api/relations/'+ '/'.join(ids),headers=headers['jrivera']).status_code == 204
    response = client.post('/api/saved-searches',headers=headers['mchen'],json={'name':'[test] shared','query':{'q':'fire','hazard':['fire']}})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['shared']
    assert any(r['id'] == saved['id'] for r in get(client,headers,'/api/saved-searches'))
    assert client.delete(f"/api/saved-searches/{saved['id']}",headers=headers['jrivera']).status_code == 403
    assert client.delete(f"/api/saved-searches/{saved['id']}",headers=headers['mchen']).status_code == 204
    with connection() as conn:
        actions = [r['action'] for r in conn.execute("SELECT action FROM workspace.audit_log WHERE entity IN ('relation','saved_search') ORDER BY id DESC LIMIT 4")]
    assert set(actions) == {'relation.upsert','relation.delete','search.save','search.delete'}


def test_patterns_and_analytics(client, headers):
    ids = [r['report_no'] for r in get(client,headers,'/api/incidents?hazard=fire&page_size=3')['items']]
    response = client.post('/api/patterns',headers=headers['jrivera'],json={'report_nos':ids})
    assert response.status_code == 200, response.text
    pattern = response.json()
    assert pattern['report_nos'] == ids
    assert next(h for h in pattern['hazards'] if h['hazard'] == 'fire')['report_nos'] == ids
    trend = get(client,headers,'/api/analytics/trend?interval=year&group_by=product_category&top=2&hazard=fire')
    assert len(trend['series']) == 3
    assert sum(s['total'] for s in trend['series']) == get(client,headers,'/api/incidents?hazard=fire')['total']
    breakdown = get(client,headers,'/api/analytics/breakdown?dimension=state&hazard=fire')
    assert breakdown['measure'] == 'report_count' and breakdown['caveat']


def test_spikes_hand_checked(client, headers):
    result = get(client, headers, '/api/analytics/spikes?dimension=product_code&window_days=90&min_count=1')
    assert result['rows']
    row = result['rows'][0]
    with connection() as conn:
        recent = conn.execute('SELECT count(*) n FROM source.incident WHERE product_code=%s AND report_date BETWEEN %s AND %s',(row['key'],result['window']['start'],result['window']['end'])).fetchone()['n']
        baseline = conn.execute('SELECT count(*) n FROM source.incident WHERE product_code=%s AND report_date BETWEEN %s AND %s',(row['key'],result['baseline']['start'],result['baseline']['end'])).fetchone()['n']
    expected = baseline*90/365
    assert row['recent_count'] == recent
    assert row['expected_count'] == pytest.approx(expected)
    assert row['z'] == pytest.approx((recent-expected)/math.sqrt(max(expected,1)))
    assert get(client,headers,'/api/incidents',params=[('product_code',row['key']),('report_date_from',result['window']['start']),('report_date_to',result['window']['end'])])['total'] == recent


def test_summary_claims_cite_only_the_reports_they_count(client, headers, workspace_cleanup):
    injured = get(client, headers, '/api/incidents?injury_only=true&page_size=2')['items']
    uninjured = get(client, headers, '/api/incidents?injury_only=false&page_size=1')['items']
    ids = [r['report_no'] for r in injured + uninjured]
    inv = client.post('/api/investigations', headers=headers['jrivera'], json={'title': '[test] citations', 'report_nos': ids}).json()
    snapshot = client.post(f"/api/investigations/{inv['id']}/summary", headers=headers['jrivera']).json()
    severity = next(s['claims'] for s in snapshot['sections'] if s['heading'] == 'Severity')
    injury_claim = next(c for c in severity if 'injury' in c['text'])
    assert injury_claim['text'] == '2 reports describe an injury.'
    assert set(injury_claim['citations']) == {r['report_no'] for r in injured if r['severity'] != 'Death'}
    assert all('..' not in c['text'] and ' 1 reports' not in c['text'] for s in snapshot['sections'] for c in s['claims'])
