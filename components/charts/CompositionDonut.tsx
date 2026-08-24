"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { pct } from "@/lib/format";
import { CHART, EXPOSURE_PALETTE } from "@/components/charts/chartColors";

export interface CompositionSlice {
  label: string;
  /** Fraction of the whole (0–1). */
  value: number;
}

/**
 * Presentational donut + legend for a set of weighted slices that sum to ~1.
 * Shared chart primitive behind the secured `ExposureDonut` and the open
 * sector-mix breakdown — keep the rendering here so both read identically.
 * Callers supply already-labelled slices (no tickers); this only draws them.
 */
export function CompositionDonut({
  slices,
  heading,
  footnote,
  size = 160,
}: {
  slices: CompositionSlice[];
  heading?: string;
  footnote?: string;
  size?: number;
}) {
  if (slices.length === 0) return null;
  const sorted = [...slices].sort((a, b) => b.value - a.value);

  return (
    <div>
      {heading ? (
        <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {heading}
        </h4>
      ) : null}
      <div className="flex items-center gap-5">
        <div style={{ width: size, height: size, flexShrink: 0 }}>
          <ResponsiveContainer
            minWidth={0}
            initialDimension={{ width: size, height: size }}
          >
            <PieChart>
              <Pie
                data={sorted}
                dataKey="value"
                nameKey="label"
                innerRadius="58%"
                outerRadius="100%"
                paddingAngle={1.5}
                stroke={CHART.panel}
                strokeWidth={2}
                isAnimationActive={false}
              >
                {sorted.map((slice, i) => (
                  <Cell
                    key={slice.label}
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
              key={slice.label}
              className="flex items-center justify-between gap-2 text-sm"
            >
              <span className="flex items-center gap-2 text-ink">
                <span
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{
                    background: EXPOSURE_PALETTE[i % EXPOSURE_PALETTE.length],
                  }}
                />
                {slice.label}
              </span>
              <span className="num text-ink-muted">{pct(slice.value)}</span>
            </li>
          ))}
        </ul>
      </div>

      {footnote ? <p className="mt-2 text-[11px] text-ink-muted">{footnote}</p> : null}
    </div>
  );
}
