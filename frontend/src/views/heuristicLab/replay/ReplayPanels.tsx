import { Button, HTMLSelect, Spinner } from "@blueprintjs/core";
import { useEffect, useRef, useState } from "react";
import type { LabReplayLinkedReport } from "../../../api/heuristicLab";
import {
  daysBetween, type FeedItem, LEAD_CAP_DAYS, type Mark, type RecallOutcome, type ReplayScore, WEEKLY_BUDGET,
} from "../../../domain/replay";
import type { RuleDraft } from "../TriageEditor";
import { ruleLabel } from "../TriageEditor";
import { SPEEDS, type Speed } from "./useReplayPlayer";

const DAY = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const PERCENT = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });

function dayLabel(day: string) {
  return DAY.format(new Date(`${day}T00:00:00Z`));
}

export function ReplayBar({ range, bounds, day, upcoming, started, playing, finished, buffering, speed, outcomes,
  onRange, onReset, onPlay, onPause, onSpeed }: {
  range: { start: string; end: string };
  bounds: { first: string; last: string };
  day: string | null;
  upcoming: string | null;
  started: boolean;
  playing: boolean;
  finished: boolean;
  buffering: boolean;
  speed: Speed;
  outcomes: RecallOutcome[];
  onRange: (range: { start: string; end: string }) => void;
  onReset: () => void;
  onPlay: () => void;
  onPause: () => void;
  onSpeed: (speed: Speed) => void;
}) {
  const total = Math.max(1, daysBetween(range.start, range.end) + 1);
  const position = (date: string) => `${(100 * (daysBetween(range.start, date) + 1)) / total}%`;
  const elapsed = day === null ? 0 : daysBetween(range.start, day) + 1;
  // Date inputs report "" while half-typed, so only a complete, in-bounds range reaches the replay.
  const [draft, setDraft] = useState(range);
  function change(next: { start: string; end: string }) {
    setDraft(next);
    if (next.start && next.end && bounds.first <= next.start && next.start <= next.end && next.end <= bounds.last) onRange(next);
  }
  return <div className="replay-bar">
    <Button small icon="reset" aria-label="Reset replay" title="Reset" disabled={!started} onClick={onReset} />
    {playing
      ? <Button small intent="primary" icon="pause" aria-label="Pause" title="Pause (space)" onClick={onPause} />
      : <Button small intent="primary" icon="play" aria-label="Play" title="Play (space)" disabled={finished} onClick={onPlay} />}
    <HTMLSelect minimal aria-label="Replay speed" value={speed}
      onChange={(event) => {
        const next = SPEEDS.find((option) => String(option.days) === event.currentTarget.value);
        if (next) onSpeed(next.days);
      }}>
      {SPEEDS.map((option) => <option key={option.days} value={option.days}>{option.label}</option>)}
    </HTMLSelect>
    <span className="replay-date mono" aria-live="off">{day ?? upcoming ?? range.end}</span>
    {buffering && <Spinner size={14} aria-label="Loading reports" />}
    <div className="replay-track" role="progressbar" aria-label="Replay progress"
      aria-valuemin={0} aria-valuemax={total} aria-valuenow={elapsed}>
      <i style={{ width: `${(100 * elapsed) / total}%` }} />
      {outcomes.map((outcome) => <b key={outcome.recall.notice_no} data-kind={outcome.kind}
        style={{ left: position(outcome.recall.announced) }} title={`${outcome.recall.announced} · ${outcome.recall.title}`} />)}
    </div>
    {started ? <span className="replay-range mono">{range.start} → {range.end}</span>
      : <span className="replay-range">
        <input className="bp5-input bp5-small" type="date" aria-label="Replay start" required min={bounds.first} max={draft.end}
          value={draft.start} onChange={(event) => change({ ...draft, start: event.currentTarget.value })} />
        →
        <input className="bp5-input bp5-small" type="date" aria-label="Replay end" required min={draft.start} max={bounds.last}
          value={draft.end} onChange={(event) => change({ ...draft, end: event.currentTarget.value })} />
      </span>}
  </div>;
}

