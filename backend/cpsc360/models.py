from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer

Role = Literal['analyst', 'lead', 'viewer']
Status = Literal['open', 'in_review', 'escalated', 'closed']
HazardKey = Literal['fire', 'overheating', 'electrical', 'burn', 'shatter_explosion', 'laceration', 'choking', 'suffocation', 'entrapment', 'fall', 'tip_over', 'chemical', 'structural', 'battery', 'drowning', 'skin_irritation']
Sort = Literal['relevance', 'report_date', '-report_date', 'severity', 'publication_date']
ReasonKind = Literal['associated_report', 'same_model', 'same_brand', 'same_manufacturer', 'same_product_type', 'shared_hazard', 'text_similarity']


class User(BaseModel):
    id: int
    handle: str
    display_name: str
    role: Role


class IntegrationSetting(BaseModel):
    configured: bool
    key_hint: str | None
    model: str
    updated_by: User | None
    updated_at: datetime | None


class IntegrationInput(BaseModel):
    api_key: str | None = None
    model: str | None = Field(default=None, min_length=1)


class AISelection(BaseModel):
    report_nos: list[str] = Field(min_length=1, max_length=50)


class AIHazardTag(BaseModel):
    hazard: HazardKey
    label: str
    evidence: list[str]


class AIHazardResult(BaseModel):
    report_no: str
    model: str
    prompt_version: str
    status: Literal['ok', 'error']
    hazards: list[AIHazardTag]
    dropped: list[dict[str, Any]]
    error: str | None
    classified_by: User | None
    classified_at: datetime


class Filters(BaseModel):
    q: str | None = None
    product_category: list[str] = Field(default_factory=list)
    product_code: list[str] = Field(default_factory=list)
    manufacturer_key: list[str] = Field(default_factory=list)
    brand: str | None = None
    model: str | None = None
    hazard: list[HazardKey] = Field(default_factory=list)
    hazard_all: list[HazardKey] = Field(default_factory=list)
    severity: list[str] = Field(default_factory=list)
    state: list[str] = Field(default_factory=list)
    submitter_category: list[str] = Field(default_factory=list)
    report_date_from: date | None = None
    report_date_to: date | None = None
    injury_only: bool | None = None
    has_company_comment: bool | None = None
    in_investigation: int | None = None


class HazardTag(BaseModel):
    hazard: HazardKey
    label: str
    evidence: list[str]
    method: str


class IncidentSummary(BaseModel):
    report_no: str
    report_date: date
    publication_date: date
    product_description: str
    product_category: str
    product_type: str | None
    product_code: str
    manufacturer_name: str
    manufacturer_key: str
    brand: str | None
    model: str | None
    severity: str
    severity_rank: int
    is_injury: bool
    state: str | None
    victim_age: int | None
    has_company_comment: bool
    hazards: list[HazardKey]
    snippet: str
    investigation_ids: list[int]


class IncidentPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[IncidentSummary]
    took_ms: float


class FacetValue(BaseModel):
    value: str
    label: str
    count: int


class IngestBatch(BaseModel):
    id: int
    kind: Literal['bulk', 'incremental']
    source_url: str
    params: dict[str, str]
    file_sha256: str
    started_at: datetime
    finished_at: datetime | None
    row_count: int | None
    inserted: int | None
    updated: int | None
    unchanged: int | None
    kept_bulk: int | None


class SourceVersion(BaseModel):
    row_sha256: str
    first_seen_at: datetime
    batch: IngestBatch
    raw: dict[str, str] | None = None


class CompanyComment(BaseModel):
    date: date | None
    company: str | None
    text: str


class Reason(BaseModel):
    kind: ReasonKind
    weight: float
    detail: str
    terms: list[str] | None = None
    hazards: list[HazardKey] | None = None


class RelationReview(BaseModel):
    report_a: str
    report_b: str
    verdict: Literal['confirmed', 'rejected']
    note: str
    reasons_snapshot: list[Reason]
    reviewer: User
    reviewed_at: datetime


class RelatedIncident(BaseModel):
    incident: IncidentSummary
    score: float
    reasons: list[Reason]
    method: str
    review: RelationReview | None


class Reported(BaseModel):
    report_no: str
    report_date: date
    sent_to_manufacturer_date: date | None
    publication_date: date
    submitter_category: str
    product_description: str
    product_category: str
    product_subcategory: str
    product_type: str | None
    product_code: str
    manufacturer_name: str
    brand: str | None
    model: str | None
    serial_number: str | None
    upc: str | None
    date_manufactured: date | None
    manufacturer_date_code: str | None
    retailer: str | None
    retailer_state: str | None
    purchase_date: date | None
    purchase_date_is_estimate: bool
    incident_description: str
    city: str | None
    state: str | None
    zip: str | None
    location: str | None
    severity: str
    victim_sex: str | None
    relation_to_victim: str | None
    victim_age: int | None
    submitter_has_product: bool | None
    damaged_before_incident: bool | None
    damage_description: str | None
    damage_repaired: bool | None
    modified_before_incident: bool | None
    contacted_manufacturer: bool | None
    plans_to_contact: bool | None
    answer_explanation: str | None
    company_comments: str | None
    associated_report_nos: list[str]


