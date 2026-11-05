export type Role = "analyst" | "lead" | "viewer";
export interface User { id: number; handle: string; display_name: string; role: Role }

export type HazardKey = "fire" | "overheating" | "electrical" | "burn" | "shatter_explosion" | "laceration" | "choking"
  | "suffocation" | "entrapment" | "fall" | "tip_over" | "chemical" | "structural" | "battery" | "drowning"
  | "skin_irritation";

export interface HazardTag { hazard: HazardKey; label: string; evidence: string[]; method: string }

export interface IncidentSummary {
  report_no: string;
  report_date: string;
  publication_date: string;
  product_description: string;
  product_category: string;
  product_type: string | null;
  product_code: string;
  manufacturer_name: string;
  manufacturer_key: string;
  brand: string | null;
  model: string | null;
  severity: string;
  severity_rank: number;
  is_injury: boolean;
  state: string | null;
  victim_age: number | null;
  has_company_comment: boolean;
  hazards: HazardKey[];
  snippet: string;
  investigation_ids: number[];
}

export interface Filters {
  q?: string;
  product_category?: string[];
  product_code?: string[];
  manufacturer_key?: string[];
  brand?: string;
  model?: string;
  hazard?: HazardKey[];
  hazard_all?: HazardKey[];
  severity?: string[];
  state?: string[];
  submitter_category?: string[];
  report_date_from?: string;
  report_date_to?: string;
  injury_only?: boolean;
  has_company_comment?: boolean;
  in_investigation?: number;
}

export type IncidentSort = "relevance" | "report_date" | "-report_date" | "severity" | "publication_date";

export interface IncidentPage {
  total: number;
  page: number;
  page_size: number;
  items: IncidentSummary[];
  took_ms: number;
}

export type FacetField = "product_category" | "product_code" | "manufacturer_key" | "hazard" | "severity" | "state"
  | "submitter_category";
export interface FacetValue { value: string; label: string; count: number }
export type Facets = Record<FacetField, FacetValue[]>;

export interface CompanyComment { date: string | null; company: string | null; text: string }

export type InvestigationStatus = "open" | "in_review" | "escalated" | "closed";

export interface ReportedIncident {
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
}

export interface IncidentDetail {
  reported: ReportedIncident;
  company_comments: CompanyComment[];
  inferred: {
    hazards: HazardTag[];
    manufacturer_key: string; manufacturer_display_name: string;
    brand_key: string | null; model_key: string | null; method: string;
  };
  analyst: {
    investigations: { id: number; title: string; status: InvestigationStatus }[];
    relation_reviews: RelationReview[];
  };
  source: {
    current_sha256: string;
    batch: IngestBatch;
    versions: SourceVersion[];
    public_search_url: "https://www.saferproducts.gov/PublicSearch";
    disclaimer: string;
  };
}

export interface SourceVersion { row_sha256: string; first_seen_at: string; batch: IngestBatch; raw?: Record<string, string> }
export interface IngestBatch {
  id: number; kind: "bulk" | "incremental"; source_url: string; params: Record<string, string>;
  file_sha256: string; started_at: string; finished_at: string | null; row_count: number | null;
  inserted: number | null; updated: number | null; unchanged: number | null; kept_bulk: number | null;
}

export type ReasonKind = "associated_report" | "same_model" | "same_brand" | "same_manufacturer" | "same_product_type"
  | "shared_hazard" | "text_similarity";

export interface Reason {
  kind: ReasonKind;
  weight: number;
  detail: string;
  terms?: string[];
  hazards?: HazardKey[];
}

export interface RelatedIncident {
  incident: IncidentSummary;
  score: number;
  reasons: Reason[];
  method: string;
  review: RelationReview | null;
}

export type Verdict = "confirmed" | "rejected";

export interface RelationReview {
  report_a: string; report_b: string;
  verdict: Verdict; note: string;
  reasons_snapshot: Reason[];
  reviewer: User; reviewed_at: string;
}

export type AgreementField = "manufacturer_key" | "brand_key" | "model_key" | "product_code" | "product_category" | "state"
  | "severity";

export interface PatternAnalysis {
  report_nos: string[];
  date_range: { first: string; last: string };
  shared_terms: { term: string; report_nos: string[] }[];
  field_agreement: {
    field: AgreementField;
    values: { value: string | null; label: string; report_nos: string[] }[];
  }[];
  hazards: { hazard: HazardKey; label: string; report_nos: string[] }[];
  severity: { severity: string; rank: number; report_nos: string[] }[];
  injury_count: number; death_count: number;
  method: string;
}

export interface InvestigationSummaryRow {
  id: number; title: string; status: InvestigationStatus; labels: string[];
  assignee: User | null; created_by: User; created_at: string; updated_at: string;
  incident_count: number; latest_report_date: string | null;
}

export interface InvestigationMember { incident: IncidentSummary; rationale: string; added_by: User; added_at: string }

export interface Investigation extends InvestigationSummaryRow {
  description: string;
  incidents: InvestigationMember[];
  notes: Note[];
  allowed_transitions: InvestigationStatus[];
}

export interface Note { id: number; author: User; body: string; cited_report_nos: string[]; created_at: string }

export interface AuditEntry {
  id: number; at: string; actor: User; action: string; entity: string; entity_id: string;
  before: unknown | null; after: unknown | null;
}

export interface SummaryClaim { text: string; citations: string[] }
export interface SummarySnapshot {
  id: number; investigation_id: number; generated_at: string; generated_by: User;
  method: string;
  label: string;
  sections: { heading: string; claims: SummaryClaim[] }[];
  member_report_nos: string[];
}

export type SavedQuery = Filters & { sort?: string };
export interface SavedSearch { id: number; name: string; query: SavedQuery; owner: User; created_at: string; shared: boolean }

export type TrendInterval = "month" | "quarter" | "year";
export type TrendGroupBy = "none" | "product_category" | "product_code" | "manufacturer_key" | "hazard" | "severity";
export type BreakdownDimension = "product_category" | "product_code" | "manufacturer_key" | "hazard" | "severity" | "state";
export type SpikeDimension = "product_code" | "manufacturer_key" | "hazard";

export interface TrendSeries { key: string; label: string; points: { period: string; count: number }[]; total: number }
export interface TrendResponse {
  measure: "report_count"; caveat: string; interval: TrendInterval; series: TrendSeries[]; incomplete_after: string;
}

export interface BreakdownRow { key: string; label: string; count: number; injury_count: number; death_count: number }
export interface BreakdownResponse { measure: "report_count"; caveat: string; dimension: BreakdownDimension; rows: BreakdownRow[] }

export interface Spike {
  key: string; label: string; recent_count: number; expected_count: number; ratio: number; z: number;
  filters: Filters;
}
export interface SpikesResponse {
  measure: "report_count"; caveat: string; method: "spike-poisson-v1";
  window: { start: string; end: string }; baseline: { start: string; end: string }; rows: Spike[];
}

export interface SourceStatus {
  incident_count: number; newest_report_date: string; newest_publication_date: string; batches: IngestBatch[];
}

export interface Session { token: string; user: User }
