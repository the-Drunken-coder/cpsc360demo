import { Button, Callout, Classes, NonIdealState, Spinner, Tag, Tooltip } from "@blueprintjs/core";
import { useQueries, useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, qk } from "../../api/client";
import type { AgreementField, IncidentDetail, PatternAnalysis } from "../../api/types";
import { Provenance } from "../../components/Provenance";
import { BulkActions } from "../../components/SelectionBadge";
import { Highlighted, ReportLink } from "../../components/text";
import { HAZARD_LABELS } from "../../domain/hazards";

const AGREEMENT_LABELS: Record<AgreementField, string> = {
  manufacturer_key: "Manufacturer",
  brand_key: "Brand",
  model_key: "Model",
  product_code: "Product type",
  product_category: "Category",
  state: "State",
  severity: "Severity",
};

// Cells show each report's own reported spelling; the canonical key only decides which cells share a color.
const REPORTED_VALUE: Record<AgreementField, (d: IncidentDetail) => string | null> = {
  manufacturer_key: (d) => d.reported.manufacturer_name,
  brand_key: (d) => d.reported.brand,
  model_key: (d) => d.reported.model,
  product_code: (d) => d.reported.product_type ?? d.reported.product_code,
  product_category: (d) => d.reported.product_category,
  state: (d) => d.reported.state,
  severity: (d) => d.reported.severity,
};

const GROUP_CLASSES = 5;

type Agreement = Map<string, { label: string; group: number | null }>;

function agreementFor(patterns: PatternAnalysis, field: AgreementField): Agreement {
  const out: Agreement = new Map();
  const values = patterns.field_agreement.find((f) => f.field === field)?.values ?? [];
  let group = 0;
  for (const v of values) {
    const shared = v.value !== null && v.report_nos.length >= 2;
    const g = shared ? group++ % GROUP_CLASSES : null;
    for (const r of v.report_nos) out.set(r, { label: v.label, group: g });
  }
  return out;
}

