import csv
import io
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb

from . import analytics, ingest, models as m, workspace as w
from .derive import HAZARD_LABELS
from .search import FACETS, JOIN, connection, filters_sql, index, pair_reasons, reports, summaries, summary
from .source_csv import COLUMNS, INCIDENT_COLUMNS


@asynccontextmanager
async def lifespan(app):
    with connection() as conn:
        for handle, name, role in [('jrivera', 'J. Rivera', 'analyst'), ('mchen', 'M. Chen', 'lead'), ('viewer', 'Read-only viewer', 'viewer')]:
            row = conn.execute('INSERT INTO workspace.app_user (handle,display_name,role,api_token) VALUES (%s,%s,%s,%s) ON CONFLICT (handle) DO NOTHING RETURNING *', (handle, name, role, secrets.token_urlsafe(32))).fetchone()
            if row:
                actor = m.User(**row)
                w.audit(conn, actor, 'user.seed', 'user', actor.id, after=actor)
    index.load()
    yield


app = FastAPI(title='CPSC360 prototype API', lifespan=lifespan)


@app.exception_handler(psycopg.errors.ForeignKeyViolation)
def bad_reference(request, exc):
    return JSONResponse(status_code=422, content={'detail': 'Referenced report, investigation, or user does not exist.'})


def authenticated(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Bearer token required')
    with connection() as conn:
        row = conn.execute('SELECT * FROM workspace.app_user WHERE api_token=%s', (authorization[7:],)).fetchone()
    if not row:
        raise HTTPException(401, 'Invalid token')
    return m.User(**row)


def writer(actor: Annotated[m.User, Depends(authenticated)]):
    if actor.role == 'viewer':
        raise HTTPException(403, 'Writer role required')
    return actor


def lead(actor: Annotated[m.User, Depends(writer)]):
    if actor.role != 'lead':
        raise HTTPException(403, 'Lead role required')
    return actor


Auth = Annotated[m.User, Depends(authenticated)]
Writer = Annotated[m.User, Depends(writer)]
Lead = Annotated[m.User, Depends(lead)]
FilterQuery = Annotated[m.Filters, Query()]


@app.get('/api/health')
def health():
    with connection() as conn:
        conn.execute('SELECT 1')
    return {'status': 'ok'}


@app.get('/api/users', response_model=list[m.User])
def users():
    with connection() as conn:
        return conn.execute('SELECT * FROM workspace.app_user ORDER BY id').fetchall()


@app.post('/api/session', response_model=m.Session)
def session(body: m.SessionInput):
    with connection() as conn:
        row = conn.execute('SELECT * FROM workspace.app_user WHERE handle=%s', (body.handle,)).fetchone()
        if not row:
            raise HTTPException(401, 'Unknown handle')
        return {'token': row['api_token'], 'user': m.User(**row)}


@app.get('/api/incidents', response_model=m.IncidentPage)
def incidents(actor: Auth, filters: FilterQuery, sort: m.Sort | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    start = time.perf_counter()
    with connection() as conn:
        total, items = summaries(conn, filters, sort, page_size, (page-1)*page_size)
    return m.IncidentPage(total=total, page=page, page_size=page_size, items=items, took_ms=(time.perf_counter()-start)*1000)


@app.get('/api/incidents/facets', response_model=dict[str, list[m.FacetValue]])
def facets(actor: Auth, filters: FilterQuery):
    result = {}
    with connection() as conn:
        for field in FACETS:
            expression, extra = analytics.grouping(field)
            where, args = filters_sql(filters, field)
            rows = conn.execute(f'SELECT {expression} value,count(*) count' + JOIN + extra + where + f' AND {expression} IS NOT NULL GROUP BY 1 ORDER BY count DESC,value LIMIT 30', args).fetchall()
            result[field] = [{**r, 'label': analytics.label(conn, field, r['value'])} for r in rows]
    return result


@app.get('/api/incidents/export.csv')
def export(actor: Auth, filters: FilterQuery):
    where, args = filters_sql(filters)
    with connection() as conn:
        rows = conn.execute('SELECT v.raw' + JOIN + ' JOIN source.incident_version v ON v.report_no=i.report_no AND v.row_sha256=i.current_sha256' + where + ' ORDER BY i.report_date DESC,i.report_no LIMIT 10000', args).fetchall()
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(COLUMNS))
    writer.writeheader()
    writer.writerows(r['raw'] for r in rows)
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="incidents.csv"'})


def versions(conn, report_no, raw):
    rows = conn.execute('SELECT v.*,row_to_json(b) batch FROM source.incident_version v JOIN source.ingest_batch b ON b.id=v.batch_id WHERE report_no=%s ORDER BY first_seen_at DESC', (report_no,)).fetchall()
    return [m.SourceVersion(**{k: v for k, v in row.items() if raw or k != 'raw'}) for row in rows]


@app.get('/api/incidents/{report_no}/versions', response_model=list[m.SourceVersion], response_model_exclude_unset=True)
def incident_versions(report_no: str, actor: Auth):
    with connection() as conn:
        reports(conn, [report_no])
        return versions(conn, report_no, True)


@app.get('/api/incidents/{report_no}', response_model=m.IncidentDetail, response_model_exclude_unset=True)
def detail(report_no: str, actor: Auth):
    with connection() as conn:
        row = reports(conn, [report_no])[0]
        hazards = conn.execute('SELECT * FROM inference.incident_hazard WHERE report_no=%s ORDER BY hazard', (report_no,)).fetchall()
        manufacturer = conn.execute('SELECT display_name FROM inference.manufacturer WHERE manufacturer_key=%s', (row['manufacturer_key'],)).fetchone()
        investigations = conn.execute('SELECT v.id,v.title,v.status FROM workspace.investigation v JOIN workspace.investigation_incident i ON i.investigation_id=v.id WHERE i.report_no=%s ORDER BY v.updated_at DESC', (report_no,)).fetchall()
        reviews = conn.execute('SELECT * FROM workspace.relation_review WHERE report_a=%s OR report_b=%s', (report_no, report_no)).fetchall()
        batch = conn.execute('SELECT * FROM source.ingest_batch WHERE id=%s', (row['batch_id'],)).fetchone()
        comments = parse_comments(row['company_comments'])
        return m.IncidentDetail(reported={k: row[k] for k in INCIDENT_COLUMNS}, company_comments=comments, inferred={**row, 'hazards': [{**h, 'label': HAZARD_LABELS[h['hazard']]} for h in hazards], 'manufacturer_display_name': manufacturer['display_name'] if manufacturer else row['manufacturer_name']}, analyst={'investigations': investigations, 'relation_reviews': [w.review(conn, r) for r in reviews]}, source={'current_sha256': row['current_sha256'], 'batch': batch, 'versions': versions(conn, report_no, False), 'public_search_url': 'https://www.saferproducts.gov/PublicSearch', 'disclaimer': DISCLAIMER})


DISCLAIMER = (Path(__file__).with_name('disclaimer.txt')).read_text().strip()


def parse_comments(text):
    if not text:
        return []
    matches = list(re.finditer(r'(?:^|\n)\s*\((\d{1,2}/\d{1,2}/\d{4})\)\s*([^:\n]+):', text))
    if not matches:
        company, sep, body = text.partition(':')
        return [{'date': None, 'company': company.strip() if sep else None, 'text': body.strip() if sep else text}]
    return [{'date': datetime.strptime(match[1], '%m/%d/%Y').date(), 'company': match[2].strip(), 'text': text[match.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()} for i, match in enumerate(matches)]


@app.get('/api/incidents/{report_no}/related', response_model=list[m.RelatedIncident], response_model_exclude_unset=True)
def related(report_no: str, actor: Auth, limit: int = Query(25, ge=1, le=200)):
    with connection() as conn:
        origin = reports(conn, [report_no])[0]
        candidates = set(index.neighbors(report_no))
        if origin['model_key']:
            candidates.update(r['report_no'] for r in conn.execute('SELECT report_no FROM inference.incident_norm WHERE model_key=%s ORDER BY report_no LIMIT 200', (origin['model_key'],)))
        candidates.update(r['report_no'] for r in conn.execute('SELECT report_no FROM source.incident WHERE report_no=ANY(%s) OR %s=ANY(associated_report_nos)', (origin['associated_report_nos'], report_no)))
        review_rows = conn.execute('SELECT * FROM workspace.relation_review WHERE report_a=%s OR report_b=%s', (report_no, report_no)).fetchall()
        reviews = {r['report_b'] if r['report_a'] == report_no else r['report_a']: w.review(conn, r) for r in review_rows}
        confirmed = {other for other, review in reviews.items() if review.verdict == 'confirmed'}
        candidates.update(confirmed)
        candidates.discard(report_no)
        result = []
        for row in reports(conn, sorted(candidates)):
            reasons = pair_reasons(origin, row)
            score = min(1, sum(r.weight for r in reasons))
            if score >= .15 or row['report_no'] in confirmed:
                result.append(m.RelatedIncident(incident=summary(conn, row), score=score, reasons=reasons, method='related-v1', review=reviews.get(row['report_no'])))
        result.sort(key=lambda r: (-r.score, r.incident.report_no))
        selected = result[:limit]
        selected_ids = {r.incident.report_no for r in selected}
        selected.extend(r for r in result if r.incident.report_no in confirmed and r.incident.report_no not in selected_ids)
        return sorted(selected, key=lambda r: (-r.score, r.incident.report_no))


@app.put('/api/relations', response_model=m.RelationReview, response_model_exclude_unset=True)
def put_relation(body: m.RelationInput, actor: Writer):
    a, b = sorted([body.report_a, body.report_b])
    if a == b:
        raise HTTPException(422, 'A relationship requires two distinct reports')
    with connection() as conn:
        rows = reports(conn, [a, b])
        reasons = [r.model_dump(exclude_none=True) for r in pair_reasons(*rows)]
        before = conn.execute('SELECT * FROM workspace.relation_review WHERE report_a=%s AND report_b=%s', (a,b)).fetchone()
        row = conn.execute('INSERT INTO workspace.relation_review (report_a,report_b,verdict,note,reasons_snapshot,reviewer_id) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (report_a,report_b) DO UPDATE SET verdict=excluded.verdict,note=excluded.note,reasons_snapshot=excluded.reasons_snapshot,reviewer_id=excluded.reviewer_id,reviewed_at=now() RETURNING *', (a,b,body.verdict,body.note,Jsonb(reasons),actor.id)).fetchone()
        w.audit(conn, actor, 'relation.upsert', 'relation', a+'/'+b, before, row)
        return w.review(conn, row)


@app.delete('/api/relations/{report_a}/{report_b}', status_code=204)
def delete_relation(report_a: str, report_b: str, actor: Writer):
    a,b = sorted([report_a,report_b])
    with connection() as conn:
        before = conn.execute('DELETE FROM workspace.relation_review WHERE report_a=%s AND report_b=%s RETURNING *', (a,b)).fetchone()
        w.audit(conn, actor, 'relation.delete', 'relation', a+'/'+b, before)
    return Response(status_code=204)


@app.post('/api/patterns', response_model=m.PatternAnalysis)
def pattern(body: m.ReportSelection, actor: Auth):
    if len(set(body.report_nos)) < 2:
        raise HTTPException(422, 'Select at least two distinct reports')
    with connection() as conn:
        return w.patterns(conn, body.report_nos)


@app.get('/api/investigations', response_model=list[m.InvestigationSummaryRow])
def investigations(actor: Auth, status: m.Status | None = None, assignee_id: int | None = None, label: str | None = None):
    with connection() as conn:
        ids = conn.execute('SELECT id FROM workspace.investigation WHERE (%s::text IS NULL OR status=%s) AND (%s::bigint IS NULL OR assignee_id=%s) AND (%s::text IS NULL OR %s=ANY(labels)) ORDER BY updated_at DESC,id DESC', (status,status,assignee_id,assignee_id,label,label)).fetchall()
        return [w.investigation(conn, r['id'], actor, False) for r in ids]


@app.post('/api/investigations', response_model=m.Investigation)
def create_investigation(body: m.InvestigationCreate, actor: Writer):
    with connection() as conn:
        row = conn.execute('INSERT INTO workspace.investigation (title,description,labels,assignee_id,created_by) VALUES (%s,%s,%s,%s,%s) RETURNING *', (body.title,body.description,body.labels,body.assignee_id,actor.id)).fetchone()
        w.audit(conn, actor, 'investigation.create', 'investigation', row['id'], after=row)
        w.add_members(conn, row['id'], body.report_nos, body.rationale, actor)
        return w.investigation(conn, row['id'], actor)


@app.get('/api/investigations/{id}', response_model=m.Investigation)
def get_investigation(id: int, actor: Auth):
    with connection() as conn:
        return w.investigation(conn, id, actor)


@app.patch('/api/investigations/{id}', response_model=m.Investigation)
def patch_investigation(id: int, body: m.InvestigationPatch, actor: Writer):
    with connection() as conn:
        before = conn.execute('SELECT * FROM workspace.investigation WHERE id=%s FOR UPDATE', (id,)).fetchone()
        if not before:
            raise HTTPException(404, 'Investigation not found')
        fields = body.model_dump(exclude_unset=True)
        if 'status' in fields and fields['status'] != before['status']:
            roles = w.TRANSITIONS[before['status']].get(fields['status'])
            if roles is None:
                raise HTTPException(409, 'Illegal status transition')
            if actor.role not in roles:
                raise HTTPException(403, 'Lead role required for this transition')
        for field, value in fields.items():
            if value is None and field != 'assignee_id':
                raise HTTPException(422, f'{field} cannot be null')
        if fields:
            conn.execute('UPDATE workspace.investigation SET '+ ','.join(f'{field}=%s' for field in fields) + ',updated_at=now() WHERE id=%s', [*fields.values(),id])
        after = w.investigation(conn, id, actor)
        w.audit(conn, actor, 'investigation.update', 'investigation', id, before, after)
        return after


@app.post('/api/investigations/{id}/incidents', response_model=m.Investigation)
def add_incidents(id: int, body: m.MembersInput, actor: Writer):
    with connection() as conn:
        w.investigation(conn, id, actor)
        w.add_members(conn, id, body.report_nos, body.rationale, actor)
        return w.investigation(conn, id, actor)


@app.delete('/api/investigations/{id}/incidents/{report_no}', response_model=m.Investigation)
def remove_incident(id: int, report_no: str, actor: Writer):
    with connection() as conn:
        w.investigation(conn, id, actor)
        before = conn.execute('DELETE FROM workspace.investigation_incident WHERE investigation_id=%s AND report_no=%s RETURNING *', (id,report_no)).fetchone()
        if before is None:
            raise HTTPException(404, f'{report_no} is not in investigation {id}')
        conn.execute('UPDATE workspace.investigation SET updated_at=now() WHERE id=%s', (id,))
        w.audit(conn, actor, 'member.remove', 'investigation', id, before)
        return w.investigation(conn, id, actor)


@app.post('/api/investigations/{id}/notes', response_model=m.Note)
def create_note(id: int, body: m.NoteInput, actor: Writer):
    with connection() as conn:
        w.investigation(conn, id, actor)
        row = conn.execute('INSERT INTO workspace.investigation_note (investigation_id,author_id,body,cited_report_nos) VALUES (%s,%s,%s,%s) RETURNING *', (id,actor.id,body.body,w.cited(body.body))).fetchone()
        conn.execute('UPDATE workspace.investigation SET updated_at=now() WHERE id=%s', (id,))
        w.audit(conn, actor, 'note.create', 'investigation', id, after=row)
        return w.note(conn, row)


@app.get('/api/investigations/{id}/audit', response_model=list[m.AuditEntry])
def audit_entries(id: int, actor: Auth):
    with connection() as conn:
        w.investigation(conn, id, actor)
        rows = conn.execute("SELECT * FROM workspace.audit_log WHERE entity='investigation' AND entity_id=%s ORDER BY at DESC,id DESC", (str(id),)).fetchall()
        return [{**r, 'actor': w.user(conn, r['actor_id'])} for r in rows]


@app.post('/api/investigations/{id}/summary', response_model=m.SummarySnapshot)
def generate_summary(id: int, actor: Writer):
    with connection() as conn:
        return w.generate_summary(conn, id, actor)


@app.get('/api/investigations/{id}/summaries', response_model=list[m.SummarySnapshot])
def get_summaries(id: int, actor: Auth):
    with connection() as conn:
        w.investigation(conn, id, actor)
        return [w.snapshot(conn, row) for row in conn.execute('SELECT * FROM workspace.summary_snapshot WHERE investigation_id=%s ORDER BY generated_at DESC,id DESC', (id,))]


def saved(conn, row):
    owner = w.user(conn, row['owner_id'])
    return m.SavedSearch(**row, owner=owner, shared=owner.role == 'lead')


@app.get('/api/saved-searches', response_model=list[m.SavedSearch], response_model_exclude_unset=True)
def saved_searches(actor: Auth):
    with connection() as conn:
        return [saved(conn, row) for row in conn.execute("SELECT s.* FROM workspace.saved_search s JOIN workspace.app_user u ON u.id=s.owner_id WHERE owner_id=%s OR u.role='lead' ORDER BY created_at DESC,id DESC", (actor.id,))]


@app.post('/api/saved-searches', response_model=m.SavedSearch, response_model_exclude_unset=True)
def save_search(body: m.SavedSearchInput, actor: Writer):
    with connection() as conn:
        row = conn.execute('INSERT INTO workspace.saved_search (owner_id,name,query) VALUES (%s,%s,%s) RETURNING *', (actor.id,body.name,Jsonb(body.query.model_dump(mode='json', exclude_unset=True)))).fetchone()
        w.audit(conn, actor, 'search.save', 'saved_search', row['id'], after=row)
        return saved(conn, row)


@app.delete('/api/saved-searches/{id}', status_code=204)
def delete_search(id: int, actor: Writer):
    with connection() as conn:
        row = conn.execute('SELECT * FROM workspace.saved_search WHERE id=%s FOR UPDATE', (id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Saved search not found')
        if row['owner_id'] != actor.id:
            raise HTTPException(403, 'Owner role required')
        conn.execute('DELETE FROM workspace.saved_search WHERE id=%s', (id,))
        w.audit(conn, actor, 'search.delete', 'saved_search', id, before=row)
    return Response(status_code=204)


@app.get('/api/analytics/trend', response_model=m.Trend)
def trend(actor: Auth, filters: FilterQuery, interval: Literal['month','quarter','year'] = 'month', group_by: Literal['none','product_category','product_code','manufacturer_key','hazard','severity'] = 'none', top: int = Query(6, ge=1, le=30)):
    with connection() as conn:
        return analytics.trend(conn, filters, interval, group_by, top)


@app.get('/api/analytics/breakdown', response_model=m.Breakdown)
def breakdown(actor: Auth, filters: FilterQuery, dimension: Literal['product_category','product_code','manufacturer_key','hazard','severity','state'] = 'product_category', limit: int = Query(20, ge=1, le=200)):
    with connection() as conn:
        return analytics.breakdown(conn, filters, dimension, limit)


@app.get('/api/analytics/spikes', response_model=m.Spikes)
def spikes(actor: Auth, dimension: Literal['product_code','manufacturer_key','hazard'] = 'product_code', window_days: int = Query(90, ge=1, le=730), min_count: int = Query(8, ge=1), limit: int = Query(25, ge=1, le=200)):
    with connection() as conn:
        return analytics.spikes(conn, dimension, window_days, min_count, limit)


@app.get('/api/source/status', response_model=m.SourceStatus)
def source_status(actor: Auth):
    with connection() as conn:
        row = conn.execute('SELECT count(*) incident_count,max(report_date) newest_report_date,max(publication_date) newest_publication_date FROM source.incident').fetchone()
        return {**row, 'batches': conn.execute('SELECT * FROM source.ingest_batch ORDER BY id DESC LIMIT 20').fetchall()}


@app.post('/api/source/sync', response_model=list[m.IngestBatch])
def sync_source(actor: Lead):
    try:
        result = ingest.sync(None)
        ingest.rebuild_inference()
        index.load()
    except Exception as exc:
        raise HTTPException(502, 'Public source sync failed') from exc
    with connection() as conn:
        ids = [r['batch_id'] for r in result]
        return conn.execute('SELECT * FROM source.ingest_batch WHERE id=ANY(%s) ORDER BY id', (ids,)).fetchall()
