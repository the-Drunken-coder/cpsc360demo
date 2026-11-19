import { HTMLTable } from "@blueprintjs/core";
import type { LabReport } from "../../api/heuristicLab";

export function StartingReports({ reports }: { reports: LabReport[] }) {
  return <details className="lab-starting-reports">
    <summary>{reports.length} {reports.length === 1 ? "report" : "reports"} available at the starting date</summary>
    {reports.length === 0 ? <p>The scenario has no reports available by this date.</p> : (
      <div className="lab-table-scroll">
        <HTMLTable compact className="full-width">
          <thead><tr><th>Available</th><th>Product</th><th>Report</th></tr></thead>
          <tbody>{reports.map((report) => <tr key={report.id}>
            <td className="nowrap">{report.available_on}</td>
            <td>{report.product}</td>
            <td><code>{report.id}</code> · {report.narrative}
              {report.facts && Object.keys(report.facts).length > 0 && <div className="lab-subtle">
                {Object.entries(report.facts).map(([field, value]) => `${field.replaceAll("_", " ")}: ${typeof value === "boolean" ? value ? "yes" : "no" : value}`).join(" · ")}
              </div>}
            </td>
          </tr>)}</tbody>
        </HTMLTable>
      </div>
    )}
  </details>;
}
