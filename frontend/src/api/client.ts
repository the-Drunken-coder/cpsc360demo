import { compactFilters, toSearchParams } from "../domain/filters";
import type {
  AuditEntry, BreakdownDimension, BreakdownResponse, Facets, Filters, IncidentDetail, IncidentPage, IncidentSort,
  IngestBatch, Investigation, InvestigationStatus, InvestigationSummaryRow, Note, PatternAnalysis, RelatedIncident,
  RelationReview, SavedQuery, SavedSearch, Session, SourceStatus, SourceVersion, SpikeDimension, SpikesResponse,
  SummarySnapshot, TrendGroupBy, TrendInterval, TrendResponse, User, Verdict,
} from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, readonly detail: string) {
    super(detail);
  }
}

let token: string | null = null;
let renewSession: (() => Promise<string | null>) | null = null;

export function setToken(next: string | null): void {
  token = next;
}

export function onUnauthorized(handler: () => Promise<string | null>): void {
  renewSession = handler;
}

type Query = URLSearchParams | Record<string, string | number | undefined>;

function queryString(query?: Query): string {
  if (!query) return "";
  const params = query instanceof URLSearchParams ? query : toSearchParams({}, query);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

async function send(method: string, path: string, body: unknown, query: Query | undefined, auth: boolean): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  return fetch(`/api${path}${queryString(query)}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d: { msg?: string }) => d.msg ?? "").join("; ");
  } catch {
    // Non-JSON error bodies fall through to the status text.
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function raw(method: string, path: string, body?: unknown, query?: Query, auth = true): Promise<Response> {
  let res = await send(method, path, body, query, auth);
  if (res.status === 401 && auth && renewSession) {
    const renewed = await renewSession();
    if (renewed) res = await send(method, path, body, query, auth);
  }
  if (!res.ok) throw new ApiError(res.status, await errorDetail(res));
  return res;
}

async function json<T>(method: string, path: string, body?: unknown, query?: Query, auth = true): Promise<T> {
  const res = await raw(method, path, body, query, auth);
  return (await res.json()) as T;
}

async function none(method: string, path: string): Promise<void> {
  await raw(method, path);
}

const enc = encodeURIComponent;

export const api = {
  users: () => json<User[]>("GET", "/users", undefined, undefined, false),
  createSession: (handle: string) => json<Session>("POST", "/session", { handle }, undefined, false),

  incidents: (filters: Filters, sort: IncidentSort | undefined, page: number, pageSize: number) =>
    json<IncidentPage>("GET", "/incidents", undefined, toSearchParams(filters, { sort, page, page_size: pageSize })),
  facets: (filters: Filters) => json<Facets>("GET", "/incidents/facets", undefined, toSearchParams(filters)),
  exportCsv: async (filters: Filters) => (await raw("GET", "/incidents/export.csv", undefined, toSearchParams(filters))).blob(),
  incident: (reportNo: string) => json<IncidentDetail>("GET", `/incidents/${enc(reportNo)}`),
  versions: (reportNo: string) => json<SourceVersion[]>("GET", `/incidents/${enc(reportNo)}/versions`),
  related: (reportNo: string, limit = 25) =>
    json<RelatedIncident[]>("GET", `/incidents/${enc(reportNo)}/related`, undefined, { limit }),

  reviewRelation: (body: { report_a: string; report_b: string; verdict: Verdict; note: string }) =>
    json<RelationReview>("PUT", "/relations", body),
  deleteRelation: (a: string, b: string) => none("DELETE", `/relations/${enc(a)}/${enc(b)}`),

  patterns: (reportNos: string[]) => json<PatternAnalysis>("POST", "/patterns", { report_nos: reportNos }),

  investigations: (query: { status?: InvestigationStatus; assignee_id?: number; label?: string } = {}) =>
    json<InvestigationSummaryRow[]>("GET", "/investigations", undefined, query),
  createInvestigation: (body: {
    title: string; description?: string; labels?: string[]; assignee_id?: number; report_nos?: string[]; rationale?: string;
  }) => json<Investigation>("POST", "/investigations", body),
  investigation: (id: number) => json<Investigation>("GET", `/investigations/${id}`),
  updateInvestigation: (id: number, body: {
    title?: string; description?: string; labels?: string[]; assignee_id?: number | null; status?: InvestigationStatus;
  }) => json<Investigation>("PATCH", `/investigations/${id}`, body),
  addMembers: (id: number, reportNos: string[], rationale?: string) =>
    json<Investigation>("POST", `/investigations/${id}/incidents`, { report_nos: reportNos, rationale }),
  removeMember: (id: number, reportNo: string) =>
    json<Investigation>("DELETE", `/investigations/${id}/incidents/${enc(reportNo)}`),
  addNote: (id: number, body: string) => json<Note>("POST", `/investigations/${id}/notes`, { body }),
  audit: (id: number) => json<AuditEntry[]>("GET", `/investigations/${id}/audit`),
  generateSummary: (id: number) => json<SummarySnapshot>("POST", `/investigations/${id}/summary`),
  summaries: (id: number) => json<SummarySnapshot[]>("GET", `/investigations/${id}/summaries`),

  savedSearches: async () => (await json<SavedSearch[]>("GET", "/saved-searches")).map((s) => ({
    ...s, query: { ...compactFilters(s.query as Record<string, unknown>), sort: s.query.sort ?? undefined },
  })),
  createSavedSearch: (name: string, query: SavedQuery) => json<SavedSearch>("POST", "/saved-searches", { name, query }),
  deleteSavedSearch: (id: number) => none("DELETE", `/saved-searches/${id}`),

  trend: (filters: Filters, interval: TrendInterval, groupBy: TrendGroupBy, top = 6) =>
    json<TrendResponse>("GET", "/analytics/trend", undefined, toSearchParams(filters, { interval, group_by: groupBy, top })),
  breakdown: (filters: Filters, dimension: BreakdownDimension, limit = 20) =>
    json<BreakdownResponse>("GET", "/analytics/breakdown", undefined, toSearchParams(filters, { dimension, limit })),
  spikes: async (dimension: SpikeDimension, windowDays = 90, minCount = 8, limit = 25) => {
    const res = await json<SpikesResponse>("GET", "/analytics/spikes", undefined, {
      dimension, window_days: windowDays, min_count: minCount, limit,
    });
    return { ...res, rows: res.rows.map((r) => ({ ...r, filters: compactFilters(r.filters as Record<string, unknown>) })) };
  },

  sourceStatus: () => json<SourceStatus>("GET", "/source/status"),
  sync: () => json<IngestBatch[]>("POST", "/source/sync"),
};

export const qk = {
  incidents: (filters: Filters, sort: string | undefined, page: number, pageSize: number) =>
    ["incidents", filters, sort, page, pageSize] as const,
  facets: (filters: Filters) => ["facets", filters] as const,
  incident: (reportNo: string) => ["incident", reportNo] as const,
  versions: (reportNo: string) => ["versions", reportNo] as const,
  related: (reportNo: string) => ["related", reportNo] as const,
  patterns: (reportNos: string[]) => ["patterns", reportNos] as const,
  investigations: () => ["investigations"] as const,
  investigation: (id: number) => ["investigation", id] as const,
  audit: (id: number) => ["audit", id] as const,
  summaries: (id: number) => ["summaries", id] as const,
  savedSearches: () => ["saved-searches"] as const,
  trend: (filters: Filters, interval: string, groupBy: string) => ["trend", filters, interval, groupBy] as const,
  breakdown: (filters: Filters, dimension: string) => ["breakdown", filters, dimension] as const,
  spikes: (dimension: string, windowDays: number) => ["spikes", dimension, windowDays] as const,
  sourceStatus: () => ["source-status"] as const,
};
