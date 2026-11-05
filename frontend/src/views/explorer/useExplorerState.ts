import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { Filters, IncidentSort } from "../../api/types";
import { parseFilters, toSearchParams } from "../../domain/filters";

const SORTS: IncidentSort[] = ["relevance", "report_date", "-report_date", "severity", "publication_date"];

export const SORT_LABELS: Record<IncidentSort, string> = {
  relevance: "Relevance",
  report_date: "Newest reported",
  "-report_date": "Oldest reported",
  severity: "Most severe",
  publication_date: "Newest published",
};

export interface ExplorerState {
  filters: Filters;
  sort: IncidentSort;
  page: number;
  preview: string | null;
}

function parseState(params: URLSearchParams): ExplorerState {
  const filters = parseFilters(params);
  const rawSort = params.get("sort");
  const fallback: IncidentSort = filters.q ? "relevance" : "report_date";
  const sort = SORTS.find((s) => s === rawSort) ?? fallback;
  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);
  return { filters, sort: sort === "relevance" && !filters.q ? "report_date" : sort, page, preview: params.get("preview") };
}

function serialize(state: ExplorerState): URLSearchParams {
  const defaultSort = state.filters.q ? "relevance" : "report_date";
  return toSearchParams(state.filters, {
    sort: state.sort === defaultSort ? undefined : state.sort,
    page: state.page > 1 ? state.page : undefined,
    preview: state.preview ?? undefined,
  });
}

export function useExplorerState() {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseState(params), [params]);

  const update = useCallback((patch: Partial<ExplorerState>, replace = false) => {
    setParams((prev) => serialize({ ...parseState(prev), ...patch }), { replace });
  }, [setParams]);

  const setFilters = useCallback((filters: Filters) => {
    setParams((prev) => {
      const cur = parseState(prev);
      const sort = cur.sort === "relevance" && !filters.q ? "report_date" : !cur.filters.q && filters.q ? "relevance" : cur.sort;
      return serialize({ filters, sort, page: 1, preview: cur.preview });
    });
  }, [setParams]);

  return { ...state, update, setFilters };
}
