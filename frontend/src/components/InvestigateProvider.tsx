import {
  Button, Classes, Dialog, DialogBody, DialogFooter, FormGroup, HTMLSelect, InputGroup, Radio, RadioGroup, TagInput,
  TextArea,
} from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, qk } from "../api/client";
import type { Investigation } from "../api/types";
import { useSession } from "../session/SessionProvider";
import { toast, toastError } from "./toaster";

interface InvestigateValue { open: (reportNos: string[]) => void }
const InvestigateContext = createContext<InvestigateValue | null>(null);

export function useInvestigate(): InvestigateValue {
  const value = useContext(InvestigateContext);
  if (!value) throw new Error("useInvestigate outside InvestigateProvider");
  return value;
}

export function InvestigateProvider({ children }: { children: ReactNode }) {
  const [reportNos, setReportNos] = useState<string[] | null>(null);
  const { canWrite } = useSession();
  const open = useCallback((nos: string[]) => {
    if (!canWrite) {
      toast({ intent: "warning", icon: "lock", message: "Read-only viewer. Switch user to create investigations." });
      return;
    }
    if (nos.length === 0) {
      toast({ icon: "info-sign", message: "Select one or more reports first." });
      return;
    }
    setReportNos(nos);
  }, [canWrite]);
  const value = useMemo(() => ({ open }), [open]);
  return (
    <InvestigateContext.Provider value={value}>
      {children}
      {reportNos && <InvestigateDialog reportNos={reportNos} onClose={() => setReportNos(null)} />}
    </InvestigateContext.Provider>
  );
}

function InvestigateDialog({ reportNos, onClose }: { reportNos: string[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { users, user } = useSession();
  const investigations = useQuery({ queryKey: qk.investigations(), queryFn: () => api.investigations() });
  const candidates = (investigations.data ?? []).filter((i) => i.status !== "closed");
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const effectiveMode = candidates.length === 0 ? "new" : mode;
  const [targetId, setTargetId] = useState<number | null>(null);
  const target = targetId ?? candidates[0]?.id ?? null;
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [labels, setLabels] = useState<string[]>([]);
  const [assigneeId, setAssigneeId] = useState<number>(user.id);
  const [rationale, setRationale] = useState("");

  const mutation = useMutation({
    mutationFn: (): Promise<Investigation> => {
      if (effectiveMode === "new") {
        return api.createInvestigation({
          title: title.trim(), description, labels, assignee_id: assigneeId, report_nos: reportNos,
          rationale: rationale || undefined,
        });
      }
      if (target === null) throw new Error("Choose an investigation.");
      return api.addMembers(target, reportNos, rationale || undefined);
    },
    onSuccess: (inv) => {
      void queryClient.invalidateQueries({ queryKey: ["investigations"] });
      void queryClient.invalidateQueries({ queryKey: ["investigation", inv.id] });
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
      void queryClient.invalidateQueries({ queryKey: ["incident"] });
      void queryClient.invalidateQueries({ queryKey: ["audit", inv.id] });
      toast({
        intent: "success",
        icon: "folder-shared",
        message: `${reportNos.length} report${reportNos.length === 1 ? "" : "s"} in “${inv.title}”.`,
        action: { text: "Open", onClick: () => navigate(`/investigations/${inv.id}`) },
      });
      onClose();
    },
    onError: toastError,
  });

  const canSubmit = effectiveMode === "new" ? title.trim().length > 0 : target !== null;

  return (
    <Dialog isOpen onClose={onClose} title={`Add ${reportNos.length} report${reportNos.length === 1 ? "" : "s"} to an investigation`}
      icon="folder-new" className="investigate-dialog">
      <DialogBody>
        <RadioGroup inline selectedValue={effectiveMode} onChange={(e) => setMode(e.currentTarget.value as "existing" | "new")}>
          <Radio value="existing" label="Existing investigation" disabled={candidates.length === 0} />
          <Radio value="new" label="New investigation" />
        </RadioGroup>
        {effectiveMode === "existing" ? (
          <FormGroup label="Investigation" labelFor="inv-target">
            <HTMLSelect id="inv-target" fill value={target ?? ""} onChange={(e) => setTargetId(Number(e.currentTarget.value))}>
              {candidates.map((i) => (
                <option key={i.id} value={i.id}>#{i.id} {i.title} ({i.incident_count} reports, {i.status.replace("_", " ")})</option>
              ))}
            </HTMLSelect>
          </FormGroup>
        ) : (
          <>
            <FormGroup label="Title" labelFor="inv-title" labelInfo="(required)">
              <InputGroup id="inv-title" autoFocus value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
            </FormGroup>
            <FormGroup label="Description" labelFor="inv-desc">
              <TextArea id="inv-desc" fill value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
            </FormGroup>
            <FormGroup label="Labels" helperText="Press Enter after each label.">
              <TagInput values={labels} onChange={(v) => setLabels(v.map(String))} addOnBlur leftIcon="tag" />
            </FormGroup>
            <FormGroup label="Assignee" labelFor="inv-assignee">
              <HTMLSelect id="inv-assignee" value={assigneeId} onChange={(e) => setAssigneeId(Number(e.currentTarget.value))}>
                {users.filter((u) => u.role !== "viewer").map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
              </HTMLSelect>
            </FormGroup>
          </>
        )}
        <FormGroup label="Rationale" labelFor="inv-rationale" labelInfo="(why these reports belong)">
          <TextArea id="inv-rationale" fill value={rationale} onChange={(e) => setRationale(e.currentTarget.value)} />
        </FormGroup>
        <p className={Classes.TEXT_MUTED}>Reports: <span className="mono">{reportNos.join(", ")}</span></p>
      </DialogBody>
      <DialogFooter actions={<>
        <Button text="Cancel" onClick={onClose} />
        <Button intent="primary" text={effectiveMode === "new" ? "Create investigation" : "Add reports"}
          disabled={!canSubmit} loading={mutation.isPending} onClick={() => mutation.mutate()} />
      </>} />
    </Dialog>
  );
}
