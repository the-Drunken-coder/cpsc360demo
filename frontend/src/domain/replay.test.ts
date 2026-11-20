import { describe, expect, it } from "vitest";
import type { LabReplayWindow } from "../api/heuristicLab";
import captured from "./fixtures/replay-ryobi.json";
import {
  type DayArrival, initialReplay, nextDay, replayReducer, type ReplayState, score, windowArrivals,
} from "./replay";

// Real windows from the API: the Ryobi pressure-washer report published 2023-04-12,
// and CPSC notice 25452 announced 2025-08-28 that lists its model.
const arrivalWindow: LabReplayWindow = captured.arrival;
const announcementWindow: LabReplayWindow = captured.announcement;
const RYOBI = "20230324-B2A32-2147348506";
const OTHER = "20230303-7D5FE-2147349071";
const RULE = { id: 41, name: "Pressure washer" };

function play(state: ReplayState, until: string, days: Map<string, DayArrival>): ReplayState {
  let next = nextDay(state);
  while (next !== null && next <= until) {
    state = replayReducer(state, { type: "reveal", arrival: days.get(next) ?? { day: next, reports: [], recalls: [] } });
    next = nextDay(state);
  }
  return state;
}

function arrivals(rules: { id: number; name: string }[]) {
  return new Map([...windowArrivals(arrivalWindow, rules), ...windowArrivals(announcementWindow, rules)]);
}

describe("replay scoring", () => {
  it("credits a rule flag on arrival with its lead to the announcement", () => {
    const days = arrivals([RULE]);
    let state = play(initialReplay("2023-04-01", "2025-09-30"), "2025-08-27", days);
    expect(state.ruleCounts.get(RULE.id)).toBe(1);
    expect(state.unmatched).toBe(arrivalWindow.reports.length - 1);
    expect(state.outcomes).toEqual([]);

    state = play(state, "2025-08-28", days);
    const [outcome] = state.outcomes;
    expect(outcome?.kind).toBe("caught");
    expect(outcome?.kind === "caught" && { lead: outcome.lead, report: outcome.report.id, by: outcome.by })
      .toEqual({ lead: 869, report: RYOBI, by: { kind: "rule", ruleId: RULE.id, name: RULE.name } });
    expect(score(state)).toMatchObject({ caught: 1, missed: 0, medianLead: 869, flags: 1, flagsWithoutRecall: 0, precision: 1 });
  });

  it("credits a hand flag from the day it was made", () => {
    const days = arrivals([]);
    let state = play(initialReplay("2023-04-01", "2025-09-30"), "2023-04-14", days);
    state = replayReducer(state, { type: "mark", id: RYOBI, state: "flagged" });
    state = replayReducer(state, { type: "mark", id: OTHER, state: "flagged" });
    state = play(state, "2025-08-28", days);
    const [outcome] = state.outcomes;
    expect(outcome?.kind === "caught" && { lead: outcome.lead, by: outcome.by }).toEqual({ lead: 867, by: { kind: "hand" } });
    expect(score(state)).toMatchObject({ caught: 1, flags: 2, flagsWithoutRecall: 1, precision: 0.5 });
  });

  it("names the unflagged reports when a recall is missed", () => {
    const days = arrivals([RULE]);
    let state = play(initialReplay("2023-04-01", "2025-09-30"), "2023-04-12", days);
    state = replayReducer(state, { type: "mark", id: RYOBI, state: "dismissed" });
    state = play(state, "2025-08-28", days);
    const [outcome] = state.outcomes;
    expect(outcome?.kind).toBe("missed");
    expect(outcome?.kind === "missed" && outcome.unflagged.map((report) => report.title))
      .toEqual(["Ryobi RY142711VNM", "Ryobi RY142300", "Ryobi RY142711VNM"]);
    expect(score(state)).toMatchObject({ caught: 0, missed: 1, medianLead: null, flags: 0, precision: null });
  });

  it("reveals each recall once and only when its day is played", () => {
    const days = arrivals([RULE]);
    let state = play(initialReplay("2023-04-01", "2025-09-30"), "2025-08-28", days);
    const announcement = days.get("2025-08-28");
    expect(announcement?.recalls).toHaveLength(1);
    if (announcement) expect(replayReducer(state, { type: "reveal", arrival: announcement })).toBe(state);
    state = play(state, "2025-09-30", days);
    expect(state.outcomes).toHaveLength(1);
    expect(state.day).toBe("2025-09-30");
    expect(nextDay(state)).toBeNull();
  });

  it("keeps a week of reports in the feed, newest day first", () => {
    const days = arrivals([RULE]);
    const state = play(initialReplay("2023-04-01", "2025-09-30"), "2023-04-18", days);
    expect(state.feed.map((item) => item.report.published)).toEqual(arrivalWindow.reports.map(() => "2023-04-12"));
    expect(play(state, "2023-04-19", days).feed).toEqual([]);
  });
});
