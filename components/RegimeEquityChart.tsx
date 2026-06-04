"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/data";
import { axisDate, compactMoney, money, shortDate, spanDays } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

export type RegimeKind = "training" | "oos" | "live";

export interface Regime {
  start: string;
  end: string;
  kind: RegimeKind;
  label?: string;
}

const REGIME_STYLE: Record<RegimeKind, { color: string; name: string }> = {
  training: { color: CHART.inkMuted, name: "Training (in-sample)" },
  oos: { color: CHART.accent, name: "Out-of-sample" },
  live: { color: CHART.gain, name: "Live (paper)" },
};

// Continuous equity curve with lifecycle bands behind it. On the strategy
// detail page, everything before the live marker is shaded as out-of-sample
// backtest history and everything after it as live paper history. The line is
// one tone; the regimes are translucent bands so the whole history reads as one
// curve. Boundaries snap to the nearest curve date.
export function RegimeEquityChart({
  points,
  regimes,
  currency = "USD",
  liveSince,
  height = 260,
}: {
  points: EquityPoint[];
  regimes: Regime[];
  currency?: string;
  liveSince?: string;
  height?: number;
}) {
  if (points.length < 2) return null;

  const dates = points.map((p) => p.d);
  const first = dates[0];
  const last = dates[dates.length - 1];
  // Snap a [start,end] window onto the curve's category axis. ReferenceArea
  // needs both bounds to be values present in the data, so we clamp+snap.
  const snap = (start: string, end: string): [string, string] | null => {
    const lo = start < first ? first : start;
    const hi = end > last ? last : end;
    if (lo > last || hi < first || lo > hi) return null;
    const x1 = dates.find((d) => d >= lo) ?? null;
    let x2: string | null = null;
    for (let i = dates.length - 1; i >= 0; i--) {
      if (dates[i] <= hi) {
        x2 = dates[i];
        break;
      }
    }
    return x1 && x2 && x1 <= x2 ? [x1, x2] : null;
  };

  const bands = regimes
    .map((r) => ({ regime: r, span: snap(r.start, r.end) }))
    .filter((b): b is { regime: Regime; span: [string, string] } => b.span !== null);

  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || max * 0.02;
  // Compact y labels (e.g. "$147M") once values run into the millions, where a
  // full "$146,638,651" would overflow the axis; full money below that.
  const fmtY = (v: number) => (max >= 1_000_000 ? compactMoney(v, currency) : money(v, currency));
  const span = spanDays(first, last);
  const up = points[points.length - 1].v >= points[0].v;
  const stroke = up ? CHART.gain : CHART.loss;

  const markerD = liveSince
    ? (dates.find((d) => d >= liveSince) ?? null)
    : null;

  // Which regime kinds actually rendered — drives the legend.
  const shownKinds = Array.from(new Set(bands.map((b) => b.regime.kind)));

  return (
    <div>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="regime-equity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.18} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            {bands.map((b, i) => (
              <ReferenceArea
                key={`${b.regime.kind}-${i}`}
                x1={b.span[0]}
                x2={b.span[1]}
                y1={min - pad}
                y2={max + pad}
                fill={REGIME_STYLE[b.regime.kind].color}
                fillOpacity={0.1}
                stroke="none"
                ifOverflow="hidden"
              />
            ))}
            <XAxis
              dataKey="d"
              tickFormatter={(d: string) => axisDate(d, span)}
              tick={{ fill: CHART.inkMuted, fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: CHART.grid }}
              minTickGap={36}
            />
            <YAxis
              width={56}
              domain={[min - pad, max + pad]}
              tickFormatter={fmtY}
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
            {markerD ? (
              <ReferenceLine
                x={markerD}
                stroke={CHART.accent}
                strokeDasharray="3 3"
                label={{
                  value: "Live",
                  position: "insideTopRight",
                  fill: CHART.accent,
                  fontSize: 10,
                }}
              />
            ) : null}
            <Area
              type="monotone"
              dataKey="v"
              stroke={stroke}
              strokeWidth={1.5}
              fill="url(#regime-equity)"
              dot={false}
              activeDot={{ r: 3, fill: stroke }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      {shownKinds.length > 0 ? (
        <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] text-ink-muted">
          {shownKinds.map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: REGIME_STYLE[k].color, opacity: 0.5 }}
              />
              {REGIME_STYLE[k].name}
            </span>
          ))}
        </p>
      ) : null}
    </div>
  );
}
