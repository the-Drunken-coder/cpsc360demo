import { AnchorButton, Button, ButtonGroup, Classes, HTMLSelect, NonIdealState, Spinner, Tooltip } from "@blueprintjs/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, qk } from "../../api/client";
import type { IncidentSort } from "../../api/types";
import { ActiveFilters } from "../../components/ActiveFilters";
import { useInvestigate } from "../../components/InvestigateProvider";
import { BulkActions, compareHref } from "../../components/SelectionBadge";
import { fmtCount } from "../../components/text";
import { toSearchParams } from "../../domain/filters";
import { toast, toastError } from "../../components/toaster";
import { useRegisteredHotkeys } from "../../hotkeys/registry";
import { useSelection } from "../../session/SelectionProvider";
import { ColumnChooser, useVisibleColumns } from "./ColumnChooser";
import { FilterPanel } from "./FilterPanel";
import { PreviewPanel } from "./PreviewPanel";
import { ResultsTable } from "./ResultsTable";
import { SORT_LABELS, useExplorerState } from "./useExplorerState";

const PAGE_SIZE = 100;

export function ExplorerView() {
  const { filters, sort, page, preview, update, setFilters } = useExplorerState();
  const navigate = useNavigate();
  const selection = useSelection();
  const investigate = useInvestigate();
  const { columns, visible, setVisible } = useVisibleColumns();
  const searchRef = useRef<HTMLInputElement>(null);
  const lastCursor = useRef(0);
  const [exporting, setExporting] = useState(false);

  const results = useQuery({
    queryKey: qk.incidents(filters, sort, page, PAGE_SIZE),
    queryFn: () => api.incidents(filters, sort, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  });
  const facets = useQuery({ queryKey: qk.facets(filters), queryFn: () => api.facets(filters), placeholderData: keepPreviousData });

  const rows = results.data?.items ?? [];
  const cursorIndex = preview ? rows.findIndex((r) => r.report_no === preview) : -1;
  if (cursorIndex >= 0) lastCursor.current = cursorIndex;
  const pages = results.data ? Math.max(1, Math.ceil(results.data.total / PAGE_SIZE)) : 1;

  const focusRow = (reportNo: string) => update({ preview: reportNo }, true);
  const moveCursor = (delta: number) => {
    if (rows.length === 0) return;
    const from = cursorIndex >= 0 ? cursorIndex : Math.min(lastCursor.current, rows.length - 1) - (delta > 0 ? 1 : 0);
    const next = Math.max(0, Math.min(rows.length - 1, from + delta));
    const row = rows[next];
    if (row) focusRow(row.report_no);
  };
  const targets = () => (selection.selected.length > 0 ? selection.selected : preview ? [preview] : []);

  useRegisteredHotkeys({
    focusSearch: () => searchRef.current?.focus(),
    next: () => moveCursor(1),
    prev: () => moveCursor(-1),
    toggle: () => { if (preview) selection.toggle(preview); },
    open: () => { if (preview) navigate(`/incidents/${preview}`); },
    close: () => update({ preview: null }, true),
    compare: () => {
      if (selection.selected.length >= 2) navigate(compareHref(selection.selected));
      else toast({ icon: "info-sign", message: "Select two or more reports to compare (x toggles the focused row)." });
    },
    investigate: () => investigate.open(targets()),
    related: () => { if (preview) navigate(`/incidents/${preview}/related`); },
  });

  const exportCsv = async () => {
    setExporting(true);
    try {
      const blob = await api.exportCsv(filters);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "saferproducts-reports.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toastError(e);
    } finally {
      setExporting(false);
    }
  };

  const sortOptions = (Object.keys(SORT_LABELS) as IncidentSort[]).filter((s) => s !== "relevance" || filters.q);

  return (
    <div className={`explorer ${preview ? "with-preview" : ""}`}>
      <FilterPanel ref={searchRef} filters={filters} sort={sort} facets={facets.data} onChange={setFilters} />
      <section className="results">
        <div className="results-toolbar">
          <span className="result-count">
            {results.data ? <><strong>{fmtCount(results.data.total)}</strong> reports</> : <Spinner size={14} />}
            {results.data && <span className={Classes.TEXT_MUTED}> · {Math.round(results.data.took_ms)} ms</span>}
            {results.isFetching && results.data && <Spinner size={12} className="inline-spinner" />}
          </span>
          <ActiveFilters filters={filters} facets={facets.data} onChange={setFilters} />
          <span className="spacer" />
          {selection.selected.length > 0 && (
            <span className="toolbar-selection">{selection.selected.length} selected</span>
          )}
          <BulkActions reportNos={selection.selected} onClear={selection.clear} />
          <HTMLSelect minimal value={sort} aria-label="Sort"
            onChange={(e) => update({ sort: e.currentTarget.value as IncidentSort, page: 1 })}>
            {sortOptions.map((s) => <option key={s} value={s}>{SORT_LABELS[s]}</option>)}
          </HTMLSelect>
          <Tooltip content="Trend, breakdown, and spikes for these filters">
            <AnchorButton small minimal icon="timeline-bar-chart" text="Trend"
              href={`/analytics?${toSearchParams(filters).toString()}`}
              onClick={(e) => { e.preventDefault(); navigate(`/analytics?${toSearchParams(filters).toString()}`); }} />
          </Tooltip>
          <ColumnChooser visible={visible} onChange={setVisible} />
          <Tooltip content="Current raw rows with original headers, up to 10,000">
            <Button small minimal icon="download" text="CSV" loading={exporting} onClick={() => void exportCsv()} />
          </Tooltip>
        </div>
        <div className="results-scroll">
          {results.isError && <NonIdealState icon="error" title="Search failed" description={results.error.message} />}
          {results.data && rows.length === 0 && (
            <NonIdealState icon="search" title="No matching reports" description="Remove a filter or broaden the search text." />
          )}
          {rows.length > 0 && (
            <ResultsTable rows={rows} columns={columns} sort={sort} cursor={preview}
              isSelected={selection.isSelected} onToggle={selection.toggle}
              onToggleAll={(on) => selection.setMany(rows.map((r) => r.report_no), on)}
              onFocusRow={focusRow} onOpenRow={(r) => navigate(`/incidents/${r}`)}
              onSort={(s) => update({ sort: s, page: 1 })} />
          )}
        </div>
        <div className="results-footer">
          <span className={Classes.TEXT_MUTED}>
            <kbd>j</kbd>/<kbd>k</kbd> move · <kbd>x</kbd> select · <kbd>Enter</kbd> open · <kbd>r</kbd> related · <kbd>c</kbd> compare · <kbd>?</kbd> all shortcuts
          </span>
          <span className="spacer" />
          <ButtonGroup minimal>
            <Button small icon="chevron-left" disabled={page <= 1} onClick={() => update({ page: page - 1 })} aria-label="Previous page" />
            <span className="page-label">Page {page} of {fmtCount(pages)}</span>
            <Button small icon="chevron-right" disabled={page >= pages} onClick={() => update({ page: page + 1 })} aria-label="Next page" />
          </ButtonGroup>
        </div>
      </section>
      {preview && (
        <PreviewPanel reportNo={preview}
          onClose={() => update({ preview: null }, true)}
          onOpen={() => navigate(`/incidents/${preview}`)}
          onRelated={() => navigate(`/incidents/${preview}/related`)} />
      )}
    </div>
  );
}