export function RulesColumn({ rules, counts, unmatched, appliesFrom, onNew, onEdit }: {
  rules: RuleDraft[];
  counts: ReadonlyMap<number, number>;
  unmatched: number;
  appliesFrom: string | null;
  onNew: () => void;
  onEdit: (index: number) => void;
}) {
  return <section className="replay-col" aria-label="Rules">
    <header className="replay-col-head"><h2>Rules</h2><Button small minimal icon="plus" text="New" onClick={onNew} /></header>
    <ul className="replay-rows">
      {rules.map((rule, index) => {
        const skipped = rule.trigger === "end";
        return <li key={rule.draftId}>
          <button type="button" className="replay-row replay-rule" onClick={() => onEdit(index)}
            title={skipped ? "End-of-replay rules don’t run in replay" : "Edit rule"}>
            <span className={skipped ? "replay-muted" : undefined}>{ruleLabel(rule).name}</span>
            <span className="mono">{skipped ? "end only" : (counts.get(rule.draftId) ?? 0).toLocaleString()}</span>
          </button>
        </li>;
      })}
      <li className="replay-row replay-muted"><span>Unmatched</span><span className="mono">{unmatched.toLocaleString()}</span></li>
    </ul>
    {rules.length === 0 && <p className="replay-note">Add a rule, such as narrative contains “candle”, to flag reports as they arrive.</p>}
    {appliesFrom && <p className="replay-note">Current rules apply from {appliesFrom}.</p>}
  </section>;
}

export function FeedColumn({ day, feed, marks, cursorId, onCursor, onOpen, onMark }: {
  day: string | null;
  feed: FeedItem[];
  marks: ReadonlyMap<string, Mark>;
  cursorId: string | null;
  onCursor: (id: string) => void;
  onOpen: (id: string) => void;
  onMark: (id: string, state: Mark["state"]) => void;
}) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    list.current?.querySelector("[data-cursor]")?.scrollIntoView({ block: "nearest" });
  }, [cursorId]);
  const today = feed.filter((item) => item.report.published === day).length;
  const days: { day: string; items: FeedItem[] }[] = [];
  for (const item of feed) {
    const last = days.at(-1);
    if (last?.day === item.report.published) last.items.push(item);
    else days.push({ day: item.report.published, items: [item] });
  }
  return <section className="replay-col replay-feed" aria-label="Incoming reports">
    <header className="replay-col-head">
      <h2>Incoming · today {today}</h2>
      <span className="replay-keys">F flag · D dismiss · J/K move · Enter open</span>
    </header>
    <div ref={list} className="replay-feed-list">
      {day === null && <p className="replay-note">Press play. Reports arrive in publication-date order.</p>}
      {day !== null && feed.length === 0 && <p className="replay-note">No reports in the last week of the replay.</p>}
      {days.map((group) => <div key={group.day} role="group" aria-label={dayLabel(group.day)}>
        <h3 className="replay-day">{group.day === day ? "Today" : dayLabel(group.day)} · {group.items.length}</h3>
        {group.items.map(({ report, ruleName }) => {
          const mark = marks.get(report.id);
          const handFlag = mark?.state === "flagged" && mark.by.kind === "hand";
          return <article key={report.id} className="replay-report" data-cursor={report.id === cursorId || undefined}
            data-mark={mark?.state} onClick={() => { onCursor(report.id); onOpen(report.id); }}>
            <div className="replay-report-top">
              <b>{report.title}</b>
              {ruleName ? <span className="replay-tag" title={report.evidence.join("; ")}>{ruleName}</span>
                : <span className="replay-muted">no rule</span>}
              {handFlag && <span className="replay-tag" data-kind="hand">flagged</span>}
              {mark?.state === "dismissed" && <span className="replay-muted">dismissed</span>}
              <span className="replay-report-actions">
                <Button small minimal icon="flag" aria-label="Flag" title="Flag (F)" active={mark?.state === "flagged"}
                  onClick={(event) => { event.stopPropagation(); onMark(report.id, "flagged"); }} />
                <Button small minimal icon="cross" aria-label="Dismiss" title="Dismiss (D)" active={mark?.state === "dismissed"}
                  onClick={(event) => { event.stopPropagation(); onMark(report.id, "dismissed"); }} />
              </span>
            </div>
            <div className="replay-snippet">{report.product} · {report.snippet}</div>
          </article>;
        })}
      </div>)}
    </div>
  </section>;
}

