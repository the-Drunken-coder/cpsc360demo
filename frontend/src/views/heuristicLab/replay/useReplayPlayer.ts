import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api } from "../../../api/client";
import type { LabCaseAction, LabTriageRule } from "../../../api/heuristicLab";
import { addDays, daysBetween, initialReplay, type Mark, nextDay, replayReducer, windowArrivals } from "../../../domain/replay";

export const SPEEDS = [
  { days: 1, label: "1 day/s" },
  { days: 7, label: "1 week/s" },
  { days: 30, label: "1 month/s" },
] as const;
export type Speed = typeof SPEEDS[number]["days"];

/** Days fetched per request. The next window is fetched while the current one plays. */
const WINDOW_DAYS = 31;
const MIN_TICK_MS = 100;

/** A rule set and the first day it applies to. */
export interface AppliedRules {
  from: string;
  rules: LabTriageRule<LabCaseAction>[];
  /** Draft id of each rule, by position. */
  ids: number[];
}

function windowStart(applied: AppliedRules, day: string) {
  return addDays(applied.from, Math.floor(daysBetween(applied.from, day) / WINDOW_DAYS) * WINDOW_DAYS);
}

export function useReplayPlayer(range: { start: string; end: string }, applied: AppliedRules) {
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(replayReducer, range, ({ start, end }) => initialReplay(start, end));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(7);

  const upcoming = nextDay(state);
  const finished = upcoming === null;
  const { start, end } = range;
  const windowQuery = (since: string | null) => ({
    // Keyed by the rules themselves, since cached windows outlive a closed Replay.
    queryKey: ["heuristic-lab", "replay", start, end, applied.from, applied.rules, applied.ids, since],
    queryFn: async () => {
      const from = since ?? start;
      const last = addDays(from, WINDOW_DAYS - 1);
      const until = last < end ? last : end;
      const window = await api.labReplayWindow({ start, end, since: from, until, rules: applied.rules });
      return windowArrivals(window, applied.rules.map((rule, position) => ({ id: applied.ids[position] ?? -1, name: rule.name })));
    },
    enabled: since !== null && since <= end && state.start === start && state.end === end,
    staleTime: Infinity,
    gcTime: 60_000,
  });
  const currentSince = upcoming && upcoming >= applied.from ? windowStart(applied, upcoming) : null;
  const current = useQuery(windowQuery(currentSince));
  const following = useQuery(windowQuery(currentSince && addDays(currentSince, WINDOW_DAYS)));

  // Ticks read the newest state and windows without restarting the timer.
  const live = useRef({ state, current: current.data, following: following.data });
  live.current = { state, current: current.data, following: following.data };

  const advance = useCallback((days: number) => {
    let day = nextDay(live.current.state);
    for (let step = 0; step < days && day !== null; step += 1) {
      const arrival = live.current.current?.get(day) ?? live.current.following?.get(day);
      if (!arrival) return;
      dispatch({ type: "reveal", arrival });
      day = day < live.current.state.end ? addDays(day, 1) : null;
    }
    if (day === null) setPlaying(false);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const interval = Math.max(1000 / speed, MIN_TICK_MS);
    const perTick = Math.max(1, Math.round((speed * interval) / 1000));
    const timer = window.setInterval(() => advance(perTick), interval);
    return () => window.clearInterval(timer);
  }, [playing, speed, advance]);

  const reset = useCallback((next: { start: string; end: string }) => {
    setPlaying(false);
    dispatch({ type: "reset", ...next });
    void queryClient.removeQueries({ queryKey: ["heuristic-lab", "replay"] });
  }, [queryClient]);

  return {
    state,
    playing: playing && !finished,
    finished,
    buffering: playing && !finished && current.isPending,
    error: current.error ?? following.error,
    speed,
    setSpeed,
    upcoming,
    play: () => { if (!finished) setPlaying(true); },
    pause: () => setPlaying(false),
    reset,
    mark: (id: string, markState: Mark["state"]) => dispatch({ type: "mark", id, state: markState }),
  };
}
