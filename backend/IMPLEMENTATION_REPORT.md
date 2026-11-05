# Backend implementation report

Serve the analyst investigation loop over 70,004 real public SaferProducts.gov reports through the agreed FastAPI API.

The service runs at `http://127.0.0.1:8000`. The detached process uses the backend worktree venv. Its log is `/home/ubuntu/cpsc-data/backend.log`. `curl -s -w '\n%{http_code}\n' 127.0.0.1:8000/api/health` returned `{"status":"ok"}` and `200`.

## Implemented endpoints

All paths below have the `/api` prefix.

| Area | Endpoints |
| --- | --- |
| Demo auth | `GET /users`, `POST /session` |
| Incidents | `GET /incidents`, `GET /incidents/facets`, `GET /incidents/export.csv`, `GET /incidents/{report_no}`, `GET /incidents/{report_no}/versions`, `GET /incidents/{report_no}/related` |
| Comparison | `POST /patterns` |
| Relationships | `PUT /relations`, `DELETE /relations/{report_a}/{report_b}` |
| Investigations | `GET /investigations`, `POST /investigations`, `GET /investigations/{id}`, `PATCH /investigations/{id}` |
| Membership | `POST /investigations/{id}/incidents`, `DELETE /investigations/{id}/incidents/{report_no}` |
| Notes and evidence | `POST /investigations/{id}/notes`, `GET /investigations/{id}/audit`, `POST /investigations/{id}/summary`, `GET /investigations/{id}/summaries` |
| Saved searches | `GET /saved-searches`, `POST /saved-searches`, `DELETE /saved-searches/{id}` |
| Analytics | `GET /analytics/trend`, `GET /analytics/breakdown`, `GET /analytics/spikes` |
| Source | `GET /source/status`, `POST /source/sync` |
| Operational | `GET /health` |

The Pydantic models mirror the contract. The status transition table drives permissions and available transitions. One reason registry drives related scores and stored relationship reasons. One filter builder drives search, facets, exports, and analytics. Workspace mutations and audit entries commit together. The TF-IDF matrix and vocabulary are cached in `backend/.data/tfidf-3.pickle`.

## Deviations and contract ambiguities

- The additional health endpoint permits unauthenticated access, as required by the brief's startup check.
- Pattern analysis directly aggregates the shared TF-IDF index and hazard rows rather than invoking the pair-reason scorer. Pattern terms include every qualifying term present in at least two reports, independent of the related scorer's cosine threshold.
- A confirmed relationship with no qualifying automated reasons remains visible with an empty `reasons` list. The contract requires both unconditional visibility for confirmed relationships and nonempty reasons. The service preserves the analyst's confirmation without inventing automated evidence.
- Confirmed relationships can extend the related response beyond `limit` to satisfy the requirement that confirmed relationships always appear.
- Spike `ratio` is recent divided by expected when expected is positive. When the baseline is zero, the finite fallback is recent divided by one. The contract does not define the ratio formula or its zero-baseline behavior. The expected count, window boundaries, minimum count, and z formula follow the contract exactly.
- The sync handler reuses `ingest.sync(None)` and `ingest.rebuild_inference()` as directed. The existing rebuild function truncates and repopulates inference in one transaction. It was not invoked during implementation or tests, so the protected source and inference data were not rewritten. Authorized demo users' workspace data was the only database data changed.

## Verification

`cd backend && .venv/bin/pytest -q` returned:

```text
14 passed, 1 warning in 11.16s
```

Seven API tests exercise the real database through FastAPI TestClient. Seven existing ingestion and derivation tests also pass. The API tests cover OR within filters, AND across filters, relevance ordering, all seven reason kinds and their exact weights, score sums, authentication, role restrictions, illegal transitions, workspace audits, member-only citations, empty membership, facets, raw exports, source versions, shared saved searches, patterns, trend totals, and an independently recounted spike window and baseline.

The warning is Starlette's deprecation notice about its httpx TestClient integration. It does not affect the responses tested. Source sync was not exercised against the external site. Its permission checks were exercised.

Tests remove their investigations, notes, members, summaries, saved searches, relationship reviews, and audit rows. The demonstration investigation remains available as investigation 6, with summary 10. No `[test]` workspace rows remain.

## Performance

The claim tested was that search with text plus two filters takes less than 300 ms server time, related reports take less than 1 s, and a fresh API process with a warm TF-IDF cache starts within 15 s.

`cd backend && .venv/bin/python scripts/measure_api.py` reproduces the measurements. The harness checks response status, nonempty results, filter correctness, and score arithmetic. It runs on the full 70,004-row database. Search and related calls alternate in one TestClient session. Each startup run launches a fresh Python process, imports the application, loads the warm disk cache, and completes a health request. Database and filesystem caches are warm. This is a single-client latency measurement.

| Measurement | Runs | Median | Range | Target |
| --- | --- | --- | --- | --- |
| Search server time | 7 | 230.30 ms | 217.59–264.20 ms | <300 ms |
| Related HTTP through TestClient | 7 | 569.95 ms | 535.47–705.20 ms | <1,000 ms |
| Fresh process with warm TF-IDF cache | 5 | 2,825.85 ms | 2,755.64–2,962.05 ms | <15,000 ms |

The search was `q=fire&hazard=fire&product_category=Kitchen`, with the default 50 results and 7,499 matching reports. Each related call returned 25 reports. There were zero failed requests. The machine had four cores and load averages of 1.01, 0.70, and 0.83 before measurement.

A separate cProfile run found that search spent 190 of 192 ms waiting for PostgreSQL in four batched queries. Related reports spent 392 of 636 ms in pair scoring, primarily sparse TF-IDF multiplication. These profile timings are diagnostic and are not included in the table. Search snippets were batched after the first measurement found repeated per-row headline queries.

## Curl evidence

[evidence/curl.json](evidence/curl.json) records actual curl response excerpts and status codes, without session tokens.

| Request | HTTP | Evidence |
| --- | --- | --- |
| `GET /api/incidents?q=fire&hazard=fire&product_category=Kitchen&page_size=3` | 200 | 7,499 matches, 171.30 ms reported server time in this individual curl run. |
| `GET /api/incidents/20250519-B64E6-2147331216` | 200 | Current source SHA `cb56dc5c48c5f8b503710a0655a52491d69b4d1b0ed10916e146f998ad2dfd08`, bulk batch 1. |
| `GET /api/incidents/20250519-B64E6-2147331216/related?limit=3` | 200 | First match `20250528-94ECE-5311851`, score 0.3938493967, with text, manufacturer, brand, and hazard reasons. |
| `POST /api/investigations/6/summary` | 200 | Snapshot 10, `summary-template-v1`, 23 claims, three cited member reports. |

## Design choices

Model the Domain shaped the transition table, reason registry, and typed request and response models. The benchmark checklist shaped the repeatable harness, response checks, ranges, and separate diagnostic profile.

Implementation and verification ran in this thread because the assigned task is itself an implementation sub-agent task. No further agents were started. No PR was opened and nothing was pushed.
