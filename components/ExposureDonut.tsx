"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { ExposureSlice } from "@/lib/data";
import { pct } from "@/lib/format";
import { CHART, EXPOSURE_PALETTE } from "@/components/charts/chartColors";

// Aggregate sector / asset-class exposure for a secured strategy. Never renders
// tickers — only the grouped weights the contract allows (see
// docs/concepts/open-vs-secured-strategies.md).
export function ExposureDonut({
  exposure,
  size = 160,
}: {
  exposure: ExposureSlice[];
  size?: number;
}) {
  if (exposure.length === 0) return null;
  const sorted = [...exposure].sort((a, b) => b.weight - a.weight);

  return (
    <div>
      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        Sector exposure
      </h4>
      <div className="flex items-center gap-5">
        <div style={{ width: size, height: size, flexShrink: 0 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={sorted}
                dataKey="weight"
                nameKey="group"
                innerRadius="58%"
                outerRadius="100%"
                paddingAngle={1.5}
                stroke={CHART.panel}
                strokeWidth={2}
                isAnimationActive={false}
              >
                {sorted.map((slice, i) => (
                  <Cell
                    key={slice.group}
                    fill={EXPOSURE_PALETTE[i % EXPOSURE_PALETTE.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: CHART.panel,
                  border: `1px solid ${CHART.grid}`,
                  borderRadius: 6,
                  fontSize: 12,
                }}
                itemStyle={{ color: CHART.ink }}
                formatter={(v, name) => [pct(Number(v)), String(name)]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <ul className="flex flex-1 flex-col gap-1.5">
          {sorted.map((slice, i) => (
            <li
              key={slice.group}
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="flex items-center gap-2 text-ink">
                <span
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{
                    background: EXPOSURE_PALETTE[i % EXPOSURE_PALETTE.length],
                  }}
                />
                {slice.group}
              </span>
              <span className="num text-ink-muted">{pct(slice.weight)}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-2 text-[11px] text-ink-muted">
        Sector breakdown is approximate; unclassified holdings are grouped as “Other.”
      </p>
    </div>
  );
}
