import csv
import html
import unicodedata
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


def test_search_snippets_are_verbatim_excerpts_of_the_narrative(client, headers):
    for q in ['fire crews', 'blendjet']:
        items = get(client, headers, '/api/incidents', params={'q': q, 'page_size': 50})['items']
        with connection() as conn:
            rows = conn.execute('SELECT report_no, incident_description FROM source.incident WHERE report_no = ANY(%s)', ([i['report_no'] for i in items],)).fetchall()
        narratives = {r['report_no']: r['incident_description'] for r in rows}
        assert any('<mark>' in item['snippet'] for item in items)
        for item in items:
            excerpt = html.unescape(item['snippet'].replace('<mark>', '').replace('</mark>', ''))
            assert ' '.join(excerpt.split()) in ' '.join(narratives[item['report_no']].split()), item['report_no']


def test_short_models_filter_and_same_model_needs_the_same_maker(client, headers):
    with connection() as conn:
        stored = conn.execute("SELECT count(*) n FROM source.incident WHERE model='GT'").fetchone()['n']
        question = conn.execute("SELECT count(*) n FROM source.incident WHERE btrim(model)='?'").fetchone()['n']
    assert stored > 0 and get(client, headers, '/api/incidents?model=GT')['total'] == stored
    assert get(client, headers, '/api/incidents', params={'model': '?'})['total'] == question
    for origin in ['20221114-11FCC-3978060', '20160302-1C3BE-1558847']:
        maker = get(client, headers, f'/api/incidents/{origin}')['inferred']['manufacturer_key']
        related = get(client, headers, f'/api/incidents/{origin}/related', params={'limit': 200})
        assert all(item['incident']['manufacturer_key'] == maker for item in related if any(r['kind'] == 'same_model' for r in item['reasons']))
    gt = get(client, headers, '/api/incidents?model=GT&page_size=2')['items']
    assert any(r['kind'] == 'same_model' for item in get(client, headers, f"/api/incidents/{gt[0]['report_no']}/related", params={'limit': 200}) for r in item['reasons'])


def test_hazard_drilldown_filter_matches_breakdown_count(client, headers):
    rows = get(client, headers, '/api/analytics/breakdown?hazard=fire&dimension=hazard&limit=30')['rows']
    burn = next(r for r in rows if r['key'] == 'burn')
    assert get(client, headers, '/api/incidents?hazard=fire&hazard_all=burn&page_size=1')['total'] == burn['count']


def test_removing_a_non_member_is_404_and_not_audited(client, headers, workspace_cleanup):
    inv = client.post('/api/investigations', headers=headers['jrivera'], json={'title': '[test] non-member'}).json()
    path = f"/api/investigations/{inv['id']}"
    assert client.delete(path + '/incidents/not-a-report', headers=headers['jrivera']).status_code == 404
    assert [a['action'] for a in get(client, headers, path + '/audit')] == ['investigation.create']


def test_company_responses_split_only_at_line_starts(client, headers):
    detail = get(client, headers, '/api/incidents/20220306-541AF-2147357338')
    assert [c['company'] for c in detail['company_comments']] == ['Bestway Inflatables & Material Corp.']


def test_trend_other_counts_reports_not_hazard_tags(client, headers):
    trend = get(client, headers, '/api/analytics/trend?interval=quarter&group_by=hazard&top=6')
    top = [s['key'] for s in trend['series'] if s['key'] != '__other__']
    other = next(s for s in trend['series'] if s['key'] == '__other__')
    point = next(p for p in other['points'] if p['period'] == '2024-01-01')
    with connection() as conn:
        reports = conn.execute("SELECT count(DISTINCT h.report_no) n FROM inference.incident_hazard h JOIN source.incident i USING (report_no) WHERE i.report_date >= '2024-01-01' AND i.report_date < '2024-04-01' AND h.hazard <> ALL(%s)", (top,)).fetchone()['n']
    assert point['count'] == reports
    assert 'several inferred hazards' in trend['caveat']


def test_concentration_claims_quote_every_cited_spelling(client, headers, workspace_cleanup):
    with connection() as conn:
        rows = conn.execute("SELECT i.report_no, i.model FROM source.incident i JOIN inference.incident_norm n USING (report_no) WHERE n.model_key = 'shapeups' AND n.manufacturer_key = (SELECT manufacturer_key FROM inference.incident_norm WHERE model_key = 'shapeups' GROUP BY 1 ORDER BY count(*) DESC LIMIT 1)").fetchall()
    spellings = {r['model'].strip() for r in rows}
    assert len(spellings) >= 2
    inv = client.post('/api/investigations', headers=headers['jrivera'], json={'title': '[test] spellings', 'report_nos': [r['report_no'] for r in rows]}).json()
    snapshot = client.post(f"/api/investigations/{inv['id']}/summary", headers=headers['jrivera']).json()
    claim = next(c for s in snapshot['sections'] for c in s['claims'] if 'match on model' in c['text'])
    assert all(f'"{s}"' in claim['text'] for s in spellings)


def test_manufacturer_claims_quote_reported_spellings(client, headers, workspace_cleanup):
    ids = ['20111111-C576B-2147473411', '20260410-8290F-2147320766']
    with connection() as conn:
        spellings = {r['manufacturer_name'].strip() for r in conn.execute('SELECT manufacturer_name FROM source.incident WHERE report_no = ANY(%s)', (ids,))}
    assert len(spellings) == 2
    inv = client.post('/api/investigations', headers=headers['jrivera'], json={'title': '[test] maker spellings', 'report_nos': ids}).json()
    snapshot = client.post(f"/api/investigations/{inv['id']}/summary", headers=headers['jrivera']).json()
    claim = next(c for s in snapshot['sections'] for c in s['claims'] if 'match on manufacturer' in c['text'])
    assert all(f'"{s}"' in claim['text'] for s in spellings)


def test_brand_and_model_filters_fold_accents(client, headers):
    with connection() as conn:
        brands = [r['brand'] for r in conn.execute("SELECT brand FROM source.incident WHERE brand ~* 'bj'")]
    fold = lambda b: ''.join(c for c in unicodedata.normalize('NFKD', b.lower()) if c.isascii() and c.isalnum())
    bjorn = sum(fold(b) == 'babybjorn' for b in brands)
    assert bjorn >= 8
    assert get(client, headers, '/api/incidents', params={'brand': 'BabyBjorn'})['total'] == bjorn
    assert get(client, headers, '/api/incidents', params={'brand': 'BABYBJÖRN'})['total'] == bjorn
    assert get(client, headers, '/api/incidents', params={'model': 'Pelotn Tread'})['total'] == 0
