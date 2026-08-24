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
  benchmarkReturns,
  benchmarkName = "S&P 500",
  height = 240,
}: {
  returns: Record<string, number>;
  benchmarkReturns?: Record<string, number>;
  benchmarkName?: string;
  height?: number;
}) {
  const data = Object.entries(returns)
    .map(([year, v]) => ({
      year,
      strategy: v,
      benchmark: benchmarkReturns?.[year] ?? null,
    }))
    .sort((a, b) => a.year.localeCompare(b.year));
  if (data.length === 0) return null;

  return (
    <div>
      <div
        role="img"
        aria-label={`Annual returns from ${data[0].year} to ${data.at(-1)!.year}; best ${signedPct(Math.max(...data.map((item) => item.strategy)))}, worst ${signedPct(Math.min(...data.map((item) => item.strategy)))}.`}
        style={{ width: "100%", height }}
      >
        <ResponsiveContainer minWidth={0} initialDimension={{ width: 800, height }}>
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
            formatter={(v: unknown, name: unknown) => {
              if (v == null) return [] as unknown as [string, string];
              return [
                signedPct(Number(v)),
                name === "benchmark" ? benchmarkName : "Strategy",
              ] as [string, string];
            }}
          />
          <ReferenceLine y={0} stroke={CHART.grid} />
          <Bar dataKey="strategy" isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.year} fill={d.strategy >= 0 ? CHART.gain : CHART.loss} />
            ))}
          </Bar>
          {benchmarkReturns ? (
            <Bar
              dataKey="benchmark"
              fill={CHART.benchmark}
              fillOpacity={0.75}
              isAnimationActive={false}
              radius={[2, 2, 0, 0]}
            />
          ) : null}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {benchmarkReturns ? (
        <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-gain" />
            Strategy gain/loss
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: CHART.benchmark, opacity: 0.75 }}
            />
            {benchmarkName}
          </span>
        </p>
      ) : null}
    </div>
  );
}
