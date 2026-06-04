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
import { CHART } from "@/components/charts/chartColors";
import { signedPct } from "@/lib/format";

export interface DivergingDatum {
  label: string;
  value: number;
  /** Optional per-bar explanation, shown in the tooltip. */
  help?: string;
}

// How bar values render. A string key (not a function) so a Server Component
// can configure the chart without passing a non-serializable callback.
//   "ratio"      -> 2-decimal number (e.g. factor betas: 1.14)
//   "signed-pct" -> signed whole-percent (e.g. sector tilts: +18%)
export type DivergingFormat = "ratio" | "signed-pct";

function formatter(format: DivergingFormat): (n: number) => string {
  return format === "signed-pct" ? (n) => signedPct(n, 0) : (n) => n.toFixed(2);
}

// Horizontal bars diverging from a zero center line — positive bars in the
// gain tone, negative in the loss tone. Reused for factor loadings (betas) and
// sector over/underweights: anything that's a signed, labelled magnitude.
export function DivergingBarChart({
  data,
  format,
  rowHeight = 28,
  positiveColor = CHART.gain,
  negativeColor = CHART.loss,
}: {
  data: DivergingDatum[];
  format: DivergingFormat;
  rowHeight?: number;
  positiveColor?: string;
  negativeColor?: string;
}) {
  if (!data || data.length === 0) return null;
  const formatValue = formatter(format);
  // Symmetric domain so the zero line sits centered and bar lengths compare.
  const bound = Math.max(...data.map((d) => Math.abs(d.value))) * 1.1 || 1;
  const height = data.length * rowHeight + 24;
  const labelWidth = Math.min(
    140,
    Math.max(48, ...data.map((d) => d.label.length * 6.5)),
  );

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 12, bottom: 0, left: 0 }}
        >
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" horizontal={false} />
          <XAxis
            type="number"
            domain={[-bound, bound]}
            tickFormatter={formatValue}
            tick={{ fill: CHART.inkMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={labelWidth}
            tick={{ fill: CHART.ink, fontSize: 11 }}
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
              maxWidth: 280,
            }}
            labelStyle={{ color: CHART.ink }}
            itemStyle={{ color: CHART.inkMuted, whiteSpace: "normal" }}
            formatter={(v: unknown, _n: unknown, item: unknown) => {
              const help = (item as { payload?: DivergingDatum })?.payload?.help;
              return [
                `${formatValue(Number(v))}${help ? ` — ${help}` : ""}`,
                "",
              ];
            }}
          />
          <ReferenceLine x={0} stroke={CHART.inkMuted} strokeOpacity={0.5} />
          <Bar dataKey="value" isAnimationActive={false} radius={2}>
            {data.map((d) => (
              <Cell
                key={d.label}
                fill={d.value >= 0 ? positiveColor : negativeColor}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
