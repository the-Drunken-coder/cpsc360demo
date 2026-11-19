import { Button, Callout, HTMLTable, Tag } from "@blueprintjs/core";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { LabCase, LabEvaluation, LabMetrics, LabRules, LabRun, LabTriageMatch } from "../../api/heuristicLab";
import { StartingReports } from "./StartingReports";

function MetricsTable({ leftName, rightName, left, right }: {
  leftName: string;
  rightName: string;
  left: LabMetrics | null;
  right: LabMetrics | null;
}) {
  function delay(days: number | null) {
    return days === null ? "—" : `${days} d`;
  }
  const rows = [
    { label: "Cases caught", left: left?.caught ?? "—", right: right?.caught ?? "—" },
    { label: "Cases missed", left: left?.missed ?? "—", right: right?.missed ?? "—" },
    { label: "Background cases flagged", left: left?.extra ?? "—", right: right?.extra ?? "—" },
    { label: "Total alerts", left: left?.alerts ?? "—", right: right?.alerts ?? "—" },
    { label: "Median delay on caught cases", left: delay(left?.median_delay_days ?? null), right: delay(right?.median_delay_days ?? null) },
  ];
  return <HTMLTable compact striped className="full-width lab-metrics">
    <thead><tr><th scope="col">Measure</th><th scope="col">{leftName}</th><th scope="col">{rightName}</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td>{row.left}</td><td>{row.right}</td></tr>)}</tbody>
  </HTMLTable>;
}

function RulesSummary({ rules }: { rules: LabRules }) {
  if (rules.use_signals === false) return <span>{rules.triage?.length ?? 0} triage rules</span>;
  return <span>“{rules.phrase}” · {rules.severity === "injury" ? "Injury reported" : "Any severity"} · {rules.minimum_count} in {rules.window_days} days</span>;
}

function Outcome({ item }: { item: LabCase }) {
  if (item.first_alert_delay === null) {
    return item.expected_alert ? <Tag minimal intent="danger">Missed</Tag> : <Tag minimal>Quiet</Tag>;
  }
  return item.expected_alert
    ? <Tag minimal intent="success">Caught · {item.first_alert_delay} d</Tag>
    : <Tag minimal intent="warning">Extra alert</Tag>;
}

function TriageMatches({ matches }: { matches: LabTriageMatch[] | undefined }) {
  if (!matches?.length) return null;
  return <ul className="lab-triage-matches">{matches.map((match, index) => <li key={index}>
    <strong>{match.action.kind} · {match.action.value}</strong>
    {!match.applied && " (overridden)"}
    <div className="lab-subtle">{match.rule} · {match.evidence.join(" · ")}</div>
  </li>)}</ul>;
}

function CaseEvidence({ baseline, candidate, baselineSignals, candidateSignals }: {
  baseline: LabCase; candidate: LabCase; baselineSignals: boolean; candidateSignals: boolean;
}) {
  return <details className="lab-case">
    <summary>
      <span><code>{baseline.id}</code> · {baseline.title}</span>
      {baselineSignals && <span><small>Baseline </small><Outcome item={baseline} /></span>}
      {candidateSignals && <span><small>Candidate </small><Outcome item={candidate} /></span>}
    </summary>
    <div className="lab-evidence">
      <p className="lab-subtle">Scenario label · {baseline.expected_alert ? "Expected to alert" : "Background activity"}</p>
      {baseline.decisions.map(({ report, reasons, triage }) => {
        const other = candidate.decisions.find((decision) => decision.report.id === report.id);
        return <article key={report.id}>
          <header><code>{report.id}</code> · {report.available_on} · {report.product} · {report.hazard}</header>
          <p>{report.narrative}</p>
          {report.facts && Object.keys(report.facts).length > 0 && <p className="lab-subtle">
            {Object.entries(report.facts).map(([field, value]) => `${field.replaceAll("_", " ")}: ${typeof value === "boolean" ? value ? "yes" : "no" : value}`).join(" · ")}
          </p>}
          <dl>
            <dt>Baseline</dt><dd>{reasons.join(" ") || (triage?.length ? "" : "No rule fired.")}<TriageMatches matches={triage} /></dd>
            <dt>Candidate</dt><dd>{other?.reasons.join(" ") || (other?.triage?.length ? "" : "No rule fired.")}<TriageMatches matches={other?.triage} /></dd>
          </dl>
        </article>;
      })}
    </div>
  </details>;
}

function appliedActions(matches: LabTriageMatch[] | undefined) {
  return [...new Set(matches?.filter((match) => match.applied && match.action.kind !== "suppress")
    .map((match) => `${match.action.kind} · ${match.action.value}`))].sort();
}

