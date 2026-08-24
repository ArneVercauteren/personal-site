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
import type { RollingSharpePoint } from "@/lib/data";
import { axisDate, dateOnly, shortDate, spanDays } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// Cap on plotted points: the series can run to thousands of daily values, more
// than a few-hundred-pixel-wide chart can resolve. Strided downsampling keeps
// the shape while staying snappy; the first and last points are always kept.
const MAX_POINTS = 800;

function downsample(points: RollingSharpePoint[]): RollingSharpePoint[] {
  if (points.length <= MAX_POINTS) return points;
  const stride = Math.ceil(points.length / MAX_POINTS);
  const out = points.filter((_, i) => i % stride === 0);
  const last = points[points.length - 1];
  if (out[out.length - 1] !== last) out.push(last);
  return out;
}

// Rolling 3-year annualized Sharpe over time, with a zero reference line. The
// area is accent-toned; dips below zero read as stretches of negative risk-
// adjusted return.
export function RollingSharpeChart({
  series,
  height = 220,
}: {
  series: RollingSharpePoint[];
  height?: number;
}) {
  if (!series || series.length < 2) return null;
  const data = downsample(series).map((p) => ({
    d: dateOnly(p.date),
    sharpe: p.sharpe,
  }));
  const span = spanDays(data[0].d, data[data.length - 1].d);
  const values = data.map((p) => p.sharpe);
  const min = Math.min(0, ...values);
  const max = Math.max(...values);

  return (
    <div
      role="img"
      aria-label={`Rolling Sharpe chart from ${shortDate(data[0].d)} to ${shortDate(data.at(-1)!.d)}; minimum ${min.toFixed(2)}, maximum ${max.toFixed(2)}.`}
      style={{ width: "100%", height }}
    >
      <ResponsiveContainer minWidth={0} initialDimension={{ width: 800, height }}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="rsharpe-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.accent} stopOpacity={0.22} />
              <stop offset="100%" stopColor={CHART.accent} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="d"
            tickFormatter={(d: string) => axisDate(d, span)}
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            minTickGap={36}
          />
          <YAxis
            width={40}
            domain={[Math.floor(min * 10) / 10, Math.ceil(max * 10) / 10]}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ stroke: CHART.inkMuted, strokeDasharray: "3 3" }}
            contentStyle={{
              background: CHART.panel,
              border: `1px solid ${CHART.grid}`,
              borderRadius: 6,
              fontSize: 12,
            }}
            labelStyle={{ color: CHART.inkMuted }}
            itemStyle={{ color: CHART.ink }}
            labelFormatter={(d) => shortDate(String(d))}
            formatter={(v: unknown) => [Number(v).toFixed(2), "Rolling Sharpe"]}
          />
          <ReferenceLine y={0} stroke={CHART.grid} />
          <Area
            type="monotone"
            dataKey="sharpe"
            stroke={CHART.accent}
            strokeWidth={1.5}
            fill="url(#rsharpe-fill)"
            dot={false}
            activeDot={{ r: 3, fill: CHART.accent }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
