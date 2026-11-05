import type { TrendInterval } from "../api/types";

const MONTHS: Record<TrendInterval, number> = { month: 1, quarter: 3, year: 12 };

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function periodRange(period: string, interval: TrendInterval): { from: string; to: string } {
  const start = new Date(`${period}T00:00:00Z`);
  const end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + MONTHS[interval], 0));
  return { from: period, to: iso(end) };
}

export function periodLabel(period: string, interval: TrendInterval): string {
  const d = new Date(`${period}T00:00:00Z`);
  const y = d.getUTCFullYear();
  if (interval === "year") return String(y);
  if (interval === "quarter") return `${y} Q${Math.floor(d.getUTCMonth() / 3) + 1}`;
  return `${y}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function clampRange(range: { from: string; to: string }, bound: { from?: string; to?: string }) {
  return {
    from: bound.from && bound.from > range.from ? bound.from : range.from,
    to: bound.to && bound.to < range.to ? bound.to : range.to,
  };
}
