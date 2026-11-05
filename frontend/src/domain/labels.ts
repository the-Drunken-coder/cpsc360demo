import type { BreakdownDimension, FacetField, TrendGroupBy } from "../api/types";
import type { FilterKey } from "./filters";

export const FILTER_LABELS: Record<FilterKey, string> = {
  q: "Text",
  product_category: "Category",
  product_code: "Product type",
  manufacturer_key: "Manufacturer",
  brand: "Brand",
  model: "Model",
  hazard: "Hazard (inferred)",
  severity: "Severity",
  state: "State",
  submitter_category: "Submitter",
  report_date_from: "Reported from",
  report_date_to: "Reported to",
  injury_only: "Injury only",
  has_company_comment: "Manufacturer responded",
  in_investigation: "Investigation",
};

export const FACET_ORDER: FacetField[] = [
  "hazard", "severity", "product_category", "product_code", "manufacturer_key", "state", "submitter_category",
];

export const DIMENSION_LABELS: Record<Exclude<TrendGroupBy, "none"> | BreakdownDimension, string> = {
  product_category: "Category",
  product_code: "Product type",
  manufacturer_key: "Manufacturer",
  hazard: "Hazard (inferred)",
  severity: "Severity",
  state: "State",
};
