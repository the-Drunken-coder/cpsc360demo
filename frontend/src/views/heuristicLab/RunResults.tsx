import { Button, HTMLTable } from "@blueprintjs/core";
import { useState } from "react";
import type { LabDecision, LabEvaluation, LabReport, LabRules, LabRun, LabTriageMatch } from "../../api/heuristicLab";
import { LabHelp } from "./LabHelp";
import { StartingReports } from "./StartingReports";
import { recommendationText } from "./TriageEditor";

function RulesSummary({ rules }: { rules: LabRules }) {
  const count = rules.triage?.length ?? 0;
  return <span>{count} triage {count === 1 ? "rule" : "rules"}</span>;
}

function TriageMatches({ matches }: { matches: LabTriageMatch[] | undefined }) {
  if (!matches?.length) return <>No rule matched.</>;
  return <ul className="lab-triage-matches">{matches.map((match, index) => <li key={index}>
    <strong>{match.rule}</strong> → {recommendationText(match.action)}
    {!match.applied && " (overridden)"}
    <div className="lab-subtle">{match.evidence.join(" · ")}</div>
  </li>)}</ul>;
}

function appliedActions(matches: LabTriageMatch[] | undefined) {
  return [...new Set(matches?.filter((match) => match.applied && match.action.kind !== "suppress")
    .map((match) => recommendationText(match.action)))].sort();
}

interface ComparedReport {
  report: LabReport;
  baseline?: LabTriageMatch[];
  candidate?: LabTriageMatch[];
}

function compareReports(baseline: LabDecision[], candidate: LabDecision[]) {
  const reports = new Map<string, ComparedReport>(baseline.map(({ report, triage }) =>
    [report.id, { report, baseline: triage }]));
  for (const { report, triage } of candidate) {
    reports.set(report.id, { report, baseline: reports.get(report.id)?.baseline, candidate: triage });
  }
  return [...reports.values()].sort((left, right) =>
    left.report.available_on.localeCompare(right.report.available_on) || left.report.id.localeCompare(right.report.id));
}

function actionsDiffer({ baseline, candidate }: ComparedReport) {
  return JSON.stringify(appliedActions(baseline)) !== JSON.stringify(appliedActions(candidate));
}

function ReportEvidence({ report, baseline, candidate }: ComparedReport) {
  return <article>
    <header><code>{report.id}</code> · {report.available_on} · {report.product} · {report.hazard}</header>
    <p>{report.narrative}</p>
    {report.facts && Object.keys(report.facts).length > 0 && <p className="lab-subtle">
      {Object.entries(report.facts).map(([field, value]) => `${field.replaceAll("_", " ")}: ${typeof value === "boolean" ? value ? "yes" : "no" : value}`).join(" · ")}
    </p>}
    <dl>
      <dt>Baseline</dt><dd><TriageMatches matches={baseline} /></dd>
      <dt>Candidate</dt><dd><TriageMatches matches={candidate} /></dd>
    </dl>
  </article>;
}

function tallies(evaluation: LabEvaluation) {
  const counts = new Map<string, number>();
  const decisions = [...evaluation.cases.flatMap((item) => item.decisions), ...evaluation.end_checks ?? []];
  for (const decision of decisions) {
    for (const action of appliedActions(decision.triage)) counts.set(action, (counts.get(action) ?? 0) + 1);
  }
  return counts;
}

export function RunResults({ run, canWrite, onRerun }: {
  run: LabRun;
  canWrite: boolean;
  onRerun: (rules: LabRules) => void;
}) {
  const { baseline, candidate } = run.result;
  const [onlyDifferences, setOnlyDifferences] = useState(false);
  const candidateCases = new Map(candidate.cases.map((item) => [item.id, item]));
  const visibleCases = baseline.cases.flatMap(({ id, title, decisions }) => {
    const reports = compareReports(decisions, candidateCases.get(id)?.decisions ?? []);
    const visibleReports = onlyDifferences ? reports.filter(actionsDiffer) : reports;
    return visibleReports.length > 0 ? [{ id, title, reports: visibleReports }] : [];
  });
  const endReports = compareReports(baseline.end_checks ?? [], candidate.end_checks ?? []);
  const visibleEndReports = onlyDifferences ? endReports.filter(actionsDiffer) : endReports;

  const leftActions = tallies(baseline);
  const rightActions = tallies(candidate);
  const actions = [...new Set([...leftActions.keys(), ...rightActions.keys()])].sort();

  return <>
    <section className="panel lab-config">
      <div className="lab-result-heading">
        <div><h2>Run {run.id}</h2><p className="lab-subtle">{run.start} → {run.end}</p></div>
        {canWrite && <Button icon="duplicate" onClick={() => onRerun(candidate.rules)}>Use these rules in a new run</Button>}
      </div>
      <div className="lab-rule-summary">
        <div><strong>Baseline</strong><RulesSummary rules={baseline.rules} /></div>
        <div><strong>Candidate</strong><RulesSummary rules={candidate.rules} /></div>
      </div>
      <section className="lab-result-section">
        <h3>Triage recommendations <LabHelp label="Triage recommendations"
          text="Counts include report arrivals and end-of-replay checks. Open Case evidence to see the matching rule, conditions, and any overridden actions." /></h3>
        {actions.length > 0 ? <HTMLTable compact striped className="full-width lab-metrics">
          <thead><tr><th scope="col">Action</th><th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead>
          <tbody>{actions.map((action) => <tr key={action}><th scope="row">{action}</th>
            <td>{leftActions.get(action) ?? 0}</td><td>{rightActions.get(action) ?? 0}</td></tr>)}</tbody>
        </HTMLTable> : <p>No triage actions were recommended.</p>}
      </section>
      <StartingReports reports={run.result.starting_reports} />
    </section>

    <section className="panel lab-config">
      <div className="lab-result-heading">
        <h2>Case evidence</h2>
        <label className="lab-date">Show
          <select aria-label="Show case evidence" className="bp5-input" value={onlyDifferences ? "triage" : "all"}
            onChange={(event) => setOnlyDifferences(event.currentTarget.value === "triage")}>
            <option value="all">All reports</option>
            <option value="triage">Different triage actions</option>
          </select>
        </label>
      </div>
      {visibleCases.length > 0 && <section className="lab-result-section">
        <h3>Report arrivals</h3>
        {visibleCases.map(({ id, title, reports }) => <details key={id} className="lab-case">
          <summary><code>{id}</code> · {title}</summary>
          <div className="lab-evidence">
            {reports.map((entry) => <ReportEvidence key={entry.report.id} {...entry} />)}
          </div>
        </details>)}
      </section>}
      {visibleEndReports.length > 0 && <section className="lab-result-section">
        <h3>End-of-replay checks</h3>
        <div className="lab-evidence">
          {visibleEndReports.map((entry) => <ReportEvidence key={entry.report.id} {...entry} />)}
        </div>
      </section>}
      {visibleCases.length === 0 && visibleEndReports.length === 0 && <p>No reports match this view.</p>}
    </section>
  </>;
}
