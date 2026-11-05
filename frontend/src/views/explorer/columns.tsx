import { Icon, Tag, Tooltip } from "@blueprintjs/core";
import type { ReactNode } from "react";
import type { IncidentSort, IncidentSummary } from "../../api/types";
import { HazardTags } from "../../components/HazardTags";
import { Marked } from "../../components/text";

export interface Column {
  id: string;
  label: string;
  width?: number;
  sort?: { desc: IncidentSort; asc?: IncidentSort };
  defaultVisible: boolean;
  render: (row: IncidentSummary) => ReactNode;
}

export const COLUMNS: Column[] = [
  { id: "report_no", label: "Report No.", width: 200, defaultVisible: true, render: (r) => <span className="mono">{r.report_no}</span> },
  {
    id: "report_date", label: "Reported", width: 88, defaultVisible: true,
    sort: { desc: "report_date", asc: "-report_date" }, render: (r) => r.report_date,
  },
  {
    id: "publication_date", label: "Published", width: 92, defaultVisible: false,
    sort: { desc: "publication_date" }, render: (r) => r.publication_date,
  },
  {
    id: "severity", label: "Severity", width: 130, defaultVisible: true, sort: { desc: "severity" },
    render: (r) => <SeverityCell row={r} />,
  },
  {
    id: "product", label: "Product", width: 220, defaultVisible: true,
    render: (r) => <span className="cell-clip" title={r.product_description}>{r.product_description}</span>,
  },
  { id: "product_category", label: "Category", width: 150, defaultVisible: false, render: (r) => <span title={r.product_category}>{r.product_category}</span> },
  {
    id: "product_type", label: "Product type", width: 160, defaultVisible: false,
    render: (r) => <span className="cell-clip" title={`${r.product_type ?? ""} (${r.product_code})`}>{r.product_type ?? r.product_code}</span>,
  },
  {
    id: "manufacturer", label: "Manufacturer", width: 140, defaultVisible: true,
    render: (r) => <span className="cell-clip" title={`Reported: ${r.manufacturer_name}`}>{r.manufacturer_name}</span>,
  },
  { id: "brand", label: "Brand", width: 110, defaultVisible: false, render: (r) => <span title={r.brand ?? undefined}>{r.brand ?? ""}</span> },
  { id: "model", label: "Model", width: 100, defaultVisible: true, render: (r) => <span className="mono" title={r.model ?? undefined}>{r.model ?? ""}</span> },
  { id: "state", label: "State", width: 96, defaultVisible: false, render: (r) => <span title={r.state ?? undefined}>{r.state ?? ""}</span> },
  { id: "victim_age", label: "Age", width: 44, defaultVisible: false, render: (r) => r.victim_age ?? "" },
  {
    id: "hazards", label: "Hazards (inferred)", width: 150, defaultVisible: true,
    render: (r) => <HazardTags hazards={r.hazards} />,
  },
  {
    id: "company", label: "Mfr.", width: 40, defaultVisible: true,
    render: (r) => r.has_company_comment
      ? <Tooltip content="Manufacturer responded"><Icon icon="office" size={12} /></Tooltip>
      : null,
  },
  {
    id: "investigations", label: "Inv.", width: 48, defaultVisible: true,
    render: (r) => r.investigation_ids.length > 0
      ? <Tooltip content={`In investigation ${r.investigation_ids.map((i) => `#${i}`).join(", ")}`}>
          <Tag minimal intent="success" icon="folder-close">{r.investigation_ids.length}</Tag>
        </Tooltip>
      : null,
  },
  {
    id: "snippet", label: "Narrative", defaultVisible: true,
    render: (r) => <span className="cell-clip snippet"><Marked html={r.snippet} /></span>,
  },
];

function SeverityCell({ row }: { row: IncidentSummary }) {
  const intent = row.severity_rank >= 8 ? "danger" : row.is_injury ? "warning" : "none";
  return (
    <span className={`severity severity-${intent}`} title={row.severity}>
      <span className="severity-rank">{row.severity_rank}</span>
      <span className="cell-clip">{row.severity}</span>
    </span>
  );
}
