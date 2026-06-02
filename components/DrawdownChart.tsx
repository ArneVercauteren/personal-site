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
import { pct, shortDate } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// Underwater (drawdown) plot derived from the equity curve: at each point,
// value / running-peak − 1, so it sits at 0 at new highs and dips below during
// losses. Always loss-colored, since drawdown is by definition ≤ 0.
export function DrawdownChart({
  points,
  height = 120,
}: {
  points: EquityPoint[];
  height?: number;
}) {
  if (points.length < 2) return null;

  let peak = -Infinity;
  const series = points.map((p) => {
    peak = Math.max(peak, p.v);
    return { d: p.d, dd: peak > 0 ? p.v / peak - 1 : 0 };
  });

  const minDd = Math.min(...series.map((s) => s.dd));

  return (
    <div>
      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        Drawdown
      </h4>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="dd-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART.loss} stopOpacity={0} />
                <stop offset="100%" stopColor={CHART.loss} stopOpacity={0.28} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="d" hide />
            <YAxis
              width={44}
              domain={[Math.min(minDd * 1.1, -0.01), 0]}
              tickFormatter={(v: number) => pct(v, 0)}
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
              formatter={(v) => [pct(Number(v)), "Drawdown"]}
            />
            <Area
              type="monotone"
              dataKey="dd"
              stroke={CHART.loss}
              strokeWidth={1.25}
              fill="url(#dd-fill)"
              dot={false}
              activeDot={{ r: 3, fill: CHART.loss }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