export function CompareView() {
  const [params, setParams] = useSearchParams();
  const reportNos = [...new Set(params.getAll("r"))];
  const details = useQueries({
    queries: reportNos.map((r) => ({ queryKey: qk.incident(r), queryFn: () => api.incident(r) })),
  });
  const sortedKey = [...reportNos].sort();
  const patterns = useQuery({
    queryKey: qk.patterns(sortedKey),
    queryFn: () => api.patterns(reportNos),
    enabled: reportNos.length >= 2 && reportNos.length <= 50,
  });

  const remove = (r: string) => {
    const next = new URLSearchParams();
    reportNos.filter((x) => x !== r).forEach((x) => next.append("r", x));
    setParams(next);
  };

  if (reportNos.length < 2) {
    return <NonIdealState icon="comparison" title="Compare reports"
      description="Select two or more reports in the explorer, related list, or an investigation, then press c." />;
  }
  if (reportNos.length > 50) return <NonIdealState icon="error" title="Compare supports up to 50 reports" />;

  const p = patterns.data;
  const loaded = details.map((q) => q.data);
  const termsFor = (r: string) => (p?.shared_terms ?? []).filter((t) => t.report_nos.includes(r)).map((t) => t.term);

  const agreementRow = (field: AgreementField) => {
    const agreement = p ? agreementFor(p, field) : new Map();
    const groups = new Set([...agreement.values()].filter((a) => a.group !== null).map((a) => a.group));
    const allSame = p?.field_agreement.find((f) => f.field === field)?.values.length === 1 && agreement.get(reportNos[0]!)?.group !== null;
    return (
      <tr key={field}>
        <th>
          {AGREEMENT_LABELS[field]}
          {allSame ? <Tag minimal intent="success" className="agree-tag">all match</Tag>
            : groups.size > 0 ? <Tag minimal className="agree-tag">{groups.size} shared</Tag> : null}
        </th>
        {reportNos.map((r, i) => {
          const a = agreement.get(r);
          const d = loaded[i];
          const value = d ? REPORTED_VALUE[field](d) : a?.label;
          return (
            <td key={r} className={a?.group !== null && a?.group !== undefined ? `agree agree-${a.group}` : "differ"}>
              {value ?? <span className="empty-value">not reported</span>}
            </td>
          );
        })}
      </tr>
    );
  };

  const detailRow = (label: string, render: (d: IncidentDetail) => ReactNode) => (
    <tr key={label}>
      <th>{label}</th>
      {loaded.map((d, i) => <td key={reportNos[i]}>{d ? render(d) : <Spinner size={12} />}</td>)}
    </tr>
  );

  return (
    <div className="compare-view">
      <header className="compare-head">
        <h2>Compare {reportNos.length} reports</h2>
        {p && <Provenance tier="inferred" method={p.method} />}
        <span className="spacer" />
        <BulkActions reportNos={reportNos} />
      </header>

      {patterns.isError && <Callout intent="danger" title="Pattern analysis failed">{patterns.error.message}</Callout>}
      {p && (
        <div className="pattern-strip">
          <div className="pattern-stat"><span className="stat-label">Report dates</span><span>{p.date_range.first} → {p.date_range.last}</span></div>
          <div className="pattern-stat"><span className="stat-label">Injury reports</span><span>{p.injury_count}</span></div>
          <div className="pattern-stat"><span className="stat-label">Death reports</span><span className={p.death_count > 0 ? "danger-text" : ""}>{p.death_count}</span></div>
          <div className="pattern-block">
            <span className="stat-label">Shared hazards</span>
            {p.hazards.length === 0 ? <span className={Classes.TEXT_MUTED}>none</span> : p.hazards.map((h) => (
              <Tooltip key={h.hazard} content={h.report_nos.join(", ")}>
                <Tag minimal intent="warning">{h.label} {h.report_nos.length}/{reportNos.length}</Tag>
              </Tooltip>
            ))}
          </div>
          <div className="pattern-block">
            <span className="stat-label">Shared terms</span>
            {p.shared_terms.length === 0 ? <span className={Classes.TEXT_MUTED}>none</span> : p.shared_terms.map((t) => (
              <Tooltip key={t.term} content={t.report_nos.join(", ")}>
                <Tag minimal className="term">{t.term} {t.report_nos.length}/{reportNos.length}</Tag>
              </Tooltip>
            ))}
          </div>
        </div>
      )}

      <div className="compare-scroll">
        <table className="compare-table bp5-html-table bp5-compact">
          <thead>
            <tr>
              <th className="compare-corner">
                <span className={Classes.TEXT_MUTED}>Matching values share a color</span>
              </th>
              {reportNos.map((r) => (
                <th key={r}>
                  <ReportLink reportNo={r} />
                  <Button minimal small icon="cross" aria-label={`Remove ${r}`} onClick={() => remove(r)} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {detailRow("Product", (d) => d.reported.product_description)}
            {detailRow("Reported", (d) => d.reported.report_date)}
            {detailRow("Published", (d) => d.reported.publication_date)}
            {(Object.keys(AGREEMENT_LABELS) as AgreementField[]).map(agreementRow)}
            {detailRow("Victim age", (d) => d.reported.victim_age ?? <span className="empty-value">—</span>)}
            {detailRow("Hazards (inferred)", (d) => (
              <span className="hazard-tags">
                {d.inferred.hazards.map((h) => {
                  const shared = p?.hazards.find((x) => x.hazard === h.hazard && x.report_nos.length >= 2);
                  return <Tag key={h.hazard} minimal={!shared} intent="warning">{HAZARD_LABELS[h.hazard]}</Tag>;
                })}
              </span>
            ))}
            {detailRow("Mfr. responses", (d) => d.company_comments.length)}
            <tr className="narrative-row">
              <th>Narrative <Provenance tier="reported" /><div className={Classes.TEXT_MUTED}>Shared terms marked</div></th>
              {loaded.map((d, i) => (
                <td key={reportNos[i]}>
                  {d ? <div className="narrative compare-narrative">
                    <Highlighted text={d.reported.incident_description} terms={termsFor(d.reported.report_no)} />
                  </div> : <Spinner size={12} />}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
