import { Button, Classes, NonIdealState, TextArea } from "@blueprintjs/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/client";
import type { Investigation } from "../../api/types";
import { Provenance } from "../../components/Provenance";
import { Linkified, ReportLink, fmtTime } from "../../components/text";
import { toastError } from "../../components/toaster";
import { useSession } from "../../session/SessionProvider";

export function NotesPanel({ investigation }: { investigation: Investigation }) {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const add = useMutation({
    mutationFn: () => api.addNote(investigation.id, body.trim()),
    onSuccess: () => {
      setBody("");
      void queryClient.invalidateQueries({ queryKey: qk.investigation(investigation.id) });
      void queryClient.invalidateQueries({ queryKey: qk.audit(investigation.id) });
    },
    onError: toastError,
  });
  const notes = [...investigation.notes].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <div className="notes">
      {canWrite && (
        <div className="note-composer">
          <TextArea fill value={body} placeholder="Note. Report numbers such as 20240101-ABCDE-1 become links."
            onChange={(e) => setBody(e.currentTarget.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && body.trim()) add.mutate(); }} />
          <div className="note-composer-actions">
            <span className={Classes.TEXT_MUTED}>Ctrl+Enter to post</span>
            <Button small intent="primary" text="Add note" disabled={!body.trim()} loading={add.isPending} onClick={() => add.mutate()} />
          </div>
        </div>
      )}
      {notes.length === 0 && <NonIdealState icon="annotation" title="No notes yet" />}
      {notes.map((n) => (
        <article key={n.id} className="note">
          <header className="note-head">
            <Provenance tier="analyst" by={n.author.display_name} />
            <strong>{n.author.display_name}</strong>
            <span className={Classes.TEXT_MUTED}>{fmtTime(n.created_at)}</span>
          </header>
          <div className="note-body"><Linkified body={n.body} /></div>
          {n.cited_report_nos.length > 0 && (
            <div className="note-cites">
              <span className={Classes.TEXT_MUTED}>Cites</span>
              {n.cited_report_nos.map((r) => <ReportLink key={r} reportNo={r} />)}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
