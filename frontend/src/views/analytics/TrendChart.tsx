import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import type { TrendInterval, TrendSeries } from "../../api/types";
import { firstIncompletePeriod, periodLabel } from "../../domain/periods";

export const SERIES_COLORS = ["#4C90F0", "#EC9A3C", "#32A467", "#D69FD6", "#F0B726", "#68C1EE"];
export const OTHER_COLOR = "#8F99A8";

export function seriesColor(series: TrendSeries, index: number): string {
  return series.key === "__other__" ? OTHER_COLOR : SERIES_COLORS[index % SERIES_COLORS.length]!;
}

const toSec = (period: string) => Date.parse(`${period}T00:00:00Z`) / 1000;

interface Props {
  series: TrendSeries[];
  interval: TrendInterval;
  incompleteAfter: string;
  onPick: (seriesIndex: number, period: string) => void;
}

export function TrendChart({ series, interval, incompleteAfter, onPick }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;
  const [hover, setHover] = useState<{ period: string; counts: number[] } | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const periods = [...new Set(series.flatMap((s) => s.points.map((p) => p.period)))].sort();
    const xs = periods.map(toSec);
    const ys = series.map((s) => {
      const byPeriod = new Map(s.points.map((p) => [p.period, p.count]));
      return periods.map((p) => byPeriod.get(p) ?? 0);
    });
    const bars = series.length === 1;
    const firstIncomplete = firstIncompletePeriod(periods, interval, incompleteAfter);
    const axisStroke = "#ABB3BF";
    const grid = { stroke: "rgba(171,179,191,0.12)", width: 1 };

    const shadeIncomplete = (u: uPlot) => {
      if (firstIncomplete === undefined) return;
      const left = Math.max(u.valToPos(toSec(firstIncomplete), "x", true), u.bbox.left);
      const right = u.bbox.left + u.bbox.width;
      if (left >= right) return;
      const ctx = u.ctx;
      ctx.save();
      ctx.fillStyle = "rgba(236,154,60,0.10)";
      ctx.fillRect(left, u.bbox.top, right - left, u.bbox.height);
      ctx.fillStyle = "#EC9A3C";
      ctx.font = `${11 * devicePixelRatio}px sans-serif`;
      ctx.textAlign = "right";
      ctx.fillText("incomplete", right - 4 * devicePixelRatio, u.bbox.top + 12 * devicePixelRatio);
      ctx.restore();
    };

    const opts: uPlot.Options = {
      width: el.clientWidth,
      height: 300,
      padding: [12, 12, 0, 0],
      cursor: { points: { size: 7 }, drag: { x: false, y: false } },
      legend: { show: false },
      scales: { x: { time: true }, y: { range: (_u, _min, max) => [0, Math.max(1, max) * 1.08] } },
      axes: [
        { stroke: axisStroke, grid, ticks: grid },
        { stroke: axisStroke, grid, ticks: grid, size: 52, label: "Reports", labelSize: 18 },
      ],
      series: [
        { value: (_u, v) => (v === null ? "" : periodLabel(new Date(v * 1000).toISOString().slice(0, 10), interval)) },
        ...series.map((s, i): uPlot.Series => ({
          label: s.label,
          stroke: seriesColor(s, i),
          fill: bars ? `${seriesColor(s, i)}B3` : undefined,
          width: bars ? 0 : 1.75,
          paths: bars ? uPlot.paths.bars?.({ size: [0.8, 40] }) : undefined,
          points: { show: !bars && periods.length <= 60, size: 4 },
        })),
      ],
      hooks: {
        drawClear: [shadeIncomplete],
        setCursor: [(u) => {
          const idx = u.cursor.idx;
          const period = idx === null || idx === undefined ? undefined : periods[idx];
          setHover(period && idx !== null && idx !== undefined ? { period, counts: ys.map((col) => col[idx] ?? 0) } : null);
        }],
      },
    };

    const u = new uPlot(opts, [xs, ...ys], el);

    const onClick = () => {
      const idx = u.cursor.idx;
      const top = u.cursor.top;
      if (idx === null || idx === undefined || top === undefined || top < 0) return;
      let best = 0;
      let bestDist = Infinity;
      ys.forEach((col, si) => {
        const dist = Math.abs(u.valToPos(col[idx] ?? 0, "y") - top);
        if (dist < bestDist) { bestDist = dist; best = si; }
      });
      const period = periods[idx];
      if (period) pickRef.current(best, period);
    };
    u.over.addEventListener("click", onClick);
    u.over.style.cursor = "pointer";

    const ro = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height: 300 }));
    ro.observe(el);
    return () => {
      ro.disconnect();
      u.over.removeEventListener("click", onClick);
      u.destroy();
    };
  }, [series, interval, incompleteAfter]);

  return (
    <div className="trend">
      <div ref={host} className="trend-chart" />
      <div className="trend-readout">
        {hover ? (
          <>
            <strong>{periodLabel(hover.period, interval)}</strong>
            {series.map((s, i) => (
              <span key={s.key} className="readout-item">
                <span className="swatch" style={{ background: seriesColor(s, i) }} />{s.label} {hover.counts[i]?.toLocaleString("en-US")}
              </span>
            ))}
            <span className="readout-hint">Click to open these reports</span>
          </>
        ) : (
          series.map((s, i) => (
            <span key={s.key} className="readout-item">
              <span className="swatch" style={{ background: seriesColor(s, i) }} />{s.label} · {s.total.toLocaleString("en-US")} total
            </span>
          ))
        )}
      </div>
    </div>
  );
}
