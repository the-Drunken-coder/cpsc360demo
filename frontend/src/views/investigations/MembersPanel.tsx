import { Button, Checkbox, Classes, HTMLTable, NonIdealState, Tooltip } from "@blueprintjs/core";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Investigation } from "../../api/types";
import { HazardTags } from "../../components/HazardTags";
import { BulkActions, compareHref, MAX_COMPARE_REPORTS } from "../../components/SelectionBadge";
import { ReportLink, fmtTime } from "../../components/text";
import { toast } from "../../components/toaster";
import { explorerHref } from "../../domain/filters";
import { useRegisteredHotkeys } from "../../hotkeys/registry";
import { useSession } from "../../session/SessionProvider";
import { useInvestigationMutations } from "./InvestigationView";

export function MembersPanel({ investigation }: { investigation: Investigation }) {
  const { canWrite } = useSession();
  const { removeMember } = useInvestigationMutations(investigation.id);
  const navigate = useNavigate();
  const [picked, setSelected] = useState<string[]>([]);
  const members = investigation.incidents;
  const all = members.map((m) => m.incident.report_no);
  const selected = picked.filter((r) => all.includes(r));
  const toggle = (r: string) => setSelected((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  useRegisteredHotkeys({
    compare: () => {
      if (selected.length < 2) {
        toast({ icon: "info-sign", message: "Select two or more reports to compare." });
      } else if (selected.length > MAX_COMPARE_REPORTS) {
        toast({ icon: "warning-sign", message: `Compare supports up to ${MAX_COMPARE_REPORTS} reports.` });
      } else {
        navigate(compareHref(selected));
      }
    },
  });

  if (members.length === 0) {
    return <NonIdealState icon="document" title="No reports yet"
      description="Add reports from the explorer, a related list, or the compare view." />;
  }
  return (
    <div className="members">
      <div className="panel-toolbar">
        <Link to={explorerHref({ in_investigation: investigation.id })}>Open members in explorer</Link>
        <span className="spacer" />
        <span className="toolbar-selection">{selected.length > 0 ? `${selected.length} selected` : "Compare uses all reports when none are selected"}</span>
        <BulkActions reportNos={selected.length > 0 ? selected : all} onClear={selected.length > 0 ? () => setSelected([]) : undefined} />
      </div>
      <HTMLTable compact className="full-width dense-table members-table">
        <thead>
          <tr>
            <th className="col-check">
              <Checkbox className="row-check" checked={selected.length === all.length} aria-label="Select all"
                indeterminate={selected.length > 0 && selected.length < all.length}
                onChange={(e) => setSelected(e.currentTarget.checked ? all : [])} />
            </th>
            <th>Report No.</th><th>Reported</th><th>Product</th><th>Manufacturer</th><th>Model</th><th>Severity</th>
            <th>Hazards (inferred)</th><th>Rationale (analyst)</th><th>Added</th><th />
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.incident.report_no} className={selected.includes(m.incident.report_no) ? "selected" : ""}>
              <td className="col-check">
                <Checkbox className="row-check" checked={selected.includes(m.incident.report_no)}
                  onChange={() => toggle(m.incident.report_no)} aria-label={`Select ${m.incident.report_no}`} />
              </td>
              <td><ReportLink reportNo={m.incident.report_no} /></td>
              <td className="member-reported">{m.incident.report_date}</td>
              <td className="cell-wrap member-product">{m.incident.product_description}</td>
              <td>{m.incident.manufacturer_name}</td>
              <td className="mono">{m.incident.model ?? ""}</td>
              <td>{m.incident.severity}</td>
              <td><HazardTags hazards={m.incident.hazards} /></td>
              <td className="cell-wrap">{m.rationale || <span className={Classes.TEXT_MUTED}>—</span>}</td>
              <td className={`${Classes.TEXT_MUTED} member-added`}>
                <span className="member-added-name">{m.added_by.display_name}</span>
                <span className="member-added-time">{fmtTime(m.added_at)}</span>
              </td>
              <td>
                <Tooltip content={canWrite ? "Remove from investigation" : "Read-only viewer"}>
                  <Button minimal small icon="remove" intent="danger" disabled={!canWrite || removeMember.isPending}
                    aria-label={`Remove ${m.incident.report_no}`} onClick={() => removeMember.mutate(m.incident.report_no)} />
                </Tooltip>
              </td>
            </tr>
          ))}
        </tbody>
      </HTMLTable>
    </div>
  );
}
