import { Button, Tag } from "@blueprintjs/core";
import type { Facets, FacetField, Filters } from "../api/types";
import { FILTER_KEYS, isEmptyFilters, withFilter, type FilterKey } from "../domain/filters";
import { HAZARD_LABELS, isHazardKey } from "../domain/hazards";
import { FILTER_LABELS } from "../domain/labels";

function valueLabel(key: FilterKey, value: string, facets: Facets | undefined): string {
  if (key === "hazard" && isHazardKey(value)) return HAZARD_LABELS[value];
  if (key === "in_investigation") return `#${value}`;
  const facet = facets?.[key as FacetField];
  return facet?.find((f) => f.value === value)?.label ?? value;
}

export function ActiveFilters({ filters, facets, onChange }: {
  filters: Filters; facets?: Facets; onChange: (filters: Filters) => void;
}) {
  if (isEmptyFilters(filters)) return <span className="active-filters-empty">All reports</span>;
  const chips: { id: string; label: string; remove: () => void }[] = [];
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value === undefined) continue;
    const name = FILTER_LABELS[key];
    if (Array.isArray(value)) {
      for (const v of value as string[]) {
        chips.push({
          id: `${key}:${v}`,
          label: `${name}: ${valueLabel(key, v, facets)}`,
          remove: () => onChange(withFilter(filters, key, (value as string[]).filter((x) => x !== v) as Filters[typeof key])),
        });
      }
    } else {
      const shown = typeof value === "boolean" ? (value ? "yes" : "no") : valueLabel(key, String(value), facets);
      chips.push({ id: key, label: `${name}: ${shown}`, remove: () => onChange(withFilter(filters, key, undefined)) });
    }
  }
  return (
    <span className="active-filters">
      {chips.map((c) => (
        <Tag key={c.id} minimal interactive onRemove={c.remove} className="filter-chip">{c.label}</Tag>
      ))}
      <Button minimal small text="Clear all" onClick={() => onChange({})} />
    </span>
  );
}
