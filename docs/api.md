# CPSC360 prototype API contract

FastAPI serves everything under `/api` on `http://127.0.0.1:8000`. The frontend dev server proxies `/api` there. JSON everywhere. Dates are ISO `YYYY-MM-DD`, timestamps ISO 8601 UTC.

This document is the contract between `backend/` and `frontend/`. The types below are TypeScript. The backend mirrors them with Pydantic models, field for field, in snake_case exactly as written.

## Provenance

Every value the UI shows belongs to one tier, and the UI must label it.

| Tier | Meaning | Where it lives |
| --- | --- | --- |
| `reported` | Text and fields as published on SaferProducts.gov. Never edited. | `source` schema |
| `inferred` | Produced by an automated method. Each carries `method`. May be wrong. | `inference` schema, or computed per request |
| `analyst` | Created by a prototype user. Attributed and audited. | `workspace` schema |

## Auth

Prototype auth only. No passwords. Three seeded demo users:

| handle | display_name | role |
| --- | --- | --- |
| `jrivera` | J. Rivera | `analyst` |
| `mchen` | M. Chen | `lead` |
| `viewer` | Read-only viewer | `viewer` |

- `GET /api/users` -> `User[]` (no auth needed, feeds the user switcher).
- `POST /api/session {handle}` -> `{token: string, user: User}`.
- Every other endpoint takes `Authorization: Bearer <token>`. Missing or bad token is `401`.
- `viewer` gets `403` on every write. `analyst` and `lead` can write. Only `lead` may set status `escalated` or `closed`, and only `lead` may trigger a sync.
- Every write to `workspace` appends an `AuditEntry`.

```ts
type Role = "analyst" | "lead" | "viewer";
interface User { id: number; handle: string; display_name: string; role: Role }
```

## Incidents

```ts
type HazardKey = "fire" | "overheating" | "electrical" | "burn" | "shatter_explosion" | "laceration" | "choking"
  | "suffocation" | "entrapment" | "fall" | "tip_over" | "chemical" | "structural" | "battery" | "drowning";

interface HazardTag { hazard: HazardKey; label: string; evidence: string[]; method: string } // inferred

interface IncidentSummary {
  report_no: string;
  report_date: string;
  publication_date: string;
  product_description: string;     // reported, untruncated
  product_category: string;
  product_type: string | null;
  product_code: string;
  manufacturer_name: string;       // reported spelling
  manufacturer_key: string;        // inferred canonical key
  brand: string | null;
  model: string | null;
  severity: string;                // reported label, e.g. "Injury, Hospital Admission"
  severity_rank: number;           // 0..9, from source.severity_level
  is_injury: boolean;
  state: string | null;
  victim_age: number | null;
  has_company_comment: boolean;
  hazards: HazardKey[];            // inferred
  snippet: string;                 // HTML-escaped excerpt of the narrative; the only markup is <mark> around query matches
  investigation_ids: number[];     // analyst
}

interface Filters {
  q?: string;                      // websearch_to_tsquery syntax: "quoted phrase", OR, -exclude
  product_category?: string[];
  product_code?: string[];
  manufacturer_key?: string[];
  brand?: string;                  // case-insensitive equality on brand_key
  model?: string;                  // case-insensitive equality on model_key
  hazard?: HazardKey[];
  severity?: string[];
  state?: string[];
  submitter_category?: string[];
  report_date_from?: string;
  report_date_to?: string;
  injury_only?: boolean;
  has_company_comment?: boolean;
  in_investigation?: number;       // only members of this investigation
}
```

Array filters are repeated query params (`?hazard=fire&hazard=burn`). Values within one filter OR together. Different filters AND together.

- `GET /api/incidents?{Filters}&sort=&page=1&page_size=50` -> `{total: number, page: number, page_size: number, items: IncidentSummary[], took_ms: number}`
  - `sort`: `relevance` (default when `q` set), `report_date` (default otherwise, desc), `-report_date` (asc), `severity` (desc rank), `publication_date`. `page_size` max 200.
