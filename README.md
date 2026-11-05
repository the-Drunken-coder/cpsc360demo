<img src="assets/icon.svg" width="64" height="64" alt="">

# CPSC360 prototype

A working proof of concept of what CPSC360 could become if it were redesigned around the analyst's investigation loop. It runs on the real public incident reports from SaferProducts.gov, about 70,000 of them.

This is a prototype. It uses public data only, it has no connection to internal CPSC systems, and nothing it produces is an official CPSC record or finding.

## What it does

1. **Explorer.** Full-text search (`"quoted phrase"`, `OR`, `-exclude`) with facet filters, a dense sortable table, and a preview panel that opens without leaving the results. Filters live in the URL, so any view can be shared or saved.
2. **Incident record.** Every reported field, the consumer's narrative verbatim, and the manufacturer's responses. The source record shows the ingest batch, the file hash, and every version received.
3. **Related incidents.** Each suggestion shows its score as a sum of named reasons: same model, same manufacturer, shared hazard, and text similarity with the shared terms. Analysts confirm or reject each one.
4. **Compare.** Reports side by side, with matching fields colored and shared terms and hazards counted.
5. **Investigations.** Group reports with a rationale. Each investigation has notes that link cited reports, labels, an assignee, a status workflow, and an audit trail.
6. **Summary.** A generated summary where every claim lists the reports it counts. It is built from a template, so it cannot cite a report it did not use.
7. **Analytics.** Trends by product, manufacturer, hazard, or severity, a breakdown, and a table of unusual increases. Every bar, point, and row opens the exact reports behind it.

Every value carries its provenance:

| Tier | Meaning |
| --- | --- |
| Reported | Published on SaferProducts.gov. Never edited. |
| Inferred | Produced by a named, versioned method, such as `hazard-rules-v2` or `related-v1`. It can be wrong. |
| Analyst | Created by a prototype user. Attributed and audited. |

Analytics count reports by submission date. They are not incident rates: there is no exposure or sales data, and reporting volume follows awareness and publicity.

## Run it

You need Python 3.12, Node 20 or newer, and Docker.

```sh
scripts/dev-db.sh                                   # Postgres 16 on 127.0.0.1:5433
cd backend
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m cpsc360.ingest init-db
.venv/bin/python -m cpsc360.ingest bulk             # downloads SPDB.zip (~40 MB) and loads it
.venv/bin/python -m cpsc360.ingest sync             # adds reports published since the snapshot
cd ..
scripts/dev-api.sh                                  # API on 127.0.0.1:8000; the first start builds the text index (~1 min)
cd frontend && npm ci && npm run dev                # UI on http://localhost:5173
```

Ingestion commands are idempotent. Rerunning `bulk` or `sync` over the same data changes nothing.

Demo users, with no passwords (prototype only):

| User | Role | Can |
| --- | --- | --- |
| J. Rivera | analyst | Investigate, review relationships, write notes |
| M. Chen | lead | All of the above, plus escalate, close, and sync |
| Read-only viewer | viewer | Read everything, write nothing |

## Tests

```sh
cd backend && .venv/bin/pytest -q        # parser, hazard rules, and the HTTP API against the loaded database
cd frontend && npm test && npm run build
```

`backend/scripts/measure_api.py` measures search, related-incident, and startup latency.

## Layout

- `backend/cpsc360/schema.sql` holds the data model. The `source`, `inference`, and `workspace` schemas hold the three provenance tiers.
- `backend/cpsc360/ingest.py` and `source_csv.py` handle the bulk and incremental loads. `derive.py` holds the matching keys and hazard rules.
- `backend/cpsc360/app.py` serves the API. `search.py` holds the shared filter builder and text index, and `workspace.py` holds investigations, patterns, and summaries.
- `frontend/src` is React, TypeScript, and Blueprint, organized by view.
- `docs/api.md` is the API contract. `docs/data-source.md` records how SaferProducts.gov publishes its data. `docs/decisions.tsv` logs the build decisions.
