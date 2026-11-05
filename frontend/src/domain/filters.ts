import type { Filters } from "../api/types";
import { isHazardKey } from "./hazards";

type FieldKind = "text" | "list" | "bool" | "int";

const FILTER_FIELDS: { [K in keyof Required<Filters>]: FieldKind } = {
  q: "text",
  product_category: "list",
  product_code: "list",
  manufacturer_key: "list",
  brand: "text",
  model: "text",
  hazard: "list",
  severity: "list",
  state: "list",
  submitter_category: "list",
  report_date_from: "text",
  report_date_to: "text",
  injury_only: "bool",
  has_company_comment: "bool",
  in_investigation: "int",
};

export type FilterKey = keyof Filters;
export type ListFilterKey = { [K in FilterKey]-?: NonNullable<Filters[K]> extends unknown[] ? K : never }[FilterKey];

export const FILTER_KEYS = Object.keys(FILTER_FIELDS) as FilterKey[];

export function parseFilters(params: URLSearchParams): Filters {
  const out: Record<string, unknown> = {};
  for (const key of FILTER_KEYS) {
    const kind = FILTER_FIELDS[key];
    if (kind === "list") {
      const values = params.getAll(key).filter((v) => v !== "");
      const valid = key === "hazard" ? values.filter(isHazardKey) : values;
      if (valid.length > 0) out[key] = valid;
      continue;
    }
    const raw = params.get(key);
    if (raw === null || raw === "") continue;
    if (kind === "text") out[key] = raw;
    else if (kind === "bool") {
      if (raw === "true") out[key] = true;
      else if (raw === "false") out[key] = false;
    } else {
      const n = Number(raw);
      if (Number.isInteger(n)) out[key] = n;
    }
  }
  return out as Filters;
}

export function toSearchParams(filters: Filters, extra: Record<string, string | number | undefined> = {}): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, String(value));
  }
  for (const [key, value] of Object.entries(extra)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params;
}

export function filtersEqual(a: Filters, b: Filters): boolean {
  return toSearchParams(a).toString() === toSearchParams(b).toString();
}

export function isEmptyFilters(filters: Filters): boolean {
  return toSearchParams(filters).toString() === "";
}

export function withFilter<K extends FilterKey>(filters: Filters, key: K, value: Filters[K] | undefined): Filters {
  const next = { ...filters };
  if (value === undefined || (Array.isArray(value) && value.length === 0) || value === "") delete next[key];
  else next[key] = value;
  return next;
}

export function toggleListValue(filters: Filters, key: ListFilterKey, value: string): Filters {
  const current = (filters[key] ?? []) as string[];
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  return withFilter(filters, key, next as Filters[ListFilterKey]);
}

export function explorerHref(filters: Filters, extra: Record<string, string | undefined> = {}): string {
  const qs = toSearchParams(filters, extra).toString();
  return qs ? `/?${qs}` : "/";
}
