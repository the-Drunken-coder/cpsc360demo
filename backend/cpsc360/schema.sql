-- Three provenance tiers, one schema each.
--   source:    public SaferProducts.gov records, written only by ingestion, never edited by analysts.
--   inference: automated derivations, rebuildable from source at any time; every row names its method.
--   workspace: prototype analyst data (investigations, reviews, notes); every write is audited.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS inference;
CREATE SCHEMA IF NOT EXISTS workspace;

CREATE TABLE IF NOT EXISTS source.ingest_batch (
    id            bigserial PRIMARY KEY,
    kind          text NOT NULL CHECK (kind IN ('bulk', 'incremental')),
    source_url    text NOT NULL,
    params        jsonb NOT NULL DEFAULT '{}'::jsonb,
    file_sha256   text NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    row_count     integer,
    inserted      integer,
    updated       integer,
    unchanged     integer,
    kept_bulk     integer
);

-- Every distinct version of a public record ever received, verbatim (CSV header -> cell text).
CREATE TABLE IF NOT EXISTS source.incident_version (
    report_no     text NOT NULL,
    row_sha256    text NOT NULL,
    raw           jsonb NOT NULL,
    batch_id      bigint NOT NULL REFERENCES source.ingest_batch(id),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (report_no, row_sha256)
);

-- Current version of each public record, typed. Text fields are the submitted text unmodified.
CREATE TABLE IF NOT EXISTS source.incident (
    report_no                  text PRIMARY KEY,
    current_sha256             text NOT NULL,
    batch_id                   bigint NOT NULL REFERENCES source.ingest_batch(id),
    report_date                date NOT NULL,
    sent_to_manufacturer_date  date,
    publication_date           date NOT NULL,
    submitter_category         text NOT NULL,
    product_description        text NOT NULL,
    product_category           text NOT NULL,
    product_subcategory        text NOT NULL,
    product_type               text,
    product_code               text NOT NULL,
    manufacturer_name          text NOT NULL,
    brand                      text,
    model                      text,
    serial_number              text,
    upc                        text,
    date_manufactured          date,
    manufacturer_date_code     text,
    retailer                   text,
    retailer_state             text,
    purchase_date              date,
    purchase_date_is_estimate  boolean NOT NULL DEFAULT false,
    incident_description       text NOT NULL,
    city                       text,
    state                      text,
    zip                        text,
    location                   text,
    severity                   text NOT NULL,
    victim_sex                 text,
    relation_to_victim         text,
    victim_age                 integer,
    submitter_has_product      boolean,
    damaged_before_incident    boolean,
    damage_description         text,
    damage_repaired            boolean,
    modified_before_incident   boolean,
    contacted_manufacturer     boolean,
    plans_to_contact           boolean,
    answer_explanation         text,
    company_comments           text,
    associated_report_nos      text[] NOT NULL DEFAULT '{}',
    search                     tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english',
            coalesce(product_description, '') || ' ' || coalesce(brand, '') || ' ' ||
            coalesce(model, '') || ' ' || coalesce(manufacturer_name, '') || ' ' ||
            coalesce(product_type, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(incident_description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(company_comments, '')), 'C')
    ) STORED
);

CREATE INDEX IF NOT EXISTS incident_search_idx ON source.incident USING gin (search);
CREATE INDEX IF NOT EXISTS incident_report_date_idx ON source.incident (report_date DESC);
CREATE INDEX IF NOT EXISTS incident_publication_date_idx ON source.incident (publication_date DESC);
CREATE INDEX IF NOT EXISTS incident_product_code_idx ON source.incident (product_code);
CREATE INDEX IF NOT EXISTS incident_category_idx ON source.incident (product_category);
CREATE INDEX IF NOT EXISTS incident_severity_idx ON source.incident (severity);
CREATE INDEX IF NOT EXISTS incident_state_idx ON source.incident (state);

-- Severity is reported; the ordering is a fixed lookup, not an inference.
CREATE TABLE IF NOT EXISTS source.severity_level (
    label      text PRIMARY KEY,
    rank       smallint NOT NULL,
    is_injury  boolean NOT NULL
);
INSERT INTO source.severity_level (label, rank, is_injury) VALUES
    ('Unspecified', 0, false),
    ('No Incident, No Injury', 1, false),
    ('Incident, No Injury', 2, false),
    ('Injury, Level of care not known', 3, true),
    ('Injury, No First Aid or Medical Attention Received', 4, true),
    ('Injury, First Aid Received by Non-Medical Professional', 5, true),
    ('Injury, Seen by Medical Professional', 6, true),
    ('Injury, Emergency Department Treatment Received', 7, true),
    ('Injury, Hospital Admission', 8, true),
    ('Death', 9, true)
ON CONFLICT (label) DO NOTHING;