- `GET /api/incidents/facets?{Filters}` -> `Record<FacetField, {value: string, label: string, count: number}[]>`
  - `FacetField` = `product_category | product_code | manufacturer_key | hazard | severity | state | submitter_category`. Top 30 values each, counts under the current filters except the facet's own filter.
- `GET /api/incidents/export.csv?{Filters}` -> CSV of the matching reports' current raw rows, original headers, max 10,000 rows.
- `GET /api/incidents/{report_no}` -> `IncidentDetail`
- `GET /api/incidents/{report_no}/versions` -> `SourceVersion[]` with `raw` included

```ts
interface CompanyComment { date: string | null; company: string | null; text: string } // parsed from reported company_comments

interface IncidentDetail {
  reported: {                       // every column of source.incident except search, verbatim
    report_no: string; report_date: string; sent_to_manufacturer_date: string | null; publication_date: string;
    submitter_category: string; product_description: string; product_category: string; product_subcategory: string;
    product_type: string | null; product_code: string; manufacturer_name: string; brand: string | null;
    model: string | null; serial_number: string | null; upc: string | null; date_manufactured: string | null;
    manufacturer_date_code: string | null; retailer: string | null; retailer_state: string | null;
    purchase_date: string | null; purchase_date_is_estimate: boolean; incident_description: string;
    city: string | null; state: string | null; zip: string | null; location: string | null; severity: string;
    victim_sex: string | null; relation_to_victim: string | null; victim_age: number | null;
    submitter_has_product: boolean | null; damaged_before_incident: boolean | null; damage_description: string | null;
    damage_repaired: boolean | null; modified_before_incident: boolean | null; contacted_manufacturer: boolean | null;
    plans_to_contact: boolean | null; answer_explanation: string | null; company_comments: string | null;
    associated_report_nos: string[];
  };
  company_comments: CompanyComment[];
  inferred: {
    hazards: HazardTag[];
    manufacturer_key: string; manufacturer_display_name: string;
    brand_key: string | null; model_key: string | null; method: string;
  };
  analyst: {
    investigations: {id: number; title: string; status: InvestigationStatus}[];
    relation_reviews: RelationReview[];   // reviews where this report is a or b
  };
  source: {
    current_sha256: string;
    batch: IngestBatch;                   // batch that supplied the current version
    versions: SourceVersion[];            // without raw
    public_search_url: "https://www.saferproducts.gov/PublicSearch";
    disclaimer: string;                   // the CPSC disclaimer text, verbatim
  };
}

interface SourceVersion { row_sha256: string; first_seen_at: string; batch: IngestBatch; raw?: Record<string, string> }
interface IngestBatch { id: number; kind: "bulk" | "incremental"; source_url: string; params: Record<string, string>;
  file_sha256: string; started_at: string; finished_at: string | null; row_count: number | null;
  inserted: number | null; updated: number | null; unchanged: number | null; kept_bulk: number | null }
```

## Related incidents

- `GET /api/incidents/{report_no}/related?limit=25` -> `RelatedIncident[]`, best first.

```ts
type ReasonKind = "associated_report" | "same_model" | "same_brand" | "same_manufacturer" | "same_product_type"
  | "shared_hazard" | "text_similarity";

interface Reason {
  kind: ReasonKind;
  weight: number;              // contribution to score
  detail: string;              // human sentence, e.g. "Same model number: WRF555SDFZ"
  terms?: string[];            // text_similarity: top shared distinctive terms
  hazards?: HazardKey[];       // shared_hazard
}

interface RelatedIncident {
  incident: IncidentSummary;
  score: number;               // sum of reason weights, 0..1 after clamping
  reasons: Reason[];           // nonempty, sorted by weight desc
  method: string;              // e.g. "related-v1"
  review: RelationReview | null;
}

interface RelationReview {
  report_a: string; report_b: string;            // report_a < report_b
  verdict: "confirmed" | "rejected"; note: string;
  reasons_snapshot: Reason[];
  reviewer: User; reviewed_at: string;
}
```

