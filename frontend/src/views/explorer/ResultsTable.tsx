import { Checkbox, Icon } from "@blueprintjs/core";
import { useEffect, useRef } from "react";
import type { IncidentSort, IncidentSummary } from "../../api/types";
import type { Column } from "./columns";

interface Props {
  rows: IncidentSummary[];
  columns: Column[];
  sort: IncidentSort;
  cursor: string | null;
  isSelected: (reportNo: string) => boolean;
  onToggle: (reportNo: string) => void;
  onToggleAll: (on: boolean) => void;
  onFocusRow: (reportNo: string) => void;
  onOpenRow: (reportNo: string) => void;
  onSort: (sort: IncidentSort) => void;
}

export function ResultsTable({ rows, columns, sort, cursor, isSelected, onToggle, onToggleAll, onFocusRow, onOpenRow, onSort }: Props) {
  const cursorRef = useRef<HTMLTableRowElement | null>(null);
  useEffect(() => cursorRef.current?.scrollIntoView({ block: "nearest" }), [cursor]);
  const selectedCount = rows.filter((r) => isSelected(r.report_no)).length;

  return (
    <table className="results-table bp5-html-table bp5-compact bp5-interactive">
      <thead>
        <tr>
          <th className="col-check">
            <Checkbox className="row-check" aria-label="Select page"
              checked={rows.length > 0 && selectedCount === rows.length}
              indeterminate={selectedCount > 0 && selectedCount < rows.length}
              onChange={(e) => onToggleAll(e.currentTarget.checked)} />
          </th>
          {columns.map((c) => {
            const active = c.sort && (sort === c.sort.desc || sort === c.sort.asc);
            const next = c.sort && (sort === c.sort.desc && c.sort.asc ? c.sort.asc : c.sort.desc);
            return (
              <th key={c.id} style={c.width ? { width: c.width } : undefined}
                className={c.sort ? `sortable ${active ? "sorted" : ""}` : undefined}
                onClick={next ? () => onSort(next) : undefined}
                aria-sort={active ? (sort === c.sort?.asc ? "ascending" : "descending") : undefined}>
                {c.label}
                {active && <Icon icon={sort === c.sort?.asc ? "chevron-up" : "chevron-down"} size={12} />}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isCursor = row.report_no === cursor;
          const selected = isSelected(row.report_no);
          return (
            <tr key={row.report_no} ref={isCursor ? cursorRef : undefined}
              className={`${isCursor ? "cursor" : ""} ${selected ? "selected" : ""}`}
              onClick={() => onFocusRow(row.report_no)}
              onDoubleClick={() => onOpenRow(row.report_no)}>
              <td className="col-check" onClick={(e) => e.stopPropagation()}>
                <Checkbox className="row-check" checked={selected} aria-label={`Select ${row.report_no}`}
                  onChange={() => onToggle(row.report_no)} />
              </td>
              {columns.map((c) => <td key={c.id}>{c.render(row)}</td>)}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
