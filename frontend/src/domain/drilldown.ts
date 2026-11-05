import type { BreakdownDimension, Filters, TrendGroupBy } from "../api/types";
import { withFilter } from "./filters";
import { isHazardKey } from "./hazards";

// "__other__" folds many groups together and "__unknown__" is a missing value; neither maps to a filter.
export const isDrillable = (key: string) => key !== "__other__" && key !== "__unknown__";

export function withGroup(filters: Filters, dimension: BreakdownDimension | Exclude<TrendGroupBy, "none">, key: string): Filters {
  if (dimension === "hazard") {
    if (!isHazardKey(key)) return filters;
    // Reports can carry several hazards, and values inside one filter OR together, so a group inside an
    // active hazard filter must be required separately to keep exactly the counted reports.
    if (!filters.hazard?.length) return withFilter(filters, "hazard", [key]);
    return withFilter(filters, "hazard_all", [...new Set([...(filters.hazard_all ?? []), key])]);
  }
  return withFilter(filters, dimension, [key]);
}
