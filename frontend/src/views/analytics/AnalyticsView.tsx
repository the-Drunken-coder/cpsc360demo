import { Callout, Classes, HTMLSelect, HTMLTable, InputGroup, NonIdealState, Spinner, Tag } from "@blueprintjs/core";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, qk } from "../../api/client";
import type {
  BreakdownDimension, Filters, SpikeDimension, TrendGroupBy, TrendInterval,
} from "../../api/types";
import { ActiveFilters } from "../../components/ActiveFilters";
import { Provenance } from "../../components/Provenance";
import { fmtCount } from "../../components/text";
import { explorerHref, parseFilters, toSearchParams, withFilter } from "../../domain/filters";
import { isDrillable, withGroup } from "../../domain/drilldown";
import { DIMENSION_LABELS } from "../../domain/labels";
import { clampRange, periodRange } from "../../domain/periods";
import { TrendChart } from "./TrendChart";

const INTERVALS: TrendInterval[] = ["month", "quarter", "year"];
const GROUP_BYS: TrendGroupBy[] = ["none", "hazard", "product_category", "product_code", "manufacturer_key", "severity"];
const DIMENSIONS: BreakdownDimension[] = ["product_code", "product_category", "manufacturer_key", "hazard", "severity", "state"];
const SPIKE_DIMENSIONS: SpikeDimension[] = ["product_code", "manufacturer_key", "hazard"];
const WINDOWS = [30, 60, 90, 180];

function pick<T extends string>(value: string | null, options: readonly T[], fallback: T): T {
  return options.find((o) => o === value) ?? fallback;
}

function useAnalyticsParams() {
  const [params, setParams] = useSearchParams();
  const filters = parseFilters(params);
  const view = {
    interval: pick(params.get("interval"), INTERVALS, "month"),
    group_by: pick(params.get("group_by"), GROUP_BYS, "none"),
    dimension: pick(params.get("dimension"), DIMENSIONS, "product_code"),
    spike_dimension: pick(params.get("spike_dimension"), SPIKE_DIMENSIONS, "product_code"),
    window_days: WINDOWS.find((w) => String(w) === params.get("window_days")) ?? 90,
  };
  const set = (nextFilters: Filters, patch: Partial<typeof view> = {}) =>
    setParams(toSearchParams(nextFilters, { ...view, ...patch }), { replace: true });
  return { filters, view, set };
}

