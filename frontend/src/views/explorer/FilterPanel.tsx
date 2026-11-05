import { Button, Checkbox, Classes, Collapse, FormGroup, Icon, InputGroup, Switch, Tag } from "@blueprintjs/core";
import { forwardRef, useEffect, useState, type ClipboardEvent } from "react";
import type { FacetField, FacetValue, Facets, Filters } from "../../api/types";
import { fmtCount } from "../../components/text";
import { toggleListValue, withFilter } from "../../domain/filters";
import { FACET_ORDER, FILTER_LABELS } from "../../domain/labels";
import { parsePastedDate } from "../../domain/pastedDate";
import { SavedSearches } from "./SavedSearches";

interface Props {
  filters: Filters;
  sort: string;
  facets: Facets | undefined;
  onChange: (filters: Filters) => void;
}

export const FilterPanel = forwardRef<HTMLInputElement, Props>(function FilterPanel({ filters, sort, facets, onChange }, searchRef) {
  const [q, setQ] = useState(filters.q ?? "");
  useEffect(() => setQ(filters.q ?? ""), [filters.q]);
  // Native date controls can emit paste without applying its text.
  const pasteDate = (field: "report_date_from" | "report_date_to") => (event: ClipboardEvent<HTMLInputElement>) => {
    const date = parsePastedDate(event.clipboardData.getData("text/plain"));
    if (date === undefined) return;
    event.preventDefault();
    onChange(withFilter(filters, field, date));
  };

  return (
    <aside className="filter-panel">
      <form className="search-form" onSubmit={(e) => { e.preventDefault(); onChange(withFilter(filters, "q", q.trim())); }}>
        <InputGroup inputRef={searchRef} leftIcon="search" placeholder="Search narratives and products…" value={q}
          onChange={(e) => setQ(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === "Escape") e.currentTarget.blur(); }}
          rightElement={<Tag minimal className="kbd">/</Tag>} />
        <div className={`${Classes.TEXT_MUTED} search-hint`}>
          <code>"quoted phrase"</code> · <code>OR</code> · <code>-exclude</code>
        </div>
      </form>

      <div className="filter-scroll">
        <SavedSearches filters={filters} sort={sort} />

        <section className="facet">
          <div className="facet-title">Report date</div>
          <div className="date-range">
            <InputGroup small type="date" value={filters.report_date_from ?? ""} aria-label="Reported from"
              onPaste={pasteDate("report_date_from")}
              onChange={(e) => onChange(withFilter(filters, "report_date_from", e.currentTarget.value))} />
            <span className={Classes.TEXT_MUTED}>to</span>
            <InputGroup small type="date" value={filters.report_date_to ?? ""} aria-label="Reported to"
              onPaste={pasteDate("report_date_to")}
              onChange={(e) => onChange(withFilter(filters, "report_date_to", e.currentTarget.value))} />
          </div>
          <div className={`${Classes.TEXT_MUTED} facet-note`}>Submission date. Reports carry no incident date.</div>
        </section>

        <section className="facet">
          <Switch checked={filters.injury_only ?? false} label="Injury reports only"
            onChange={(e) => onChange(withFilter(filters, "injury_only", e.currentTarget.checked || undefined))} />
          <Switch checked={filters.has_company_comment ?? false} label="Manufacturer responded"
            onChange={(e) => onChange(withFilter(filters, "has_company_comment", e.currentTarget.checked || undefined))} />
        </section>

        {FACET_ORDER.map((field) => (
          <FacetSection key={field} field={field} values={facets?.[field]} filters={filters} onChange={onChange} />
        ))}

        <section className="facet">
          <FormGroup label="Brand (exact)" inline={false} className="text-filter">
            <ExactInput value={filters.brand} onCommit={(v) => onChange(withFilter(filters, "brand", v))} />
          </FormGroup>
          <FormGroup label="Model (exact)" className="text-filter">
            <ExactInput value={filters.model} onCommit={(v) => onChange(withFilter(filters, "model", v))} />
          </FormGroup>
        </section>
      </div>
    </aside>
  );
});

function ExactInput({ value, onCommit }: { value: string | undefined; onCommit: (v: string | undefined) => void }) {
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => setDraft(value ?? ""), [value]);
  return (
    <InputGroup small value={draft} onChange={(e) => setDraft(e.currentTarget.value)}
      onBlur={() => { if (draft.trim() !== (value ?? "")) onCommit(draft.trim() || undefined); }}
      onKeyDown={(e) => { if (e.key === "Enter") onCommit(draft.trim() || undefined); }} />
  );
}

const COLLAPSED_COUNT = 6;

function FacetSection({ field, values, filters, onChange }: {
  field: FacetField; values: FacetValue[] | undefined; filters: Filters; onChange: (f: Filters) => void;
}) {
  const [open, setOpen] = useState(field === "hazard" || field === "severity" || field === "product_category");
  const [showAll, setShowAll] = useState(false);
  const active = (filters[field] ?? []) as string[];
  const list = values ?? [];
  const missing = active.filter((v) => !list.some((x) => x.value === v)).map((v) => ({ value: v, label: v, count: 0 }));
  const all = [...missing, ...list];
  const shown = showAll ? all : all.filter((v, i) => i < COLLAPSED_COUNT || active.includes(v.value));
  return (
    <section className="facet">
      <button type="button" className="facet-title facet-toggle" onClick={() => setOpen(!open)}>
        <Icon icon={open ? "chevron-down" : "chevron-right"} size={12} />
        {FILTER_LABELS[field]}
        {active.length > 0 && <Tag minimal round intent="primary" className="facet-active">{active.length}</Tag>}
      </button>
      <Collapse isOpen={open} keepChildrenMounted>
        {values === undefined && <div className={Classes.SKELETON}>loading</div>}
        {shown.map((v) => (
          <Checkbox key={v.value} className="facet-value" checked={active.includes(v.value)}
            onChange={() => onChange(toggleListValue(filters, field, v.value))}
            labelElement={<><span className="facet-label" title={v.label}>{v.label}</span>
              <span className="facet-count">{fmtCount(v.count)}</span></>} />
        ))}
        {all.length > shown.length || showAll ? (
          <Button minimal small className="facet-more" onClick={() => setShowAll(!showAll)}
            text={showAll ? "Show fewer" : `Show all ${all.length}`} />
        ) : null}
        {field === "hazard" && <div className={`${Classes.TEXT_MUTED} facet-note`}>Inferred from narrative phrases. May be wrong.</div>}
      </Collapse>
    </section>
  );
}