export function ScoreColumn({ score }: { score: ReplayScore }) {
  const rows: [string, string, string?][] = [
    ["Recalls caught early", score.caught.toLocaleString(), "good"],
    ["Recalls missed", score.missed.toLocaleString(), "bad"],
    ["Median days early", score.medianLead === null ? "–" : score.medianLead.toLocaleString()],
    [`Flags per week (budget ${WEEKLY_BUDGET})`, score.flagsPerWeek.toFixed(1), score.flagsPerWeek > WEEKLY_BUDGET ? "bad" : undefined],
    ["Flags, no recall yet", score.flagsWithoutRecall.toLocaleString()],
    ["Precision, at least", score.precision === null ? "–" : PERCENT.format(score.precision)],
  ];
  return <section className="replay-col" aria-label="Score">
    <header className="replay-col-head"><h2>Score</h2></header>
    <dl className="replay-rows">
      {rows.map(([label, value, tone]) => <div key={label} className="replay-row">
        <dt>{label}</dt><dd className="mono" data-tone={tone}>{value}</dd>
      </div>)}
    </dl>
    <p className="replay-note">
      Recalls are CPSC notices that list a reported model, and near-identical notices count once. A flag counts
      when it comes before the announcement, for up to {LEAD_CAP_DAYS} days of lead. Flags with no recall may still
      be hazards CPSC missed, so precision is a floor.
    </p>
  </section>;
}

function ReportList({ reports, onOpen }: { reports: LabReplayLinkedReport[]; onOpen: (id: string) => void }) {
  const shown = reports.slice(0, 3);
  return <>{shown.map((report, index) => <span key={report.id}>
    {index > 0 && ", "}
    <button type="button" className="replay-link" onClick={() => onOpen(report.id)}>{report.title}</button>
    {` (${report.published})`}
  </span>)}{reports.length > shown.length && `, and ${reports.length - shown.length} more`}</>;
}

export function RecallLog({ outcomes, onOpen }: { outcomes: RecallOutcome[]; onOpen: (id: string) => void }) {
  const latest = outcomes.slice(-3).reverse();
  if (latest.length === 0) return null;
  return <ol className="replay-recalls" aria-label="Recall announcements" aria-live="polite">
    {latest.map((outcome) => {
      const notice = <a href={outcome.recall.url} target="_blank" rel="noreferrer">{outcome.recall.title}</a>;
      return <li key={outcome.recall.notice_no} data-kind={outcome.kind}>
        <b>Recall announced {outcome.recall.announced}:</b> {notice}.{" "}
        {outcome.kind === "caught" ? <>
          You flagged its first report, <button type="button" className="replay-link" onClick={() => onOpen(outcome.report.id)}>
            {outcome.report.title}</button>, <b>{outcome.lead.toLocaleString()} days early</b>{" "}
          ({outcome.by.kind === "rule" ? `rule: ${outcome.by.name}` : "by hand"}).
        </> : <>
          {outcome.unflagged.length === 1 ? "1 earlier report went" : `${outcome.unflagged.length} earlier reports went`} unflagged:{" "}
          <ReportList reports={outcome.unflagged} onOpen={onOpen} />.
        </>}
      </li>;
    })}
  </ol>;
}
