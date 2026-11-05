import { Button, HTMLSelect, HTMLTable, InputGroup, NonIdealState, Spinner, Tag } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { InvestigationStatus } from "../../api/types";
import { useInvestigate } from "../../components/InvestigateProvider";
import { STATUS_META, StatusTag } from "../../components/StatusTag";
import { fmtTime } from "../../components/text";
import { useSelection } from "../../session/SelectionProvider";
import { useSession } from "../../session/SessionProvider";

export function InvestigationsList() {
  const { users, canWrite } = useSession();
  const navigate = useNavigate();
  const investigate = useInvestigate();
  const selection = useSelection();
  const [status, setStatus] = useState<InvestigationStatus | "">("");
  const [assignee, setAssignee] = useState<number | "">("");
  const [label, setLabel] = useState("");
  const query = { status: status || undefined, assignee_id: assignee === "" ? undefined : assignee, label: label.trim() || undefined };
  const list = useQuery({ queryKey: ["investigations", query], queryFn: () => api.investigations(query) });

  return (
    <div className="page">
      <header className="page-head">
        <h2>Investigations</h2>
        <HTMLSelect minimal value={status} onChange={(e) => setStatus(e.currentTarget.value as InvestigationStatus | "")} aria-label="Status">
          <option value="">Any status</option>
          {(Object.keys(STATUS_META) as InvestigationStatus[]).map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
        </HTMLSelect>
        <HTMLSelect minimal value={assignee} onChange={(e) => setAssignee(e.currentTarget.value === "" ? "" : Number(e.currentTarget.value))} aria-label="Assignee">
          <option value="">Any assignee</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
        </HTMLSelect>
        <InputGroup small leftIcon="tag" placeholder="Label" value={label} onChange={(e) => setLabel(e.currentTarget.value)} />
        <span className="spacer" />
        <Button small icon="folder-new" intent="primary" disabled={!canWrite || selection.selected.length === 0}
          text={selection.selected.length > 0 ? `New from ${selection.selected.length} selected` : "Select reports to start one"}
          onClick={() => investigate.open(selection.selected)} />
      </header>
      {list.isPending && <Spinner />}
      {list.isError && <NonIdealState icon="error" description={list.error.message} />}
      {list.data?.length === 0 && (
        <NonIdealState icon="folder-shared" title="No investigations"
          description="Select reports in the explorer and press i to group them into an investigation." />
      )}
      {list.data && list.data.length > 0 && (
        <HTMLTable compact interactive className="full-width dense-table">
          <thead>
            <tr><th>#</th><th>Title</th><th>Status</th><th>Labels</th><th>Assignee</th><th>Reports</th><th>Latest report</th><th>Updated</th></tr>
          </thead>
          <tbody>
            {list.data.map((i) => (
              <tr key={i.id} onClick={() => navigate(`/investigations/${i.id}`)}>
                <td className="mono">{i.id}</td>
                <td><Link to={`/investigations/${i.id}`} onClick={(e) => e.stopPropagation()}>{i.title}</Link></td>
                <td><StatusTag status={i.status} /></td>
                <td>{i.labels.map((l) => <Tag key={l} minimal className="label-tag">{l}</Tag>)}</td>
                <td>{i.assignee?.display_name ?? "Unassigned"}</td>
                <td>{i.incident_count}</td>
                <td>{i.latest_report_date ?? "—"}</td>
                <td>{fmtTime(i.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </HTMLTable>
      )}
    </div>
  );
}
