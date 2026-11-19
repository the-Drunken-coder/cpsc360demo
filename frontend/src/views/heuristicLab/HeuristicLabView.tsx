import { Button, Callout, Classes, Popover, Spinner, Tab, Tabs } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { flushSync } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { LabCaseAction, LabRules, LabTriageAction, LabTriageRule } from "../../api/heuristicLab";
import { useSession } from "../../session/SessionProvider";
import { LabHelp } from "./LabHelp";
import { RunResults } from "./RunResults";
import { StartingReports } from "./StartingReports";
import { TriageEditor } from "./TriageEditor";
import "./heuristicLab.css";

const LAB_PATH = "/heuristic-lab";
const INITIAL_DATE = "2025-01-15";
const SETS = [
  { id: "baseline", title: "Baseline", role: "Reference" },
  { id: "candidate", title: "Candidate", role: "Under test" },
] as const;
const SHORT_DATE = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
type RuleSet = typeof SETS[number]["id"];
type RuleSetDraft = LabRules<LabTriageAction | null>;
type RuleSetDrafts = Record<RuleSet, RuleSetDraft>;

function replayEnd(start: string) {
  const end = new Date(`${start}T00:00:00Z`);
  const day = end.getUTCDate();
  end.setUTCMonth(end.getUTCMonth() + 3, 1);
  const lastDay = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() + 1, 0)).getUTCDate();
  end.setUTCDate(Math.min(day, lastDay));
  return SHORT_DATE.format(end);
}

function scenarioQuery(start: string) {
  return { queryKey: ["heuristic-lab", "scenario", start], queryFn: () => api.labScenario(start) };
}