class Inferred(BaseModel):
    ai_hazards: list[AIHazardResult] = Field(default_factory=list)
    hazards: list[HazardTag]
    manufacturer_key: str
    manufacturer_display_name: str
    brand_key: str | None
    model_key: str | None
    method: str


class InvestigationRef(BaseModel):
    id: int
    title: str
    status: Status


class AnalystDetail(BaseModel):
    investigations: list[InvestigationRef]
    relation_reviews: list[RelationReview]


class SourceDetail(BaseModel):
    current_sha256: str
    batch: IngestBatch
    versions: list[SourceVersion]
    public_search_url: Literal['https://www.saferproducts.gov/PublicSearch']
    disclaimer: str


class IncidentDetail(BaseModel):
    reported: Reported
    company_comments: list[CompanyComment]
    inferred: Inferred
    analyst: AnalystDetail
    source: SourceDetail


class DateRange(BaseModel):
    first: date
    last: date


class SharedTerm(BaseModel):
    term: str
    report_nos: list[str]


class AgreementValue(BaseModel):
    value: str | None
    label: str
    report_nos: list[str]


class FieldAgreement(BaseModel):
    field: Literal['manufacturer_key', 'brand_key', 'model_key', 'product_code', 'product_category', 'state', 'severity']
    values: list[AgreementValue]


class PatternHazard(BaseModel):
    hazard: HazardKey
    label: str
    report_nos: list[str]


class PatternSeverity(BaseModel):
    severity: str
    rank: int
    report_nos: list[str]


class PatternAnalysis(BaseModel):
    report_nos: list[str]
    date_range: DateRange
    shared_terms: list[SharedTerm]
    field_agreement: list[FieldAgreement]
    hazards: list[PatternHazard]
    severity: list[PatternSeverity]
    injury_count: int
    death_count: int
    method: str


class Note(BaseModel):
    id: int
    author: User
    body: str
    cited_report_nos: list[str]
    created_at: datetime


class InvestigationSummaryRow(BaseModel):
    id: int
    title: str
    status: Status
    labels: list[str]
    assignee: User | None
    created_by: User
    created_at: datetime
    updated_at: datetime
    incident_count: int
    latest_report_date: date | None


class Member(BaseModel):
    incident: IncidentSummary
    rationale: str
    added_by: User
    added_at: datetime


class Investigation(InvestigationSummaryRow):
    description: str
    incidents: list[Member]
    notes: list[Note]
    allowed_transitions: list[Status]


class AuditEntry(BaseModel):
    id: int
    at: datetime
    actor: User
    action: str
    entity: str
    entity_id: str
    before: Any | None
    after: Any | None


class SummaryClaim(BaseModel):
    text: str
    citations: list[str]


class SummarySection(BaseModel):
    heading: str
    claims: list[SummaryClaim]


class SummarySnapshot(BaseModel):
    id: int
    investigation_id: int
    generated_at: datetime
    generated_by: User
    method: str
    label: str
    sections: list[SummarySection]
    member_report_nos: list[str]


class SearchQuery(Filters):
    sort: Sort | None = None


class SavedSearch(BaseModel):
    id: int
    name: str
    query: SearchQuery
    owner: User
    created_at: datetime
    shared: bool


class Measure(BaseModel):
    measure: Literal['report_count'] = 'report_count'
    caveat: str


class Point(BaseModel):
    period: date
    count: int


class Series(BaseModel):
    key: str
    label: str
    points: list[Point]
    total: int


class Trend(Measure):
    interval: Literal['month', 'quarter', 'year']
    series: list[Series]
    incomplete_after: date


class BreakdownRow(BaseModel):
    key: str
    label: str
    count: int
    injury_count: int
    death_count: int


class Breakdown(Measure):
    dimension: str
    rows: list[BreakdownRow]


class Window(BaseModel):
    start: date
    end: date


class Spike(BaseModel):
    key: str
    label: str
    recent_count: int
    expected_count: float
    ratio: float
    z: float
    filters: Filters

    @field_serializer('filters')
    def only_set_filters(self, filters: Filters):
        return filters.model_dump(mode='json', exclude_defaults=True)


class Spikes(Measure):
    method: Literal['spike-poisson-v1'] = 'spike-poisson-v1'
    window: Window
    baseline: Window
    rows: list[Spike]


class SourceStatus(BaseModel):
    incident_count: int
    newest_report_date: date
    newest_publication_date: date
    batches: list[IngestBatch]


class SessionInput(BaseModel):
    handle: str


class Session(BaseModel):
    token: str
    user: User


class ReportSelection(BaseModel):
    report_nos: list[str] = Field(min_length=2, max_length=50)


class RelationInput(BaseModel):
    report_a: str
    report_b: str
    verdict: Literal['confirmed', 'rejected']
    note: str = ''


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ''
    labels: list[str] = Field(default_factory=list)
    assignee_id: int | None = None
    report_nos: list[str] = Field(default_factory=list)
    rationale: str = ''


class InvestigationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    labels: list[str] | None = None
    assignee_id: int | None = None
    status: Status | None = None


class MembersInput(BaseModel):
    report_nos: list[str]
    rationale: str = ''


class NoteInput(BaseModel):
    body: str = Field(min_length=1)


class SavedSearchInput(BaseModel):
    name: str = Field(min_length=1)
    query: SearchQuery
