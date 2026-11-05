import re
from collections import defaultdict

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from . import models as m
from .derive import HAZARD_LABELS
from .search import KEY_LABELS, index, reports, summary

TRANSITIONS = {
    'open': {'in_review': {'analyst', 'lead'}},
    'in_review': {'open': {'analyst', 'lead'}, 'escalated': {'lead'}, 'closed': {'lead'}},
    'escalated': {'closed': {'lead'}, 'in_review': {'analyst', 'lead'}},
    'closed': {'open': {'analyst', 'lead'}},
}


def user(conn, user_id):
    row = conn.execute('SELECT id,handle,display_name,role FROM workspace.app_user WHERE id=%s', (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'User not found')
    return m.User(**row)


def audit(conn, actor, action, entity, entity_id, before=None, after=None):
    conn.execute('INSERT INTO workspace.audit_log (actor_id,action,entity,entity_id,before,after) VALUES (%s,%s,%s,%s,%s,%s)', (actor.id, action, entity, str(entity_id), Jsonb(jsonable_encoder(before)), Jsonb(jsonable_encoder(after))))


def review(conn, row):
    return m.RelationReview(**{**row, 'reviewer': user(conn, row['reviewer_id'])})


def note(conn, row):
    return m.Note(**row, author=user(conn, row['author_id']))


def investigation(conn, id, actor, full=True):
    row = conn.execute('SELECT * FROM workspace.investigation WHERE id=%s', (id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Investigation not found')
    members = conn.execute('SELECT * FROM workspace.investigation_incident WHERE investigation_id=%s ORDER BY added_at,report_no', (id,)).fetchall()
    incident_rows = reports(conn, [r['report_no'] for r in members])
    data = {**row, 'assignee': user(conn, row['assignee_id']) if row['assignee_id'] else None, 'created_by': user(conn, row['created_by']), 'incident_count': len(members), 'latest_report_date': max((r['report_date'] for r in incident_rows), default=None)}
    if not full:
        return m.InvestigationSummaryRow(**data)
    data.update(incidents=[m.Member(incident=summary(conn, r), rationale=member['rationale'], added_by=user(conn, member['added_by']), added_at=member['added_at']) for r, member in zip(incident_rows, members)], notes=[note(conn, r) for r in conn.execute('SELECT * FROM workspace.investigation_note WHERE investigation_id=%s ORDER BY created_at DESC,id DESC', (id,))], allowed_transitions=[s for s, roles in TRANSITIONS[row['status']].items() if actor.role in roles])
    return m.Investigation(**data)


def add_members(conn, id, ids, rationale, actor):
    reports(conn, ids)
    changed = False
    for report in dict.fromkeys(ids):
        row = conn.execute('INSERT INTO workspace.investigation_incident (investigation_id,report_no,rationale,added_by) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *', (id, report, rationale, actor.id)).fetchone()
        if row:
            changed = True
            audit(conn, actor, 'member.add', 'investigation', id, after=row)
    if changed:
        conn.execute('UPDATE workspace.investigation SET updated_at=now() WHERE id=%s', (id,))


def patterns(conn, ids):
    rows = reports(conn, ids)
    if not rows:
        return None
    ids = [r['report_no'] for r in rows]
    agreements = []
    for field in ['manufacturer_key', 'brand_key', 'model_key', 'product_code', 'product_category', 'state', 'severity']:
        groups = defaultdict(list)
        for row in rows:
            groups[row[field]].append(row['report_no'])
        label_field = KEY_LABELS.get(field, (None, field))[1]
        labels = {row[field]: row[label_field] or row[field] for row in rows}
        agreements.append({'field': field, 'values': [{'value': value, 'label': labels[value] or 'Not reported', 'report_nos': group} for value, group in sorted(groups.items(), key=lambda p: (-len(p[1]), p[0] or ''))]})
    hazards, severities = defaultdict(list), defaultdict(list)
    for row in rows:
        for hazard in row['hazards']:
            hazards[hazard].append(row['report_no'])
        severities[(row['severity'], row['severity_rank'])].append(row['report_no'])
    return m.PatternAnalysis(report_nos=ids, date_range={'first': min(r['report_date'] for r in rows), 'last': max(r['report_date'] for r in rows)}, shared_terms=index.shared(ids), field_agreement=agreements, hazards=[{'hazard': h, 'label': HAZARD_LABELS[h], 'report_nos': group} for h, group in sorted(hazards.items(), key=lambda p: -len(p[1]))], severity=[{'severity': s, 'rank': rank, 'report_nos': group} for (s, rank), group in sorted(severities.items(), key=lambda p: -p[0][1])], injury_count=sum(r['is_injury'] and r['severity_rank'] != 9 for r in rows), death_count=sum(r['severity_rank'] == 9 for r in rows), method='patterns-tfidf-v1')


HEADINGS = ['Scope', 'Severity', 'Hazard pattern', 'Product concentration', 'Narrative themes', 'Manufacturer responses', 'Analyst notes']
SUMMARY_LABEL = 'Automated summary. Built only from the reports cited. Not an official CPSC finding.'


def generate_summary(conn, id, actor):
    inv = investigation(conn, id, actor)
    ids = [member.incident.report_no for member in inv.incidents]
    analysis = patterns(conn, ids)
    sections = {h: [] for h in HEADINGS}
    def claim(heading, text, citations):
        citations = sorted(set(citations) & set(ids))
        if citations:
            sections[heading].append({'text': text, 'citations': citations})
    if analysis:
        rows = reports(conn, ids)
        claim('Scope', f'{len(ids)} public reports, submitted {analysis.date_range.first} through {analysis.date_range.last}.', ids)
        for group in next(a.values for a in analysis.field_agreement if a.field == 'product_category'):
            claim('Scope', f'{len(group.report_nos)} reports describe products in {group.label}.', group.report_nos)
        claim('Severity', f'{analysis.injury_count} reports describe injury; {analysis.death_count} report death.', ids)
        for hazard in analysis.hazards[:5]:
            evidence = conn.execute('SELECT DISTINCT unnest(evidence) phrase FROM inference.incident_hazard WHERE hazard=%s AND report_no=ANY(%s) LIMIT 8', (hazard.hazard, hazard.report_nos)).fetchall()
            claim('Hazard pattern', f'{hazard.label} inferred in {len(hazard.report_nos)} reports. Matched phrases: ' + ', '.join(r['phrase'] for r in evidence) + '.', hazard.report_nos)
        for field in analysis.field_agreement:
            if field.field in ['model_key', 'brand_key', 'manufacturer_key']:
                for group in field.values:
                    if group.value and len(group.report_nos) >= 2:
                        claim('Product concentration', f'{len(group.report_nos)} reports share {KEY_LABELS[field.field][0]}: {group.label}.', group.report_nos)
        for term in analysis.shared_terms:
            claim('Narrative themes', f'Shared distinctive term "{term.term}" in {len(term.report_nos)} reports.', term.report_nos)
        responses = [r['report_no'] for r in rows if r['has_company_comment']]
        claim('Manufacturer responses', f'{len(responses)} reports have a published company response.', responses)
        for n in inv.notes[:5]:
            claim('Analyst notes', f'{n.author.display_name}: {n.body}', n.cited_report_nos)
    body = {'label': SUMMARY_LABEL, 'sections': [{'heading': h, 'claims': claims} for h, claims in sections.items()], 'member_report_nos': ids}
    row = conn.execute('INSERT INTO workspace.summary_snapshot (investigation_id,method,body,generated_by) VALUES (%s,%s,%s,%s) RETURNING *', (id, 'summary-template-v1', Jsonb(body), actor.id)).fetchone()
    audit(conn, actor, 'summary.generate', 'investigation', id, after={**body, 'snapshot_id': row['id']})
    return snapshot(conn, row)


def snapshot(conn, row):
    return m.SummarySnapshot(**{k: v for k, v in row.items() if k not in ['body', 'generated_by']}, **row['body'], generated_by=user(conn, row['generated_by']))


def cited(body):
    return sorted(set(re.findall(r'\d{8}-[0-9A-F]{5}-\d+', body)))