function prepareRules(rules: RuleSetDraft): LabRules<LabCaseAction> | undefined {
  const triage: LabTriageRule<LabCaseAction>[] = [];
  for (const rule of rules.triage ?? []) {
    if (!rule.action || "value" in rule.action) return undefined;
    triage.push({
      ...rule,
      action: rule.action,
      conditions: rule.conditions.map((condition) =>
        condition.kind === "number" && condition.operator === "unknown" ? { ...condition, value: 0 } : condition),
    });
  }
  return { triage };
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
  const [drafts, setDrafts] = useState<RuleSetDrafts | null>(null);
  const [activeSet, setActiveSet] = useState<RuleSet>("candidate");
  const [formVersion, setFormVersion] = useState(0);
  const defaults = useQuery({ ...scenarioQuery(INITIAL_DATE), enabled: !runId });
  const validStart = Boolean(defaults.data && start >= defaults.data.first_start && start <= defaults.data.last_start);
  const preview = useQuery({ ...scenarioQuery(start), enabled: !runId && validStart });
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
  const ruleSets = drafts ?? defaults.data;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWrite || createRun.isPending) return;

    const invalid = event.currentTarget.querySelector<HTMLInputElement | HTMLSelectElement>("input:invalid, select:invalid");
    if (invalid) {
      const owner = invalid.closest<HTMLElement>("[data-rule-set]")?.dataset.ruleSet;
      if (owner === "baseline" || owner === "candidate") {
        flushSync(() => setActiveSet(owner));
        const detail = invalid.closest("details");
        if (detail) detail.open = true;
      }
      invalid.reportValidity();
      return;
    }

    if (ruleSets && defaults.data && validStart && preview.data) {
      const baseline = prepareRules(ruleSets.baseline);
      const candidate = prepareRules(ruleSets.candidate);
      if (baseline && candidate) createRun.mutate({ start, baseline, candidate });
    }
  }

  function setUp(nextStart: string, nextDrafts: RuleSetDrafts | null) {
    setStart(nextStart);
    setDrafts(nextDrafts);
    setActiveSet("candidate");
    setFormVersion((version) => version + 1);
    createRun.reset();
  }

  function onRerun(next: LabRules) {
    if (!run.data) return;
    setUp(run.data.start, { baseline: run.data.result.baseline.rules, candidate: next });
    navigate(LAB_PATH);
  }

  return <div className="page heuristic-lab">
    <header className="lab-header">
      <div>
        <h1>Heuristic Lab</h1>
        <p>Replay the same three months of synthetic reports with two rule sets.</p>
      </div>
      <Popover placement="bottom-end" minimal content={
        <nav className="lab-history" aria-label="Saved runs">
          <h2>Saved runs</h2>
          <Link className={Classes.POPOVER_DISMISS} to={LAB_PATH} onClick={() => setUp(INITIAL_DATE, null)}>New run</Link>
          {history.isPending && <Spinner size={18} />}
          {history.isError && <Callout intent="danger">{history.error.message}</Callout>}
          {history.data?.length === 0 && <p>No saved runs yet.</p>}
          {history.data?.map((item) => <Link key={item.id} className={Classes.POPOVER_DISMISS} to={`${LAB_PATH}/${item.id}`}
            aria-current={runId === String(item.id) ? "page" : undefined}>
            <strong>Run {item.id}</strong>
            <small>{item.start} → {item.end}</small>
          </Link>)}
        </nav>
      }>
        <Button type="button" icon="history" text="Run history" />
      </Popover>
    </header>

    <div className="lab-content">
      {runId ? <>
        {run.isPending && <Spinner size={26} />}
        {run.isError && <Callout intent="danger">{run.error.message}</Callout>}
        {run.data && <RunResults key={run.data.id} run={run.data} canWrite={canWrite} onRerun={onRerun} />}
      </> : <form className="panel lab-config" key={formVersion} noValidate onSubmit={submit}>
        <div className="lab-replay-settings">
          <div className="lab-date">
            <div className="lab-field-label">
              <label htmlFor="lab-start">Replay starts</label>
              <LabHelp label="Replay dates" text="Each comparison runs for three calendar months. Reports available on the start date can contribute to patterns, and reports that arrive later are evaluated during the replay." />
            </div>
            <input id="lab-start" className="bp5-input" type="date" required
              min={defaults.data?.first_start} max={defaults.data?.last_start}
              value={start} onChange={(event) => setStart(event.currentTarget.value)} />
            {validStart && <span className="lab-subtle">Ends {replayEnd(start)}</span>}
          </div>
          <div className="lab-preview">
            {defaults.data && !validStart && <p role="status">Choose a date from {defaults.data.first_start} to {defaults.data.last_start}.</p>}
            {validStart && preview.isPending && <p role="status">Loading starting reports…</p>}
            {preview.data && validStart && <StartingReports reports={preview.data.reports} />}
          </div>
        </div>
        {(defaults.isError || (validStart && preview.isError)) && <Callout intent="danger">
          {defaults.error?.message ?? preview.error?.message}
        </Callout>}
        {defaults.isPending && <Spinner size={20} />}
        {ruleSets && <Tabs id="lab-rule-sets" className="lab-rule-tabs" animate={false} selectedTabId={activeSet}
          onChange={(id) => { if (id === "baseline" || id === "candidate") setActiveSet(id); }}>
          {SETS.map(({ id, title, role }) => <Tab key={id} id={id} title={<>{title} <span className="lab-tab-role">· {role}</span></>}
            panel={<div className="lab-rule-editor" data-rule-set={id} data-readonly={!canWrite || undefined}>
              <TriageEditor rules={ruleSets[id].triage ?? []} disabled={!canWrite}
                onChange={(triage) => setDrafts({ baseline: ruleSets.baseline, candidate: ruleSets.candidate, [id]: { triage } })} />
            </div>} />)}
        </Tabs>}
        {createRun.isError && <Callout intent="danger">{createRun.error.message}</Callout>}
        {canWrite ? <div className="lab-form-actions">
          <Button type="submit" intent="primary" icon="fast-forward" text="Run comparison" loading={createRun.isPending}
            disabled={!validStart || !preview.data || !ruleSets} />
        </div> : <p className="lab-subtle">Switch to an analyst or lead to create a run.</p>}
      </form>}
    </div>
  </div>;
}