Scoring `related-v1` is additive and fixed, so every score can be recomputed by hand from its reasons:

| kind | weight | condition |
| --- | --- | --- |
| `associated_report` | 0.50 | either report lists the other in Associated Report Numbers |
| `same_model` | 0.35 | equal non-null `model_key` |
| `text_similarity` | 0.40 x cosine | TF-IDF cosine of narrative + product description, shown when cosine >= 0.12 |
| `same_manufacturer` | 0.10 | equal `manufacturer_key` |
| `same_brand` | 0.05 | equal non-null `brand_key` |
| `same_product_type` | 0.05 | equal `product_code` |
| `shared_hazard` | 0.05 per shared hazard, max 0.10 | intersecting hazard tags |

Candidates are the union of the 300 nearest TF-IDF neighbours, up to 200 same-model reports, and associated reports. Results need score >= 0.15. Confirmed relationships always appear, even below threshold, with their review attached.

- `PUT /api/relations` `{report_a, report_b, verdict, note}` -> `RelationReview`. The server orders the pair, recomputes the reasons, and stores them as `reasons_snapshot`. Upsert, audited.
- `DELETE /api/relations/{report_a}/{report_b}` -> `204`. Audited.

## Comparison and patterns

- `POST /api/patterns {report_nos: string[]}` (2..50) -> `PatternAnalysis`. Used by the compare view and the summary generator.

```ts
interface PatternAnalysis {
  report_nos: string[];
  date_range: {first: string; last: string};
  shared_terms: {term: string; report_nos: string[]}[];      // inferred: distinctive TF-IDF terms present in >= 2 reports, top 15
  field_agreement: {field: "manufacturer_key" | "brand_key" | "model_key" | "product_code" | "product_category" | "state" | "severity";
                    values: {value: string | null; label: string; report_nos: string[]}[]}[];
  hazards: {hazard: HazardKey; label: string; report_nos: string[]}[];
  severity: {severity: string; rank: number; report_nos: string[]}[];
  injury_count: number; death_count: number;
  method: string;
}
```

## Investigations

```ts
type InvestigationStatus = "open" | "in_review" | "escalated" | "closed";

interface InvestigationSummaryRow {
  id: number; title: string; status: InvestigationStatus; labels: string[];
  assignee: User | null; created_by: User; created_at: string; updated_at: string;
  incident_count: number; latest_report_date: string | null;
}

interface Investigation extends InvestigationSummaryRow {
  description: string;
  incidents: {incident: IncidentSummary; rationale: string; added_by: User; added_at: string}[];
  notes: Note[];
  allowed_transitions: InvestigationStatus[];   // for the current user
}

interface Note { id: number; author: User; body: string; cited_report_nos: string[]; created_at: string }
```

Status machine: `open -> in_review`, `in_review -> open | escalated | closed`, `escalated -> closed | in_review`, `closed -> open`. An illegal transition is `409`.

- `GET /api/investigations?status=&assignee_id=&label=` -> `InvestigationSummaryRow[]`, newest updated first.
- `POST /api/investigations {title, description?, labels?, assignee_id?, report_nos?, rationale?}` -> `Investigation`.
- `GET /api/investigations/{id}` -> `Investigation`.
- `PATCH /api/investigations/{id} {title?, description?, labels?, assignee_id?, status?}` -> `Investigation`.
- `POST /api/investigations/{id}/incidents {report_nos: string[], rationale?}` -> `Investigation`. Already-present reports are a no-op.
- `DELETE /api/investigations/{id}/incidents/{report_no}` -> `Investigation`.
- `POST /api/investigations/{id}/notes {body}` -> `Note`. The server extracts report numbers (`\d{8}-[0-9A-F]{5}-\d+`) from the body into `cited_report_nos`.
- `GET /api/investigations/{id}/audit` -> `AuditEntry[]`, newest first.
- `POST /api/investigations/{id}/summary` -> `SummarySnapshot`. Stored.
- `GET /api/investigations/{id}/summaries` -> `SummarySnapshot[]`, newest first.

