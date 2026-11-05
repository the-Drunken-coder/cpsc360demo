import html
import pickle
import threading
from pathlib import Path

import numpy as np
from fastapi import HTTPException
from psycopg.rows import dict_row
from sklearn.feature_extraction.text import TfidfVectorizer

from . import derive
from .db import connect
from .models import Filters, IncidentSummary, Reason

JOIN = ''' FROM source.incident i
JOIN inference.incident_norm n USING (report_no)
LEFT JOIN inference.manufacturer mf ON mf.manufacturer_key=n.manufacturer_key
LEFT JOIN source.severity_level s ON s.label=i.severity '''
FIELDS = '''i.*, n.manufacturer_key,n.brand_key,n.model_key,n.method,
coalesce(mf.display_name, i.manufacturer_name) manufacturer_display_name,
coalesce(s.rank,0) severity_rank, coalesce(s.is_injury,false) is_injury,
(coalesce(i.company_comments,'') <> '') has_company_comment,
ARRAY(SELECT hazard FROM inference.incident_hazard h WHERE h.report_no=i.report_no ORDER BY hazard) hazards,
ARRAY(SELECT investigation_id FROM workspace.investigation_incident w WHERE w.report_no=i.report_no ORDER BY investigation_id) investigation_ids'''
# Matching compares canonical keys; people read the reported spelling.
KEY_LABELS = {'manufacturer_key': ('manufacturer', 'manufacturer_display_name'), 'brand_key': ('brand', 'brand'), 'model_key': ('model', 'model'), 'product_code': ('product type', 'product_type')}
FACETS = ['product_category', 'product_code', 'manufacturer_key', 'hazard', 'severity', 'state', 'submitter_category']


def connection():
    conn = connect()
    conn.row_factory = dict_row
    return conn


def filters_sql(filters: Filters, omit: str | None = None):
    clauses, args = [], []
    for field in ['product_category', 'product_code', 'manufacturer_key', 'severity', 'state', 'submitter_category']:
        values = getattr(filters, field)
        if values and omit != field:
            alias = 'n' if field == 'manufacturer_key' else 'i'
            clauses.append(f'{alias}.{field} = ANY(%s)')
            args.append(values)
    if filters.hazard and omit != 'hazard':
        clauses.append('EXISTS (SELECT 1 FROM inference.incident_hazard h WHERE h.report_no=i.report_no AND h.hazard=ANY(%s))')
        args.append(filters.hazard)
    for hazard in filters.hazard_all:
        clauses.append('EXISTS (SELECT 1 FROM inference.incident_hazard h WHERE h.report_no=i.report_no AND h.hazard=%s)')
        args.append(hazard)
    for field in ['brand', 'model']:
        value = getattr(filters, field)
        if value is None:
            continue
        if derive.match_text(value):
            clauses.append(f"n.{field}_text = %s")
            args.append(derive.match_text(value))
        else:
            clauses.append(f"lower(btrim(i.{field})) = %s")
            args.append(value.strip().lower())
    if filters.q:
        clauses.append("i.search @@ websearch_to_tsquery('english', %s)")
        args.append(filters.q)
    for field, op in [('report_date_from', '>='), ('report_date_to', '<=')]:
        if getattr(filters, field):
            clauses.append(f'i.report_date {op} %s')
            args.append(getattr(filters, field))
    if filters.injury_only is not None:
        clauses.append('coalesce(s.is_injury,false) = %s')
        args.append(filters.injury_only)
    if filters.has_company_comment is not None:
        clauses.append("(coalesce(i.company_comments,'') <> '') = %s")
        args.append(filters.has_company_comment)
    if filters.in_investigation is not None:
        clauses.append('EXISTS (SELECT 1 FROM workspace.investigation_incident w WHERE w.report_no=i.report_no AND investigation_id=%s)')
        args.append(filters.in_investigation)
    return ' WHERE ' + (' AND '.join(clauses) or 'true'), args


def summaries(conn, filters: Filters, sort=None, limit=50, offset=0):
    where, args = filters_sql(filters)
    total = conn.execute('SELECT count(*) total' + JOIN + where, args).fetchone()['total']
    order = {'report_date': 'i.report_date DESC', '-report_date': 'i.report_date ASC', 'severity': 'coalesce(s.rank,0) DESC', 'publication_date': 'i.publication_date DESC'}
    if filters.q and sort in (None, 'relevance'):
        sorting = "ts_rank_cd(i.search,websearch_to_tsquery('english',%s)) DESC"
        args.append(filters.q)
    else:
        sorting = order.get(sort, order['report_date'])
    rows = conn.execute('SELECT ' + FIELDS + JOIN + where + f' ORDER BY {sorting},i.report_no LIMIT %s OFFSET %s', [*args, limit, offset]).fetchall()
    if filters.q and rows:
        # Headline already-escaped text so tag-like narrative text such as "<ser #123>" survives;
        # alphanumeric sentinels mark matches because ts_headline cannot be given an empty or HTML selector.
        marked = conn.execute("SELECT report_no, ts_headline('english', narrative, websearch_to_tsquery('english',%s), 'StartSel=QQCPSCMARKQQ, StopSel=QQCPSCENDQQ, MaxWords=40, MinWords=20') snippet FROM unnest(%s::text[],%s::text[]) AS t(report_no,narrative)", (filters.q, [r['report_no'] for r in rows], [html.escape(r['incident_description']) for r in rows])).fetchall()
        snippets = {m['report_no']: m['snippet'].replace('QQCPSCMARKQQ', '<mark>').replace('QQCPSCENDQQ', '</mark>') for m in marked}
        for row in rows:
            row['_snippet'] = snippets[row['report_no']]
    return total, [summary(conn, row) for row in rows]


