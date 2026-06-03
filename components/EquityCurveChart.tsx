"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/data";
import { money, shortDate } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// Full equity curve: a terminal-style line with a faint grid, a soft area
// fill, and hover-to-inspect tooltips. When `liveSince` is given the curve is
// split into a muted/dashed out-of-sample backfill segment and a solid live
// segment, with a marker at the live-since boundary.
export function EquityCurveChart({
  points,
  currency = "USD",
  height = 200,
  liveSince,
}: {
  points: EquityPoint[];
  currency?: string;
  height?: number;
  liveSince?: string;
}) {
  if (points.length < 2) return null;

  // A tight domain makes the curve's shape legible rather than flat near zero.
  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || max * 0.02;

  // Shared axis/grid/tooltip config (recharts needs these as direct children,
  // so we spread plain prop objects rather than wrap them in components).
  const gridProps = {
    stroke: CHART.grid,
    strokeDasharray: "2 4",
    vertical: false,
  } as const;
  const xProps = {
    dataKey: "d",
    tickFormatter: (d: string) =>
      new Date(d + "T00:00:00Z").toLocaleDateString("en-US", {
        month: "short",
        timeZone: "UTC",
      }),
    tick: { fill: CHART.inkMuted, fontSize: 10 },
    tickLine: false,
    axisLine: { stroke: CHART.grid },
    minTickGap: 28,
  } as const;
  const yProps = {
    width: 52,
    domain: [min - pad, max + pad] as [number, number],
    tickFormatter: (v: number) => money(v, currency),
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
    formatter: (v: unknown) =>
      v == null
        ? ([] as unknown as [string, string])
        : ([money(Number(v), currency), "Equity"] as [string, string]),
  } as const;

  // Boundary: first point on/after the live date. Split only when it falls
  // strictly inside the curve (some backfill before, some live after).
  const boundary = liveSince ? points.findIndex((p) => p.d >= liveSince) : -1;
  const split = boundary > 0 && boundary < points.length;

  if (!split) {
    // Single-tone fallback (no backfill, or curve entirely one side).
    const up = points[points.length - 1].v >= points[0].v;
    const stroke = up ? CHART.gain : CHART.loss;
    const gradientId = `equity-${points[0].d}-${points[points.length - 1].d}`;
    return (
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
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
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Two-tone: pre-live (backtest) muted/dashed, live solid. Both carry the
  // boundary point so the segments join without a gap.
  const data = points.map((p, i) => ({
    d: p.d,
    vBack: i <= boundary ? p.v : null,
    vLive: i >= boundary ? p.v : null,
  }));
  const liveUp = points[points.length - 1].v >= points[boundary].v;
  const liveStroke = liveUp ? CHART.gain : CHART.loss;

  return (
    <div>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="equity-live" x1="0" y1="0" x2="0" y2="1">
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
              fill="url(#equity-live)"
              dot={false}
              activeDot={{ r: 3, fill: liveStroke }}
              connectNulls={false}
              isAnimationActive={false}
            />
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
      </p>
    </div>
  );
}
