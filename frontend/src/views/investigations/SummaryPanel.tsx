import { Button, Callout, Classes, Menu, MenuItem, NonIdealState, Spinner } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/client";
import type { Investigation } from "../../api/types";
import { Provenance } from "../../components/Provenance";
import { ReportLink, fmtTime } from "../../components/text";
import { toastError } from "../../components/toaster";
import { useSession } from "../../session/SessionProvider";

export function SummaryPanel({ investigation }: { investigation: Investigation }) {
  const id = investigation.id;
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const summaries = useQuery({ queryKey: qk.summaries(id), queryFn: () => api.summaries(id) });
  const [chosen, setChosen] = useState<number | null>(null);
  const generate = useMutation({
    mutationFn: () => api.generateSummary(id),
    onSuccess: (s) => {
      setChosen(s.id);
      void queryClient.invalidateQueries({ queryKey: qk.summaries(id) });
      void queryClient.invalidateQueries({ queryKey: qk.audit(id) });
    },
    onError: toastError,
  });

  const list = summaries.data ?? [];
  const snapshot = list.find((s) => s.id === chosen) ?? list[0];
  const members = investigation.incidents.map((m) => m.incident.report_no).sort();
  const stale = snapshot && snapshot.member_report_nos.slice().sort().join() !== members.join();

  return (
    <div className="summary-layout">
      <div className="summary-main">
        <div className="panel-toolbar">
          <Button intent="primary" icon="manual" text="Generate summary" loading={generate.isPending}
            disabled={!canWrite || investigation.incidents.length === 0} onClick={() => generate.mutate()} />
          {!canWrite && <span className={Classes.TEXT_MUTED}>Read-only viewer</span>}
          <span className={Classes.TEXT_MUTED}>Deterministic. Built only from member reports, pattern analysis, and notes.</span>
        </div>
        {summaries.isPending && <Spinner />}
        {summaries.isError && <Callout intent="danger">{summaries.error.message}</Callout>}
        {summaries.data && !snapshot && (
          <NonIdealState icon="manual" title="No summary yet" description="Generate one to get an evidence-linked brief of this investigation." />
        )}
        {snapshot && (
          <article className="summary">
            <Callout intent="warning" icon="automatic-updates" className="summary-label">
              <strong>{snapshot.label}</strong>
              <div className="summary-meta">
                <Provenance tier="inferred" method={snapshot.method} />
                <span>Generated {fmtTime(snapshot.generated_at)} by {snapshot.generated_by.display_name}</span>
                <span>· {snapshot.member_report_nos.length} member reports at generation</span>
              </div>
            </Callout>
            {stale && (
              <Callout intent="primary" icon="refresh" compact>
                Membership changed since this snapshot. Generate again to include the current {members.length} reports.
              </Callout>
            )}
            {snapshot.sections.filter((section) => section.claims.length > 0).map((section) => (
              <section key={section.heading} className="summary-section">
                <h3>{section.heading}</h3>
                <ul>
                  {section.claims.map((claim, i) => (
                    <li key={i} className="claim">
                      <span className="claim-text">{claim.text}</span>
                      <span className="citations">
                        {claim.citations.map((c) => <ReportLink key={c} reportNo={c} />)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </article>
        )}
      </div>
      <aside className="summary-history">
        <h4>Snapshots</h4>
        {list.length === 0 ? <p className={Classes.TEXT_MUTED}>None.</p> : (
          <Menu>
            {list.map((s, i) => (
              <MenuItem key={s.id} active={s.id === snapshot?.id} onClick={() => setChosen(s.id)}
                text={fmtTime(s.generated_at)} icon="history"
                label={`${s.member_report_nos.length} reports${i === 0 ? " · latest" : ""}`} />
            ))}
          </Menu>
        )}
      </aside>
    </div>
  );
}