```ts
interface AuditEntry { id: number; at: string; actor: User; action: string; entity: string; entity_id: string;
  before: unknown | null; after: unknown | null }

interface SummaryClaim { text: string; citations: string[] }   // every citation is a member report_no
interface SummarySnapshot {
  id: number; investigation_id: number; generated_at: string; generated_by: User;
  method: string;                 // "summary-template-v1": deterministic, built from PatternAnalysis and member data
  label: string;                  // "Automated summary. Built only from the reports cited. Not an official CPSC finding."
  sections: {heading: string; claims: SummaryClaim[]}[];
  member_report_nos: string[];    // membership when generated
}
```

The summary has these sections: Scope (count, date range, products), Severity (injury and death counts), Hazard pattern (top inferred hazards with the phrases that triggered them), Product concentration (shared model, brand, manufacturer), Narrative themes (shared distinctive terms), Manufacturer responses (reports with company comments), Analyst notes (latest notes, attributed). Every claim cites the reports it counts. A claim with no supporting reports is omitted.

## Saved searches

- `GET /api/saved-searches` -> `SavedSearch[]` (own, plus every lead's, marked `shared`)
- `POST /api/saved-searches {name, query: Filters & {sort?: string}}` -> `SavedSearch`
- `DELETE /api/saved-searches/{id}` -> `204` (owner only)

```ts
interface SavedSearch { id: number; name: string; query: Filters & {sort?: string}; owner: User; created_at: string; shared: boolean }
```

## Analytics

Every analytics response carries `measure: "report_count"` and `caveat`. The caveat says these are counts of public reports by report date. They are not incident rates. No exposure or sales data exists, reporting volume depends on awareness and publicity, and the most recent ~30 days are incomplete because publication lags submission.

- `GET /api/analytics/trend?{Filters}&interval=month|quarter|year&group_by=none|product_category|product_code|manufacturer_key|hazard|severity&top=6`
  -> `{measure, caveat, interval, series: {key: string, label: string, points: {period: string, count: number}[], total: number}[], incomplete_after: string}`.
  With `group_by` the top `top` groups by total get series and the rest fold into `key: "__other__"`. `period` is the period's first day.
- `GET /api/analytics/breakdown?{Filters}&dimension=product_category|product_code|manufacturer_key|hazard|severity|state&limit=20`
  -> `{measure, caveat, dimension, rows: {key: string, label: string, count: number, injury_count: number, death_count: number}[]}`.
- `GET /api/analytics/spikes?dimension=product_code|manufacturer_key|hazard&window_days=90&min_count=8&limit=25`
  -> `{measure, caveat, method: "spike-poisson-v1", window: {start: string, end: string}, baseline: {start: string, end: string}, rows: Spike[]}`.

```ts
interface Spike { key: string; label: string; recent_count: number; expected_count: number; ratio: number; z: number;
  filters: Filters }   // only the filters that are set; they reproduce the recent window in the explorer
```

`spike-poisson-v1`: the window ends 30 days before the newest report date, to skip the incomplete tail. The baseline is the 365 days before the window, scaled to the window length. `z = (recent - expected) / sqrt(max(expected, 1))`. Keep rows with `recent_count >= min_count` and `z >= 3`, sorted by z.

## Source and sync

- `GET /api/source/status` -> `{incident_count: number, newest_report_date: string, newest_publication_date: string, batches: IngestBatch[]}` (last 20 batches).
- `POST /api/source/sync` (lead only) -> `IngestBatch[]`. Runs the incremental sync synchronously and rebuilds inference. The TF-IDF index reloads afterwards.

## Errors

`{detail: string}` with a 4xx status. `422` for validation (FastAPI default shape is fine).