export function RunResults({ run, canWrite, onRerun }: {
  run: LabRun;
  canWrite: boolean;
  onRerun: (rules: LabRules) => void;
}) {
  const { baseline, candidate } = run.result;
  const baselineSignals = baseline.rules.use_signals !== false;
  const candidateSignals = candidate.rules.use_signals !== false;
  const [filter, setFilter] = useState("all");
  const candidateCases = new Map(candidate.cases.map((item) => [item.id, item]));
  const comparedCases = baseline.cases.flatMap((item) => {
    const other = candidateCases.get(item.id);
    if (!other) return [];
    const left = item.first_alert_delay !== null;
    const right = other.first_alert_delay !== null;
    const group = item.expected_alert
      ? left && right ? "both" : left ? "baseline" : right ? "candidate" : "missed"
      : left || right ? "extra" : "quiet";
    const triageDiffers = item.decisions.some((decision, position) =>
      JSON.stringify(appliedActions(decision.triage)) !== JSON.stringify(appliedActions(other.decisions[position]?.triage)));
    return [{ item, other, group, triageDiffers }];
  });
  const visibleCases = comparedCases.filter(({ group, triageDiffers }) => filter === "all" || group === filter || (filter === "triage" && triageDiffers));
  const advice = useMutation({ mutationFn: () => api.labAdvice(run.id) });

  const proposal = advice.data?.proposal;
  const tallies = (evaluation: LabEvaluation) => {
    const counts = new Map<string, number>();
    const decisions = [...evaluation.cases.flatMap((item) => item.decisions), ...evaluation.end_checks ?? []];
    for (const decision of decisions) {
      const actions = appliedActions(decision.triage);
      for (const action of actions) counts.set(action, (counts.get(action) ?? 0) + 1);
    }
    return counts;
  };
  const leftActions = tallies(baseline);
  const rightActions = tallies(candidate);
  const actions = [...new Set([...leftActions.keys(), ...rightActions.keys()])].sort();

  return <>
    <section className="panel lab-config">
      <div className="lab-result-heading">
        <div><h2>Run {run.id}</h2><p className="lab-subtle">{run.start} → {run.end} · {run.result.evaluator}</p></div>
        {canWrite && <Button icon="duplicate" onClick={() => onRerun(candidate.rules)}>Use these rules in a new run</Button>}
      </div>
      <div className="lab-rule-summary">
        <div><strong>Baseline</strong><RulesSummary rules={baseline.rules} /></div>
        <div><strong>Candidate</strong><RulesSummary rules={candidate.rules} /></div>
      </div>
      {actions.length > 0 && <HTMLTable compact striped className="full-width lab-metrics">
        <thead><tr><th scope="col">Triage action</th><th scope="col">Baseline matches</th><th scope="col">Candidate matches</th></tr></thead>
        <tbody>{actions.map((action) => <tr key={action}><th scope="row">{action}</th>
          <td>{leftActions.get(action) ?? 0}</td><td>{rightActions.get(action) ?? 0}</td></tr>)}</tbody>
      </HTMLTable>}
      {(baselineSignals || candidateSignals) && <MetricsTable leftName="Baseline" rightName="Candidate" left={baselineSignals ? baseline.metrics : null} right={candidateSignals ? candidate.metrics : null} />}
      {(baselineSignals || candidateSignals) && <p className="lab-subtle">Detection metrics count basic signals. Triage actions are compared separately. Total alerts include repeat flags. Delay starts at the first report for a case during the replay.</p>}
      <StartingReports reports={run.result.starting_reports} />
    </section>

    <section className="panel lab-config">
      <div className="lab-result-heading">
        <h2>Case evidence</h2>
        <label className="lab-date">Show
          <select className="bp5-input" value={filter} onChange={(event) => setFilter(event.currentTarget.value)}>
            <option value="all">All cases</option>
            <option value="triage">Different triage actions</option>
            {(baselineSignals || candidateSignals) && <>
            <option value="both">Caught by both</option>
            <option value="baseline">Caught only by baseline</option>
            <option value="candidate">Caught only by candidate</option>
            <option value="missed">Missed by both</option>
            <option value="extra">Background cases flagged</option>
            <option value="quiet">Quiet background cases</option>
            </>}
          </select>
        </label>
      </div>
      {visibleCases.length === 0 && <p>No cases match this view.</p>}
      {visibleCases.map(({ item, other }) => <CaseEvidence key={item.id} baseline={item} candidate={other}
        baselineSignals={baselineSignals} candidateSignals={candidateSignals} />)}
    </section>

    {[baseline, candidate].some((evaluation) => evaluation.end_checks?.length) && <section className="panel lab-config">
      <h2>End-of-replay checks</h2>
      {[{ name: "Baseline", evaluation: baseline }, { name: "Candidate", evaluation: candidate }].map(({ name, evaluation }) => (
        <div key={name}><h3>{name}</h3>
          {evaluation.end_checks?.length ? evaluation.end_checks.map((decision) => <article key={decision.report.id}>
            <strong>{decision.report.id} · {decision.report.product}</strong>
            <TriageMatches matches={decision.triage} />
          </article>) : <p>No checks matched.</p>}
        </div>
      ))}
    </section>}

    {canWrite && candidate.rules.use_signals !== false && <section className="panel lab-config">
      <div className="lab-result-heading">
        <div><h2>AI suggestion</h2><p className="lab-subtle">Propose one candidate rule change and measure it on a separate synthetic scenario.</p></div>
        <Button icon="predictive-analysis" loading={advice.isPending} onClick={() => advice.mutate()}>Get suggestion</Button>
      </div>
      {advice.isError && <Callout intent="warning">{advice.error.message} <Link to="/settings">Open Settings</Link></Callout>}
      {advice.data && proposal && <>
        <p>{proposal.reasoning}</p>
        <p className="lab-subtle">{advice.data.model} · Cases cited {proposal.case_ids.join(", ")}</p>
        <div><RulesSummary rules={proposal.rules} /></div>
        <MetricsTable leftName="Current candidate" rightName="Proposed" left={advice.data.current} right={advice.data.proposed} />
        <div><Button onClick={() => onRerun(proposal.rules)}>Try proposal in a new run</Button></div>
      </>}
    </section>}
  </>;
}
