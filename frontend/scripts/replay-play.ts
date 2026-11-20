// Play the Heuristic Lab replay headlessly with a fixed rule set, using the same API
// windows and scoring code as the browser. Rules only: no hand flags.
//
//   npx vite-node scripts/replay-play.ts -- --rules rules.json --start 2019-01-01 --end 2022-06-30 \
//     [--api http://127.0.0.1:8000] [--outcomes]
//
// rules.json is an array of Lab triage rules, the same JSON the Replay drawer sends.
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import type { LabCaseAction, LabReplayWindow, LabTriageRule } from "../src/api/heuristicLab";
import { addDays, daysBetween, initialReplay, nextDay, replayReducer, score, windowArrivals } from "../src/domain/replay";

const WINDOW_DAYS = 31;
const { values } = parseArgs({
  options: {
    rules: { type: "string" },
    start: { type: "string" },
    end: { type: "string" },
    api: { type: "string", default: "http://127.0.0.1:8000" },
    outcomes: { type: "boolean", default: false },
  },
});
const { start, end, api } = values;
if (!values.rules || !start || !end) throw new Error("Pass --rules, --start and --end.");
const rules: LabTriageRule<LabCaseAction>[] = JSON.parse(readFileSync(values.rules, "utf8"));

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const response = await fetch(`${api}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path} ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

const { token } = await post<{ token: string }>("/session", { handle: "viewer" });
const windows: Promise<LabReplayWindow>[] = [];
for (let since = start; since <= end; since = addDays(since, WINDOW_DAYS)) {
  const last = addDays(since, WINDOW_DAYS - 1);
  windows.push(post("/heuristic-lab/replay/window", { start, end, since, until: last < end ? last : end, rules }, token));
}
const named = rules.map((rule, position) => ({ id: position, name: rule.name }));
const days = new Map((await Promise.all(windows)).flatMap((window) => [...windowArrivals(window, named)]));

let state = initialReplay(start, end);
for (let day = nextDay(state); day !== null; day = nextDay(state)) {
  const arrival = days.get(day);
  if (!arrival) throw new Error(`Missing window for ${day}`);
  state = replayReducer(state, { type: "reveal", arrival });
}

const weeks = (daysBetween(start, end) + 1) / 7;
const result = {
  start, end,
  score: score(state),
  flags_per_week: Number((score(state).flags / weeks).toFixed(2)),
  reachable_recalls: state.outcomes.length,
  rule_matches: Object.fromEntries(rules.map((rule, position) => [rule.name, state.ruleCounts.get(position) ?? 0])),
  ...(values.outcomes ? {
    caught: state.outcomes.flatMap((outcome) => outcome.kind === "caught"
      ? [{ notice: outcome.recall.notice_no, title: outcome.recall.title, lead: outcome.lead, report: outcome.report.id,
        rule: outcome.by.kind === "rule" ? outcome.by.name : "hand" }] : []),
  } : {}),
};
console.log(JSON.stringify(result, null, 2));
