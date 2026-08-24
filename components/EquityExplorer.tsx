"use client";

import { useMemo, useState } from "react";
import type { Benchmark, EquityPoint } from "@/lib/data";
import { RegimeEquityChart, type Regime } from "@/components/RegimeEquityChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { pct, shortDate } from "@/lib/format";

// Interactive wrapper around the lifecycle equity + drawdown charts: preset
// buttons jump to a phase (out-of-sample / live), and two date inputs set an
// arbitrary window. Both charts re-render against the visible slice, so the
// y-axis and drawdown rescale to whatever range is shown.
// Client component (state); the charts it wraps are already client components.

interface Preset {
  key: string;
  label: string;
  from: string;
  to: string;
}

function clamp(value: string, lo: string, hi: string): string {
  if (value < lo) return lo;
  if (value > hi) return hi;
  return value;
}

export function EquityExplorer({
  points,
  segmentCurves,
  regimes,
  benchmark,
  currency = "USD",
  liveSince,
}: {
  points: EquityPoint[];
  segmentCurves?: Partial<Record<"training" | "oos", EquityPoint[]>>;
  regimes: Regime[];
  benchmark?: Benchmark;
  currency?: string;
  liveSince?: string;
}) {
  const first = points[0]?.d ?? "";
  const last = points[points.length - 1]?.d ?? "";

  // Build the phase presets from the regimes that actually intersect the curve.
  const presets = useMemo<Preset[]>(() => {
    if (!first || !last) return [];
    const out: Preset[] = [{ key: "full", label: "Full history", from: first, to: last }];

    const trainings = regimes.filter((r) => r.kind === "training");
    if (trainings.length > 0) {
      const trainingCurve = segmentCurves?.training;
      const from =
        trainingCurve && trainingCurve.length >= 2
          ? trainingCurve[0].d
          : clamp(
              trainings.reduce((m, r) => (r.start < m ? r.start : m), trainings[0].start),
              first,
              last,
            );
      const to =
        trainingCurve && trainingCurve.length >= 2
          ? trainingCurve[trainingCurve.length - 1].d
          : clamp(
              trainings.reduce((m, r) => (r.end > m ? r.end : m), trainings[0].end),
              first,
              last,
            );
      out.push({ key: "training", label: "Training", from, to });
    }

    const oos = regimes.find((r) => r.kind === "oos");
    if (oos) {
      const oosCurve = segmentCurves?.oos;
      out.push({
        key: "oos",
        label: "Out-of-sample",
        from: oosCurve && oosCurve.length >= 2 ? oosCurve[0].d : clamp(oos.start, first, last),
        to:
          oosCurve && oosCurve.length >= 2
            ? oosCurve[oosCurve.length - 1].d
            : clamp(oos.end, first, last),
      });
    }

    const live = regimes.find((r) => r.kind === "live");
    const liveStart = live?.start ?? liveSince;
    if (liveStart && liveStart <= last) {
      out.push({ key: "live", label: "Live", from: clamp(liveStart, first, last), to: last });
    }

    return out;
  }, [regimes, segmentCurves, first, last, liveSince]);

  const initialLive = Boolean(liveSince && liveSince >= first && liveSince <= last);
  const [from, setFrom] = useState(initialLive ? liveSince! : first);
  const [to, setTo] = useState(last);
  const [active, setActive] = useState(initialLive ? "live" : "full");

  const visible = useMemo(() => {
    const segment = active === "training" || active === "oos" ? segmentCurves?.[active] : undefined;
    const source = segment && segment.length >= 2 ? segment : points;
    return source.filter((p) => p.d >= from && p.d <= to);
  }, [points, segmentCurves, active, from, to]);

  function applyPreset(p: Preset) {
    setFrom(p.from);
    setTo(p.to);
    setActive(p.key);
  }

  // Too narrow a window can leave < 2 points; the charts render nothing then.
  const tooNarrow = visible.length < 2;
  const visibleReturn = visible.length > 1
    ? visible[visible.length - 1].v / visible[0].v - 1
    : 0;
  let peak = -Infinity;
  let worstDrawdown = 0;
  for (const point of visible) {
    peak = Math.max(peak, point.v);
    if (peak > 0) worstDrawdown = Math.min(worstDrawdown, point.v / peak - 1);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {presets.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => applyPreset(p)}
              aria-pressed={active === p.key}
              className={
                "rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors " +
                (active === p.key
                  ? "border-accent/40 bg-accent/15 text-accent"
                  : "border-hair text-ink-muted hover:border-ink-muted/40 hover:text-ink")
              }
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <label className="flex items-center gap-1.5">
            <span className="sr-only">From</span>
            <input
              type="date"
              value={from}
              min={first}
              max={to}
              onChange={(e) => {
                setFrom(clamp(e.target.value || first, first, to));
                setActive("custom");
              }}
              className="rounded border border-hair bg-panel px-2 py-1 text-ink [color-scheme:dark]"
            />
          </label>
          <span aria-hidden>→</span>
          <label className="flex items-center gap-1.5">
            <span className="sr-only">To</span>
            <input
              type="date"
              value={to}
              min={from}
              max={last}
              onChange={(e) => {
                setTo(clamp(e.target.value || last, from, last));
                setActive("custom");
              }}
              className="rounded border border-hair bg-panel px-2 py-1 text-ink [color-scheme:dark]"
            />
          </label>
        </div>
      </div>

      {!tooNarrow ? (
        <p className="text-xs text-ink-muted" role="status" aria-live="polite">
          Showing {visible.length} observations from {shortDate(visible[0].d)} to{" "}
          {shortDate(visible[visible.length - 1].d)}: {pct(visibleReturn)} total return and{" "}
          {pct(worstDrawdown)} maximum drawdown in this view.
        </p>
      ) : null}

      {tooNarrow ? (
        <p className="panel p-6 text-center text-sm text-ink-muted">
          Selected window is too short to plot. Widen the range
          {first && last ? (
            <>
              {" "}
              (curve runs {shortDate(first)} – {shortDate(last)})
            </>
          ) : null}
          .
        </p>
      ) : (
        <>
          <RegimeEquityChart
            points={visible}
            regimes={regimes}
            benchmark={benchmark}
            currency={currency}
            liveSince={liveSince}
          />
          <div className="mt-1">
            <DrawdownChart points={visible} liveSince={liveSince} />
          </div>
        </>
      )}
    </div>
  );
}
