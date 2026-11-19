import { Button, Callout, Spinner, Tag } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { LabRules, LabRunInput } from "../../api/heuristicLab";
import { useSession } from "../../session/SessionProvider";
import { RunResults } from "./RunResults";
import { StartingReports } from "./StartingReports";
import { TriageEditor } from "./TriageEditor";
import "./heuristicLab.css";

const LAB_PATH = "/heuristic-lab";
const INITIAL_DATE = "2025-01-15";

function RuleEditor({ name, rules, onChange, disabled }: {
  name: string;
  rules: LabRules;
  onChange: (rules: LabRules) => void;
  disabled: boolean;
}) {
  return <fieldset className="lab-rule-editor" disabled={disabled}>
    <legend>{name}</legend>
    <label className="lab-signal-toggle"><input type="checkbox" checked={rules.use_signals ?? true}
      onChange={(event) => onChange({ ...rules, use_signals: event.currentTarget.checked })} /> Include basic detection signals</label>
    {(rules.use_signals ?? true) && <>
    <label>Phrase
      <input className="bp5-input" required maxLength={80} pattern=".*\S.*" value={rules.phrase}
        onChange={(event) => onChange({ ...rules, phrase: event.currentTarget.value })} />
    </label>
    <label>Phrase severity
      <select className="bp5-input" value={rules.severity}
        onChange={(event) => onChange({ ...rules, severity: event.currentTarget.value === "injury" ? "injury" : "any" })}>
        <option value="any">Any report</option>
        <option value="injury">Injury reported</option>
      </select>
    </label>
    <label>Rolling window (days)
      <input className="bp5-input" type="number" required min={1} max={90}
        value={Number.isNaN(rules.window_days) ? "" : rules.window_days}
        onChange={(event) => onChange({ ...rules, window_days: event.currentTarget.valueAsNumber })} />
    </label>
    <label>Minimum reports in window
      <input className="bp5-input" type="number" required min={2} max={20}
        value={Number.isNaN(rules.minimum_count) ? "" : rules.minimum_count}
        onChange={(event) => onChange({ ...rules, minimum_count: event.currentTarget.valueAsNumber })} />
    </label>
    </>}
    <TriageEditor rules={rules.triage ?? []} onChange={(triage) => onChange({ ...rules, triage })} />
  </fieldset>;
}

export function HeuristicLabView() {
  const { user, canWrite } = useSession();
  return <LabWorkspace key={user.id} actorId={user.id} canWrite={canWrite} />;
}

function LabWorkspace({ actorId, canWrite }: { actorId: number; canWrite: boolean }) {
  const { runId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [start, setStart] = useState(INITIAL_DATE);
  const [drafts, setDrafts] = useState<Pick<LabRunInput, "baseline" | "candidate"> | null>(null);
  const scenario = useQuery({
    queryKey: ["heuristic-lab", "scenario", start],
    queryFn: () => api.labScenario(start),
    enabled: Boolean(start),
  });
  const historyKey = ["heuristic-lab", actorId, "runs"];
  const history = useQuery({ queryKey: historyKey, queryFn: api.labRuns });
  const run = useQuery({
    queryKey: [...historyKey, runId],
    queryFn: () => api.labRun(runId ?? ""),
    enabled: Boolean(runId),
  });
  const createRun = useMutation({
    mutationFn: api.runLab,
    onSuccess: (saved) => {
      queryClient.setQueryData([...historyKey, String(saved.id)], saved);
      void queryClient.invalidateQueries({ queryKey: historyKey, exact: true });
      navigate(`${LAB_PATH}/${saved.id}`);
    },
  });
  const baseline = drafts?.baseline ?? scenario.data?.baseline;
  const candidate = drafts?.candidate ?? scenario.data?.candidate;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (baseline && candidate && scenario.data && canWrite && !createRun.isPending) {
      const clean = (rules: LabRules, defaults: LabRules): LabRules => ({
        ...(rules.use_signals === false ? { ...rules, phrase: defaults.phrase, severity: defaults.severity,
          window_days: defaults.window_days, minimum_count: defaults.minimum_count } : rules),
        triage: rules.triage?.map((rule) => ({
          ...rule,
          conditions: rule.conditions.map((condition) =>
            condition.kind === "number" && condition.operator === "unknown" ? { ...condition, value: 0 } : condition),
        })),
      });
      createRun.mutate({ start, baseline: clean(baseline, scenario.data.baseline),
        candidate: clean(candidate, scenario.data.candidate) });
    }
  }

  function onRerun(next: LabRules) {
    if (!run.data) return;
    setStart(run.data.start);
    setDrafts({ baseline: run.data.result.baseline.rules, candidate: next });
    navigate(LAB_PATH);
  }

  return <div className="page heuristic-lab">
    <header className="lab-header">
      <div>
        <h1>Heuristic Lab</h1>
        <p>Replay three months of product reports and compare what two rule sets catch.</p>
      </div>
      <Tag minimal intent="primary">Synthetic scenario</Tag>
    </header>

    <div className="lab-layout">
      <aside className="panel lab-history">
        <h2>Runs</h2>
        <Link className={runId ? undefined : "lab-active-link"} to={LAB_PATH}>New run</Link>
        {history.isPending && <Spinner size={18} />}
        {history.isError && <Callout intent="danger">{history.error.message}</Callout>}
        {history.data?.map((item) => <Link key={item.id} to={`${LAB_PATH}/${item.id}`}
          aria-current={runId === String(item.id) ? "page" : undefined}>
          <strong>Run {item.id}</strong>
          <small>{item.start} → {item.end}</small>
        </Link>)}
      </aside>

      <div className="lab-content">
        {runId ? <>
          {run.isPending && <Spinner size={26} />}
          {run.isError && <Callout intent="danger">{run.error.message}</Callout>}
          {run.data && <RunResults key={run.data.id} run={run.data} canWrite={canWrite} onRerun={onRerun} />}
        </> : <form className="panel lab-config" onSubmit={submit}>
          <h2>Set up a run</h2>
          <div className="lab-date">
            <label htmlFor="lab-start">Analyst’s starting date</label>
            <input id="lab-start" className="bp5-input" type="date" required
              min={scenario.data?.first_start} max={scenario.data?.last_start}
              value={start} onChange={(event) => setStart(event.currentTarget.value)} />
          </div>
          {scenario.isPending && start && <Spinner size={20} />}
          {scenario.isError && <Callout intent="danger">{scenario.error.message}</Callout>}
          {scenario.data && <StartingReports reports={scenario.data.reports} />}
          {baseline && candidate && <>
            <p className="lab-subtle">Add triage rules to simulate actions such as routing, escalation, and dispositions. Reports available at the start feed rolling patterns.</p>
            <div className="lab-rule-grid">
              <RuleEditor name="Baseline" rules={baseline} onChange={(next) => setDrafts({ baseline: next, candidate })} disabled={!canWrite} />
              <RuleEditor name="Candidate" rules={candidate} onChange={(next) => setDrafts({ baseline, candidate: next })} disabled={!canWrite} />
            </div>
          </>}
          {createRun.isError && <Callout intent="danger">{createRun.error.message}</Callout>}
          {canWrite ? <div><Button type="submit" intent="primary" icon="fast-forward" loading={createRun.isPending}
            disabled={!scenario.data || !baseline || !candidate}>Advance three months</Button></div>
            : <p className="lab-subtle">Switch to an analyst or lead to create a run.</p>}
        </form>}
      </div>
    </div>
  </div>;
}
