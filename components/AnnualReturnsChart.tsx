"use client";

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { pct, signedPct } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// Calendar-year returns as a zero-anchored bar chart: green above the line,
// red below. Reads the `annual_returns` map ({ "2008": -0.36, ... }).
export function AnnualReturnsChart({
  returns,
  height = 240,
}: {
  returns: Record<string, number>;
  height?: number;
}) {
  const data = Object.entries(returns)
    .map(([year, v]) => ({ year, v }))
    .sort((a, b) => a.year.localeCompare(b.year));
  if (data.length === 0) return null;

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            minTickGap={8}
          />
          <YAxis
            width={44}
            tickFormatter={(v: number) => pct(v, 0)}
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ fill: CHART.grid, fillOpacity: 0.3 }}
            contentStyle={{
              background: CHART.panel,
              border: `1px solid ${CHART.grid}`,
              borderRadius: 6,
              fontSize: 12,
            }}
            labelStyle={{ color: CHART.inkMuted }}
            itemStyle={{ color: CHART.ink }}
            formatter={(v: unknown) => [signedPct(Number(v)), "Return"]}
          />
          <ReferenceLine y={0} stroke={CHART.grid} />
          <Bar dataKey="v" isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.year} fill={d.v >= 0 ? CHART.gain : CHART.loss} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
