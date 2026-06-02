"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/data";
import { money, shortDate } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// Full equity curve: a terminal-style line with a faint grid, a soft area
// fill, and hover-to-inspect tooltips. Replaces the lightweight Sparkline.
export function EquityCurveChart({
  points,
  currency = "USD",
  height = 200,
}: {
  points: EquityPoint[];
  currency?: string;
  height?: number;
}) {
  if (points.length < 2) return null;

  const up = points[points.length - 1].v >= points[0].v;
  const stroke = up ? CHART.gain : CHART.loss;
  const gradientId = `equity-${points[0].d}-${points[points.length - 1].d}`;

  // A tight domain makes the curve's shape legible rather than flat near zero.
  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || max * 0.02;

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
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="d"
            tickFormatter={(d: string) =>
              new Date(d + "T00:00:00Z").toLocaleDateString("en-US", {
                month: "short",
                timeZone: "UTC",
              })
            }
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            minTickGap={28}
          />
          <YAxis
            width={52}
            domain={[min - pad, max + pad]}
            tickFormatter={(v: number) => money(v, currency)}
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
            formatter={(v) => [money(Number(v), currency), "Equity"]}
          />
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