-- Canonical keys for matching. Reported values stay untouched in source.incident.
CREATE TABLE IF NOT EXISTS inference.incident_norm (
    report_no         text PRIMARY KEY REFERENCES source.incident(report_no) ON DELETE CASCADE,
    manufacturer_key  text NOT NULL,
    brand_key         text,
    model_key         text,
    method            text NOT NULL
);
-- Folded letters and digits of the reported brand and model, which the explorer's brand and model filters compare.
ALTER TABLE inference.incident_norm ADD COLUMN IF NOT EXISTS brand_text text;
ALTER TABLE inference.incident_norm ADD COLUMN IF NOT EXISTS model_text text;
CREATE INDEX IF NOT EXISTS incident_norm_brand_text_idx ON inference.incident_norm (brand_text);
CREATE INDEX IF NOT EXISTS incident_norm_model_text_idx ON inference.incident_norm (model_text);
CREATE INDEX IF NOT EXISTS incident_norm_mfr_idx ON inference.incident_norm (manufacturer_key);
CREATE INDEX IF NOT EXISTS incident_norm_brand_idx ON inference.incident_norm (brand_key);
CREATE INDEX IF NOT EXISTS incident_norm_model_idx ON inference.incident_norm (model_key);

-- Display name for each manufacturer_key: the most frequent reported spelling.
CREATE TABLE IF NOT EXISTS inference.manufacturer (
    manufacturer_key  text PRIMARY KEY,
    display_name      text NOT NULL,
    variant_count     integer NOT NULL,
    report_count      integer NOT NULL,
    method            text NOT NULL
);

-- Hazard tags from keyword rules. evidence holds the exact matched phrases from the narrative.
CREATE TABLE IF NOT EXISTS inference.incident_hazard (
    report_no  text NOT NULL REFERENCES source.incident(report_no) ON DELETE CASCADE,
    hazard     text NOT NULL,
    evidence   text[] NOT NULL,
    method     text NOT NULL,
    PRIMARY KEY (report_no, hazard)
);
CREATE INDEX IF NOT EXISTS incident_hazard_hazard_idx ON inference.incident_hazard (hazard);

CREATE TABLE IF NOT EXISTS workspace.app_user (
    id            bigserial PRIMARY KEY,
    handle        text NOT NULL UNIQUE,
    display_name  text NOT NULL,
    role          text NOT NULL CHECK (role IN ('analyst', 'lead', 'viewer')),
    api_token     text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS workspace.investigation (
    id           bigserial PRIMARY KEY,
    title        text NOT NULL,
    description  text NOT NULL DEFAULT '',
    status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_review', 'escalated', 'closed')),
    assignee_id  bigint REFERENCES workspace.app_user(id),
    labels       text[] NOT NULL DEFAULT '{}',
    created_by   bigint NOT NULL REFERENCES workspace.app_user(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace.investigation_incident (
    investigation_id  bigint NOT NULL REFERENCES workspace.investigation(id) ON DELETE CASCADE,
    report_no         text NOT NULL REFERENCES source.incident(report_no),
    rationale         text NOT NULL DEFAULT '',
    added_by          bigint NOT NULL REFERENCES workspace.app_user(id),
    added_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (investigation_id, report_no)
);

CREATE TABLE IF NOT EXISTS workspace.investigation_note (
    id                bigserial PRIMARY KEY,
    investigation_id  bigint NOT NULL REFERENCES workspace.investigation(id) ON DELETE CASCADE,
    author_id         bigint NOT NULL REFERENCES workspace.app_user(id),
    body              text NOT NULL,
    cited_report_nos  text[] NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Analyst verdict on a suggested relationship. report_a < report_b so each pair has one row.
-- reasons_snapshot freezes the explanation the analyst saw when deciding.
CREATE TABLE IF NOT EXISTS workspace.relation_review (
    report_a          text NOT NULL REFERENCES source.incident(report_no),
    report_b          text NOT NULL REFERENCES source.incident(report_no),
    verdict           text NOT NULL CHECK (verdict IN ('confirmed', 'rejected')),
    note              text NOT NULL DEFAULT '',
    reasons_snapshot  jsonb NOT NULL,
    reviewer_id       bigint NOT NULL REFERENCES workspace.app_user(id),
    reviewed_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (report_a, report_b),
    CHECK (report_a < report_b)
);

CREATE TABLE IF NOT EXISTS workspace.saved_search (
    id          bigserial PRIMARY KEY,
    owner_id    bigint NOT NULL REFERENCES workspace.app_user(id),
    name        text NOT NULL,
    query       jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Generated summaries are stored, so a claim can be traced to the exact reports it cited at that time.
CREATE TABLE IF NOT EXISTS workspace.summary_snapshot (
    id                bigserial PRIMARY KEY,
    investigation_id  bigint NOT NULL REFERENCES workspace.investigation(id) ON DELETE CASCADE,
    method            text NOT NULL,
    body              jsonb NOT NULL,
    generated_by      bigint NOT NULL REFERENCES workspace.app_user(id),
    generated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace.audit_log (
    id         bigserial PRIMARY KEY,
    at         timestamptz NOT NULL DEFAULT now(),
    actor_id   bigint NOT NULL REFERENCES workspace.app_user(id),
    action     text NOT NULL,
    entity     text NOT NULL,
    entity_id  text NOT NULL,
    before     jsonb,
    after      jsonb
);
CREATE INDEX IF NOT EXISTS audit_log_entity_idx ON workspace.audit_log (entity, entity_id, at DESC);