export function AnalyticsView() {
  const { filters, view, set } = useAnalyticsParams();
  const navigate = useNavigate();
  const [q, setQ] = useState(filters.q ?? "");
  useEffect(() => setQ(filters.q ?? ""), [filters.q]);

  const trend = useQuery({
    queryKey: qk.trend(filters, view.interval, view.group_by),
    queryFn: () => api.trend(filters, view.interval, view.group_by),
    placeholderData: keepPreviousData,
  });
  const breakdown = useQuery({
    queryKey: qk.breakdown(filters, view.dimension),
    queryFn: () => api.breakdown(filters, view.dimension),
    placeholderData: keepPreviousData,
  });
  const spikes = useQuery({
    queryKey: qk.spikes(view.spike_dimension, view.window_days),
    queryFn: () => api.spikes(view.spike_dimension, view.window_days),
    placeholderData: keepPreviousData,
  });
  const facets = useQuery({ queryKey: qk.facets(filters), queryFn: () => api.facets(filters), placeholderData: keepPreviousData });

  const caveat = trend.data?.caveat ?? breakdown.data?.caveat ?? spikes.data?.caveat;
  const maxCount = Math.max(1, ...(breakdown.data?.rows.map((r) => r.count) ?? [1]));

  const openTrendPoint = (seriesIndex: number, period: string) => {
    const t = trend.data;
    const s = t?.series[seriesIndex];
    if (!t || !s || trend.isPlaceholderData || !isDrillable(s.key)) return;
    const range = clampRange(periodRange(period, t.interval), { from: filters.report_date_from, to: filters.report_date_to });
    let next: Filters = { ...filters, report_date_from: range.from, report_date_to: range.to };
    if (view.group_by !== "none") next = withGroup(next, view.group_by, s.key);
    navigate(explorerHref(next));
  };

  return (
    <div className="analytics page">
      <Callout intent="warning" icon="warning-sign" className="caveat" title="Counts of public reports, not incident rates">
        {caveat ?? "Loading caveat…"}
      </Callout>

      <div className="analytics-filters">
        <form onSubmit={(e) => { e.preventDefault(); set(withFilter(filters, "q", q.trim())); }}>
          <InputGroup small leftIcon="search" placeholder="Narrow by text…" value={q} onChange={(e) => setQ(e.currentTarget.value)} />
        </form>
        <ActiveFilters filters={filters} facets={facets.data} onChange={(f) => set(f)} />
        <span className="spacer" />
        <Link to={explorerHref(filters)}>Refine filters in explorer</Link>
      </div>

      <section className="panel">
        <header className="panel-head">
          <h3>Reports by report date</h3>
          <HTMLSelect minimal value={view.interval} aria-label="Interval"
            onChange={(e) => set(filters, { interval: e.currentTarget.value as TrendInterval })}>
            {INTERVALS.map((i) => <option key={i} value={i}>by {i}</option>)}
          </HTMLSelect>
          <HTMLSelect minimal value={view.group_by} aria-label="Group by"
            onChange={(e) => set(filters, { group_by: e.currentTarget.value as TrendGroupBy })}>
            {GROUP_BYS.map((g) => <option key={g} value={g}>{g === "none" ? "no grouping" : `grouped by ${DIMENSION_LABELS[g].toLowerCase()}`}</option>)}
          </HTMLSelect>
          {trend.isFetching && <Spinner size={14} />}
          <span className="spacer" />
          {trend.data && (
            <span className={Classes.TEXT_MUTED}>
              Shaded: after {trend.data.incomplete_after}, publication lag leaves counts incomplete.
              {trend.data.series.some((s) => s.key === "__other__") && " “Other” is not clickable: filters cannot exclude groups."}
            </span>
          )}
        </header>
        {trend.isError && <NonIdealState icon="error" description={trend.error.message} />}
        {trend.data && trend.data.series.length === 0 && <NonIdealState icon="timeline-bar-chart" title="No reports match" />}
        {trend.data && trend.data.series.length > 0 && (
          <TrendChart series={trend.data.series} interval={trend.data.interval}
            incompleteAfter={trend.data.incomplete_after} onPick={openTrendPoint} />
        )}
      </section>

      <div className="analytics-grid">
        <section className="panel">
          <header className="panel-head">
            <h3>Breakdown</h3>
            <HTMLSelect minimal value={view.dimension} aria-label="Dimension"
              onChange={(e) => set(filters, { dimension: e.currentTarget.value as BreakdownDimension })}>
              {DIMENSIONS.map((d) => <option key={d} value={d}>by {DIMENSION_LABELS[d].toLowerCase()}</option>)}
            </HTMLSelect>
            {breakdown.isFetching && <Spinner size={14} />}
          </header>
          {breakdown.isError && <NonIdealState icon="error" description={breakdown.error.message} />}
          {breakdown.data && (
            <HTMLTable compact interactive className="full-width dense-table breakdown-table">
              <thead><tr><th>{DIMENSION_LABELS[breakdown.data.dimension]}</th><th className="num">Reports</th><th /><th className="num">Injury</th><th className="num">Death</th></tr></thead>
              <tbody>
                {breakdown.data.rows.map((r) => (
                  <tr key={r.key} className={isDrillable(r.key) ? undefined : "not-drillable"}
                    title={isDrillable(r.key) ? undefined : "Reports with no value here cannot be filtered on"}
                    onClick={() => isDrillable(r.key) && !breakdown.isPlaceholderData && navigate(explorerHref(withGroup(filters, breakdown.data.dimension, r.key)))}>
                    <td className="cell-clip" title={r.label}>{r.label}</td>
                    <td className="num">{fmtCount(r.count)}</td>
                    <td className="bar-cell"><div className="inline-bar" style={{ width: `${(r.count / maxCount) * 100}%` }} /></td>
                    <td className="num">{fmtCount(r.injury_count)}</td>
                    <td className={`num ${r.death_count > 0 ? "danger-text" : ""}`}>{fmtCount(r.death_count)}</td>
                  </tr>
                ))}
              </tbody>
            </HTMLTable>
          )}
        </section>

        <section className="panel">
          <header className="panel-head">
            <h3>Spikes</h3>
            <HTMLSelect minimal value={view.spike_dimension} aria-label="Spike dimension"
              onChange={(e) => set(filters, { spike_dimension: e.currentTarget.value as SpikeDimension })}>
              {SPIKE_DIMENSIONS.map((d) => <option key={d} value={d}>by {DIMENSION_LABELS[d].toLowerCase()}</option>)}
            </HTMLSelect>
            <HTMLSelect minimal value={view.window_days} aria-label="Window"
              onChange={(e) => set(filters, { window_days: Number(e.currentTarget.value) })}>
              {WINDOWS.map((w) => <option key={w} value={w}>{w}-day window</option>)}
            </HTMLSelect>
            {spikes.data && <Provenance tier="inferred" method={spikes.data.method} />}
            {spikes.isFetching && <Spinner size={14} />}
          </header>
          {spikes.data && (
            <p className={`${Classes.TEXT_MUTED} spike-explainer`}>
              Window {spikes.data.window.start} → {spikes.data.window.end} vs. baseline {spikes.data.baseline.start} → {spikes.data.baseline.end},
              scaled to the window. Kept when z ≥ 3. Covers all reports, not the filters above.
            </p>
          )}
          {spikes.isError && <NonIdealState icon="error" description={spikes.error.message} />}
          {spikes.data && spikes.data.rows.length === 0 && <NonIdealState icon="pulse" title="No spikes at z ≥ 3" />}
          {spikes.data && spikes.data.rows.length > 0 && (
            <HTMLTable compact interactive className="full-width dense-table">
              <thead><tr><th>{DIMENSION_LABELS[view.spike_dimension]}</th><th className="num">Recent</th><th className="num">Expected</th><th className="num">Ratio</th><th className="num">z</th></tr></thead>
              <tbody>
                {spikes.data.rows.map((s) => (
                  <tr key={s.key} onClick={() => navigate(explorerHref(s.filters))}>
                    <td className="cell-clip" title={s.label}>{s.label}</td>
                    <td className="num">{fmtCount(s.recent_count)}</td>
                    <td className="num">{s.expected_count.toFixed(1)}</td>
                    <td className="num">{s.ratio.toFixed(1)}×</td>
                    <td className="num"><Tag minimal intent={s.z >= 6 ? "danger" : "warning"}>{s.z.toFixed(1)}</Tag></td>
                  </tr>
                ))}
              </tbody>
            </HTMLTable>
          )}
        </section>
      </div>
      <p className={`${Classes.TEXT_MUTED} analytics-foot`}>
        Every bar, point, and row opens the explorer filtered to the reports it counts.
      </p>
    </div>
  );
}
