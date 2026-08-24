"use client";

import { useId, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Benchmark, EquityPoint } from "@/lib/data";
import { axisDate, compactMoney, money, shortDate, spanDays } from "@/lib/format";
import { scaledBenchmarkOverlay } from "@/components/charts/benchmarkOverlay";
import { CHART } from "@/components/charts/chartColors";

// Full equity curve: a terminal-style line with a faint grid, a soft area
// fill, and hover-to-inspect tooltips. When `liveSince` is given the curve is
// split into a muted/dashed out-of-sample backfill segment and a solid live
// segment, with a marker at the live-since boundary.
export function EquityCurveChart({
  points,
  benchmark,
  currency = "USD",
  height = 200,
  liveSince,
}: {
  points: EquityPoint[];
  benchmark?: Benchmark;
  currency?: string;
  height?: number;
  liveSince?: string;
}) {
  const rawId = useId().replace(/:/g, "");
  const liveGradientId = `equity-live-${rawId}`;
  const [showBenchmark, setShowBenchmark] = useState(Boolean(benchmark));
  if (points.length < 2) return null;

  const { overlay, values: benchmarkValues } = scaledBenchmarkOverlay(points, benchmark);
  const benchmarkVisible = Boolean(benchmark && showBenchmark && benchmarkValues.length > 1);
  // A tight domain makes the curve's shape legible rather than flat near zero.
  const values = benchmarkVisible ? points.map((p) => p.v).concat(benchmarkValues) : points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || max * 0.02;
  // Compact y labels (e.g. "$147M") once values run into the millions, where a
  // full "$146,638,651" would overflow the narrow axis; full money below that.
  const fmtY = (v: number) => (max >= 1_000_000 ? compactMoney(v, currency) : money(v, currency));
  // Adaptive x labels: wide spans collapse the date to the year so a multi-year
  // curve isn't labelled with ambiguous "Apr 01"-style month/day-looking ticks.
  const span = spanDays(points[0].d, points[points.length - 1].d);

  // Shared axis/grid/tooltip config (recharts needs these as direct children,
  // so we spread plain prop objects rather than wrap them in components).
  const gridProps = {
    stroke: CHART.grid,
    strokeDasharray: "2 4",
    vertical: false,
  } as const;
  const xProps = {
    dataKey: "d",
    tickFormatter: (d: string) => axisDate(d, span),
    tick: { fill: CHART.inkMuted, fontSize: 10 },
    tickLine: false,
    axisLine: { stroke: CHART.grid },
    minTickGap: 36,
  } as const;
  const yProps = {
    width: 52,
    domain: [min - pad, max + pad] as [number, number],
    tickFormatter: fmtY,
    tick: { fill: CHART.inkMuted, fontSize: 10 },
    tickLine: false,
    axisLine: false,
  } as const;
  const tooltipProps = {
    cursor: { stroke: CHART.inkMuted, strokeDasharray: "3 3" },
    contentStyle: {
      background: CHART.panel,
      border: `1px solid ${CHART.grid}`,
      borderRadius: 6,
      fontSize: 12,
    },
    labelStyle: { color: CHART.inkMuted },
    itemStyle: { color: CHART.ink },
    labelFormatter: (d: unknown) => shortDate(String(d)),
    formatter: (v: unknown, name: unknown) => {
      if (v == null) return [] as unknown as [string, string];
      const label = name === "vBenchmark" ? (benchmark?.name ?? "S&P 500") : "Account equity";
      return [money(Number(v), currency), label] as [string, string];
    },
  } as const;
  const BenchmarkLine = benchmarkVisible ? (
    <Line
      type="monotone"
      dataKey="vBenchmark"
      stroke={CHART.benchmark}
      strokeWidth={1.35}
      strokeDasharray="2 3"
      dot={false}
      activeDot={{ r: 3, fill: CHART.benchmark }}
      connectNulls={false}
      isAnimationActive={false}
    />
  ) : null;
  const BenchmarkToggle = benchmark ? (
    <label
      className="inline-flex cursor-pointer items-center gap-1.5 font-mono text-[10px] text-ink-muted"
      onClick={(e) => e.stopPropagation()}
    >
      <input
        type="checkbox"
        checked={showBenchmark}
        onChange={(e) => setShowBenchmark(e.target.checked)}
        className="h-3 w-3 accent-accent"
      />
      <span className="inline-block h-0 w-3 border-t border-dashed" style={{ borderColor: CHART.benchmark }} />
      {benchmark.name}
    </label>
  ) : null;

  // Boundary: first point on/after the live date. Split only when it falls
  // strictly inside the curve (some backfill before, some live after).
  const boundary = liveSince ? points.findIndex((p) => p.d >= liveSince) : -1;
  const split = boundary > 0 && boundary < points.length;

  if (!split) {
    // Single-tone fallback (no backfill, or curve entirely one side).
    const up = points[points.length - 1].v >= points[0].v;
    const stroke = up ? CHART.gain : CHART.loss;
    const gradientId = `equity-${rawId}`;
    const data = points.map((p, i) => ({ ...p, vBenchmark: overlay[i]?.vBenchmark ?? null }));
    return (
      <div>
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer minWidth={0} initialDimension={{ width: 800, height }}>
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid {...gridProps} />
              <XAxis {...xProps} />
              <YAxis {...yProps} />
              <Tooltip {...tooltipProps} />
              <Area
                type="monotone"
                dataKey="v"
                stroke={stroke}
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 3, fill: stroke }}
                isAnimationActive={false}
              />
              {BenchmarkLine}
            </AreaChart>
          </ResponsiveContainer>
        </div>
        {BenchmarkToggle ? <div className="mt-1">{BenchmarkToggle}</div> : null}
      </div>
    );
  }

  // Two-tone: pre-live (backtest) muted/dashed, live solid. Both carry the
  // boundary point so the segments join without a gap.
  const data = points.map((p, i) => ({
    d: p.d,
    vBack: i <= boundary ? p.v : null,
    vLive: i >= boundary ? p.v : null,
    vBenchmark: overlay[i]?.vBenchmark ?? null,
  }));
  const liveUp = points[points.length - 1].v >= points[boundary].v;
  const liveStroke = liveUp ? CHART.gain : CHART.loss;

  return (
    <div>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer minWidth={0} initialDimension={{ width: 800, height }}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={liveGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={liveStroke} stopOpacity={0.22} />
                <stop offset="100%" stopColor={liveStroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid {...gridProps} />
            <XAxis {...xProps} />
            <YAxis {...yProps} />
            <Tooltip {...tooltipProps} />
            <ReferenceLine
              x={points[boundary].d}
              stroke={CHART.accent}
              strokeDasharray="3 3"
              label={{
                value: "Live",
                position: "insideTopRight",
                fill: CHART.accent,
                fontSize: 10,
              }}
            />
            <Area
              type="monotone"
              dataKey="vBack"
              stroke={CHART.inkMuted}
              strokeWidth={1.25}
              strokeDasharray="4 3"
              fill="none"
              dot={false}
              activeDot={{ r: 3, fill: CHART.inkMuted }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="vLive"
              stroke={liveStroke}
              strokeWidth={1.5}
              fill={`url(#${liveGradientId})`}
              dot={false}
              activeDot={{ r: 3, fill: liveStroke }}
              connectNulls={false}
              isAnimationActive={false}
            />
            {BenchmarkLine}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[10px] text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-0 w-3 border-t border-dashed border-ink-muted" />
          Backtest (out-of-sample)
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            className="inline-block h-0 w-3 border-t"
            style={{ borderColor: liveStroke }}
          />
          Live since {shortDate(liveSince!)}
        </span>
        {BenchmarkToggle}
      </p>
    </div>
  );
}
