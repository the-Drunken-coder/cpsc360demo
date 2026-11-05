import {
  Breadcrumbs, Button, ButtonGroup, Classes, EditableText, HTMLSelect, NonIdealState, Spinner, Tab, Tabs, TagInput, Tooltip,
} from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, qk } from "../../api/client";
import type { Investigation, InvestigationStatus } from "../../api/types";
import { Provenance } from "../../components/Provenance";
import { STATUS_META, StatusTag } from "../../components/StatusTag";
import { fmtTime } from "../../components/text";
import { toastError } from "../../components/toaster";
import { useSession } from "../../session/SessionProvider";
import { AuditPanel } from "./AuditPanel";
import { MembersPanel } from "./MembersPanel";
import { NotesPanel } from "./NotesPanel";
import { SummaryPanel } from "./SummaryPanel";

const STATUS_MACHINE: Record<InvestigationStatus, InvestigationStatus[]> = {
  open: ["in_review"],
  in_review: ["open", "escalated", "closed"],
  escalated: ["closed", "in_review"],
  closed: ["open"],
};

const TRANSITION_VERB: Record<InvestigationStatus, string> = {
  open: "Reopen",
  in_review: "Send to review",
  escalated: "Escalate",
  closed: "Close",
};

type Patch = Parameters<typeof api.updateInvestigation>[1];

export function useInvestigationMutations(id: number) {
  const queryClient = useQueryClient();
  const settle = (inv: Investigation) => {
    queryClient.setQueryData(qk.investigation(id), inv);
    void queryClient.invalidateQueries({ queryKey: ["investigations"] });
    void queryClient.invalidateQueries({ queryKey: qk.audit(id) });
    void queryClient.invalidateQueries({ queryKey: ["incidents"] });
    void queryClient.invalidateQueries({ queryKey: ["incident"] });
  };
  const patch = useMutation({ mutationFn: (body: Patch) => api.updateInvestigation(id, body), onSuccess: settle, onError: toastError });
  const removeMember = useMutation({ mutationFn: (reportNo: string) => api.removeMember(id, reportNo), onSuccess: settle, onError: toastError });
  return { patch, removeMember };
}

type TabId = "reports" | "notes" | "summary" | "audit";
const TABS: TabId[] = ["reports", "notes", "summary", "audit"];

export function InvestigationView() {
  const params = useParams();
  const id = Number(params.id);
  const tab: TabId = TABS.find((t) => t === params.tab) ?? "reports";
  const navigate = useNavigate();
  const { canWrite, users } = useSession();
  const inv = useQuery({ queryKey: qk.investigation(id), queryFn: () => api.investigation(id), enabled: Number.isInteger(id) });
  const { patch } = useInvestigationMutations(id);

  if (inv.isPending) return <NonIdealState icon={<Spinner />} title={`Loading investigation #${params.id}`} />;
  if (inv.isError) return <NonIdealState icon="error" title={`Investigation #${params.id}`} description={inv.error.message} />;
  const i = inv.data;

  return (
    <div className="investigation-view">
      <header className="investigation-head">
        <Breadcrumbs items={[
          { text: "Investigations", icon: "folder-shared", onClick: () => navigate("/investigations") },
          { text: `#${i.id}` },
        ]} />
        <div className="investigation-title-row">
          <h2 className="investigation-title">
            <EditableText key={`t${i.updated_at}`} defaultValue={i.title} disabled={!canWrite} placeholder="Title"
              onConfirm={(title) => { if (title.trim() && title !== i.title) patch.mutate({ title: title.trim() }); }} />
          </h2>
          <Provenance tier="analyst" by={i.created_by.display_name} />
          <span className="spacer" />
          <StatusTag status={i.status} />
          <ButtonGroup>
            {STATUS_MACHINE[i.status].map((to) => {
              const allowed = i.allowed_transitions.includes(to);
              const why = !canWrite ? "Read-only viewer" : allowed ? `Set status to ${STATUS_META[to].label}` : "Only a lead can set this status";
              return (
                <Tooltip key={to} content={why}>
                  <Button small text={TRANSITION_VERB[to]} intent={allowed ? STATUS_META[to].intent : "none"}
                    disabled={!allowed || patch.isPending} onClick={() => patch.mutate({ status: to })} />
                </Tooltip>
              );
            })}
          </ButtonGroup>
        </div>
        <div className="investigation-meta">
          <label className="meta-field">
            <span className="stat-label">Assignee</span>
            <HTMLSelect minimal disabled={!canWrite} value={i.assignee?.id ?? ""}
              onChange={(e) => patch.mutate({ assignee_id: e.currentTarget.value === "" ? null : Number(e.currentTarget.value) })}>
              <option value="">Unassigned</option>
              {users.filter((u) => u.role !== "viewer").map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
            </HTMLSelect>
          </label>
          <div className="meta-field labels-field">
            <span className="stat-label">Labels</span>
            <TagInput values={i.labels} disabled={!canWrite} addOnBlur placeholder="Add label…"
              onChange={(values) => patch.mutate({ labels: values.map(String) })} />
          </div>
          <span className={Classes.TEXT_MUTED}>
            Created by {i.created_by.display_name} {fmtTime(i.created_at)} · updated {fmtTime(i.updated_at)}
          </span>
        </div>
        <div className="investigation-description">
          <EditableText key={`d${i.updated_at}`} multiline minLines={2} defaultValue={i.description} disabled={!canWrite}
            placeholder={canWrite ? "Add a description: what links these reports, what to establish next…" : "No description."}
            onConfirm={(description) => { if (description !== i.description) patch.mutate({ description }); }} />
        </div>
      </header>
      <Tabs id="investigation-tabs" selectedTabId={tab} renderActiveTabPanelOnly className="investigation-tabs"
        onChange={(t) => navigate(`/investigations/${id}${t === "reports" ? "" : `/${String(t)}`}`, { replace: true })}>
        <Tab id="reports" title={`Reports (${i.incidents.length})`} panel={<MembersPanel investigation={i} />} />
        <Tab id="notes" title={`Notes (${i.notes.length})`} panel={<NotesPanel investigation={i} />} />
        <Tab id="summary" title="Summary" panel={<SummaryPanel investigation={i} />} />
        <Tab id="audit" title="Audit trail" panel={<AuditPanel id={i.id} />} />
      </Tabs>
    </div>
  );
}
