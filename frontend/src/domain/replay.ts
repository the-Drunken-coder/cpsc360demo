import type { LabReplayLinkedReport, LabReplayRecall, LabReplayReport, LabReplayWindow } from "../api/heuristicLab";

// Replay state for one play-through. Dates are ISO days compared as strings.
// A report is "flagged" on arrival when its first matching rule sends it for review, or by hand.
// A recall counts as caught when any covered report was still flagged at the
// announcement and was flagged on or before its `flag_by` day. Marks on a report
// lock once a recall covering it is announced, so the score can't be revised later.

export type FlagSource = { kind: "rule"; ruleId: number; name: string } | { kind: "hand" };
export type Mark = { state: "flagged"; on: string; by: FlagSource } | { state: "dismissed"; on: string };

export interface FeedItem {
  report: LabReplayReport;
  /** Rule ids that matched, in rule order. */
  ruleIds: number[];
  /** Name of the first matching rule. */
  ruleName: string | null;
}

export type RecallOutcome =
  | { kind: "caught"; recall: LabReplayRecall; lead: number; report: LabReplayLinkedReport; by: FlagSource }
  | { kind: "missed"; recall: LabReplayRecall; unflagged: LabReplayLinkedReport[] };

export interface ReplayState {
  start: string;
  end: string;
  /** The last revealed day, or null before the replay starts. */
  day: string | null;
  marks: ReadonlyMap<string, Mark>;
  ruleCounts: ReadonlyMap<number, number>;
  unmatched: number;
  /** Recent reports, newest day first, capped at FEED_DAYS revealed days. */
  feed: FeedItem[];
  /** Covered report id → its flag-by day, for every announced recall. */
  recalled: ReadonlyMap<string, string>;
  outcomes: RecallOutcome[];
}

export interface DayArrival {
  day: string;
  reports: FeedItem[];
  recalls: LabReplayRecall[];
}

export type ReplayAction =
  | { type: "reveal"; arrival: DayArrival }
  | { type: "mark"; id: string; state: Mark["state"] }
  | { type: "reset"; start: string; end: string };

export const FEED_DAYS = 7;
/** Leads count up to a year, so one early flag on a long-lived model can't dominate the median. */
export const LEAD_CAP_DAYS = 365;
/** Flags a reviewer can work through each week, the recall benchmark's budget. */
export const WEEKLY_BUDGET = 3;

export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

/** Split a fetched window into one arrival per day, naming each report's rules by the ids sent with it. */
export function windowArrivals(window: LabReplayWindow, rules: { id: number; name: string }[]): Map<string, DayArrival> {
  const days = new Map<string, DayArrival>();
  for (let day = window.since; day <= window.until; day = addDays(day, 1)) days.set(day, { day, reports: [], recalls: [] });
  for (const report of window.reports) {
    const matched = report.rules.flatMap((position) => rules[position] ?? []);
    days.get(report.published)?.reports.push({ report, ruleIds: matched.map((rule) => rule.id), ruleName: matched[0]?.name ?? null });
  }
  for (const recall of window.recalls) days.get(recall.announced)?.recalls.push(recall);
  return days;
}

export function initialReplay(start: string, end: string): ReplayState {
  return { start, end, day: null, marks: new Map(), ruleCounts: new Map(), unmatched: 0, feed: [],
    recalled: new Map(), outcomes: [] };
}

export function nextDay(state: ReplayState): string | null {
  const next = state.day === null ? state.start : addDays(state.day, 1);
  return next <= state.end ? next : null;
}

function credited(report: LabReplayLinkedReport, marks: ReadonlyMap<string, Mark>) {
  const mark = marks.get(report.id);
  return mark?.state === "flagged" && mark.on <= report.flag_by ? mark : undefined;
}

export function judge(recall: LabReplayRecall, marks: ReadonlyMap<string, Mark>): RecallOutcome {
  let best: { report: LabReplayLinkedReport; mark: Extract<Mark, { state: "flagged" }> } | undefined;
  for (const report of recall.reports) {
    const mark = credited(report, marks);
    if (mark && (!best || mark.on < best.mark.on)) best = { report, mark };
  }
  return best
    ? { kind: "caught", recall, lead: daysBetween(best.mark.on, recall.announced), report: best.report, by: best.mark.by }
    : { kind: "missed", recall, unflagged: recall.reports };
}