def summary(conn, row):
    snippet = row.get('_snippet', html.escape(row['incident_description'][:240]))
    return IncidentSummary.model_validate({**row, 'snippet': snippet})


def reports(conn, ids):
    rows = conn.execute('SELECT ' + FIELDS + JOIN + ' WHERE i.report_no=ANY(%s)', (list(ids),)).fetchall()
    found = {row['report_no']: row for row in rows}
    if set(ids) - found.keys():
        raise HTTPException(404, 'Report not found: ' + ', '.join(sorted(set(ids) - found.keys())))
    return [found[r] for r in dict.fromkeys(ids)]


class TextIndex:
    def __init__(self):
        self.lock = threading.RLock()
        self.batch = None

    def load(self):
        with self.lock, connection() as conn:
            batch = conn.execute('SELECT max(id) id FROM source.ingest_batch').fetchone()['id']
            if self.batch == batch:
                return
            cache = Path(__file__).resolve().parents[1] / '.data' / f'tfidf-{batch}.pickle'
            if cache.exists():
                with cache.open('rb') as stream:
                    ids, vectorizer, matrix = pickle.load(stream)
            else:
                rows = conn.execute("SELECT report_no, incident_description || ' ' || product_description text FROM source.incident ORDER BY report_no").fetchall()
                ids = [r['report_no'] for r in rows]
                vectorizer = TfidfVectorizer(stop_words='english', sublinear_tf=True, ngram_range=(1, 2), min_df=2, max_df=0.5, dtype=np.float32)
                matrix = vectorizer.fit_transform(r['text'] for r in rows)
                cache.parent.mkdir(exist_ok=True)
                temporary = cache.with_suffix('.tmp')
                with temporary.open('wb') as stream:
                    pickle.dump((ids, vectorizer, matrix), stream, protocol=5)
                temporary.replace(cache)
            self.ids = ids
            self.positions = {report: i for i, report in enumerate(ids)}
            self.matrix = matrix
            self.terms = vectorizer.get_feature_names_out()
            self.batch = batch

    def neighbors(self, report):
        with self.lock:
            scores = (self.matrix @ self.matrix[self.positions[report]].T).toarray().ravel()
            indices = np.argsort(-scores)[:301]
            return {self.ids[i]: float(scores[i]) for i in indices if self.ids[i] != report}

    def pair(self, a, b):
        with self.lock:
            product = self.matrix[self.positions[a]].multiply(self.matrix[self.positions[b]])
            order = np.argsort(-product.data)[:8]
            return float(product.sum()), [str(self.terms[product.indices[i]]) for i in order]

    def shared(self, ids):
        with self.lock:
            subset = self.matrix[[self.positions[r] for r in ids]]
            count = np.asarray((subset > 0).sum(axis=0)).ravel()
            weight = np.asarray(subset.sum(axis=0)).ravel()
            candidates = np.flatnonzero(count >= 2)
            best = candidates[np.argsort(-weight[candidates])[:15]]
            return [{'term': str(self.terms[t]), 'report_nos': [r for r, present in zip(ids, subset[:, t].toarray().ravel()) if present]} for t in best]


index = TextIndex()
REASON_WEIGHTS = {'associated_report': .5, 'same_model': .35, 'text_similarity': .4, 'same_manufacturer': .1, 'same_brand': .05, 'same_product_type': .05, 'shared_hazard': .05}


def pair_reasons(a, b):
    reasons = []
    def add(kind, detail, multiplier=1, **extra):
        reasons.append(Reason(kind=kind, weight=REASON_WEIGHTS[kind] * multiplier, detail=detail, **extra))
    if b['report_no'] in a['associated_report_nos'] or a['report_no'] in b['associated_report_nos']:
        add('associated_report', 'The published reports explicitly associate this pair.')
    if a['model_key'] is not None and (a['model_key'], a['manufacturer_key']) == (b['model_key'], b['manufacturer_key']):
        add('same_model', f"Same model from the same manufacturer: {a['model'].strip()}")
    for field, kind in [('manufacturer_key', 'same_manufacturer'), ('brand_key', 'same_brand'), ('product_code', 'same_product_type')]:
        if a[field] is not None and a[field] == b[field]:
            noun, label_field = KEY_LABELS[field]
            add(kind, f'Same {noun}: {a[label_field] or a[field]}')
    hazards = sorted(set(a['hazards']) & set(b['hazards']))
    if hazards:
        add('shared_hazard', 'Shared inferred hazards: ' + ', '.join(derive.HAZARD_LABELS[h] for h in hazards), min(len(hazards), 2), hazards=hazards)
    cosine, terms = index.pair(a['report_no'], b['report_no'])
    if cosine >= .12:
        add('text_similarity', f'Narrative and product text cosine similarity {cosine:.3f}.', cosine, terms=terms)
    return sorted(reasons, key=lambda r: -r.weight)