function reveal(state: ReplayState, { day, reports, recalls }: DayArrival): ReplayState {
  if (day !== nextDay(state)) return state;
  const marks = new Map(state.marks);
  const ruleCounts = new Map(state.ruleCounts);
  let unmatched = state.unmatched;
  for (const item of reports) {
    const [first] = item.ruleIds;
    if (first === undefined) unmatched += 1;
    else if (item.report.flagged && !marks.has(item.report.id)) {
      marks.set(item.report.id, { state: "flagged", on: day, by: { kind: "rule", ruleId: first, name: item.ruleName ?? "" } });
    }
    for (const id of item.ruleIds) ruleCounts.set(id, (ruleCounts.get(id) ?? 0) + 1);
  }
  const oldest = addDays(day, 1 - FEED_DAYS);
  const ordered = [...reports].sort((a, b) => b.report.id.localeCompare(a.report.id));
  const feed = [...ordered, ...state.feed.filter((item) => item.report.published >= oldest)];
  const recalled = new Map(state.recalled);
  const outcomes = [...state.outcomes];
  for (const recall of recalls) {
    if (outcomes.some((outcome) => outcome.recall.notice_no === recall.notice_no)) continue;
    outcomes.push(judge(recall, marks));
    for (const report of recall.reports) recalled.set(report.id, report.flag_by);
  }
  return { ...state, day, marks, ruleCounts, unmatched, feed, recalled, outcomes };
}

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  switch (action.type) {
    case "reveal": return reveal(state, action.arrival);
    case "mark": {
      if (state.day === null || state.recalled.has(action.id)) return state;
      const current = state.marks.get(action.id);
      if (current?.state === action.state) return state;
      const marks = new Map(state.marks);
      marks.set(action.id, action.state === "flagged"
        ? { state: "flagged", on: state.day, by: { kind: "hand" } }
        : { state: "dismissed", on: state.day });
      return { ...state, marks };
    }
    case "reset": return initialReplay(action.start, action.end);
  }
}

export interface ReplayScore {
  /** Recall waves (near-identical notices count once) with a flag before the announcement. */
  caught: number;
  missed: number;
  /** Median of each caught wave's best lead, capped at LEAD_CAP_DAYS. */
  medianLead: number | null;
  flags: number;
  flagsPerWeek: number;
  /** Flagged reports that no announced recall covers. They may still be real hazards CPSC never acted on. */
  flagsWithoutRecall: number;
  /** Share of flags credited to an announced recall, a floor on true precision. */
  precision: number | null;
}

function median(values: number[]): number | null {
  const sorted = [...values].sort((a, b) => a - b);
  const lower = sorted[Math.floor((sorted.length - 1) / 2)];
  const upper = sorted[Math.floor(sorted.length / 2)];
  return lower === undefined || upper === undefined ? null : (lower + upper) / 2;
}

export function score(state: ReplayState): ReplayScore {
  // Each wave's best capped lead, or null while none of its notices was caught.
  const waves = new Map<string, number | null>();
  for (const outcome of state.outcomes) {
    const lead = outcome.kind === "caught" ? Math.min(outcome.lead, LEAD_CAP_DAYS) : null;
    const best = waves.get(outcome.recall.wave) ?? null;
    waves.set(outcome.recall.wave, lead === null ? best : Math.max(lead, best ?? lead));
  }
  const leads = [...waves.values()].filter((lead) => lead !== null);
  let flags = 0;
  let hits = 0;
  let withoutRecall = 0;
  for (const [id, mark] of state.marks) {
    if (mark.state !== "flagged") continue;
    flags += 1;
    const flagBy = state.recalled.get(id);
    if (flagBy === undefined) withoutRecall += 1;
    else if (mark.on <= flagBy) hits += 1;
  }
  const weeks = state.day === null ? 0 : (daysBetween(state.start, state.day) + 1) / 7;
  return {
    caught: leads.length,
    missed: waves.size - leads.length,
    medianLead: median(leads),
    flags,
    flagsPerWeek: weeks ? flags / weeks : 0,
    flagsWithoutRecall: withoutRecall,
    precision: flags ? hits / flags : null,
  };
}
