"use client";

import { useState } from "react";
import type { PickRecord } from "@/lib/data";
import { dateOnly, pct, shortDate } from "@/lib/format";
import { CHART } from "@/components/charts/chartColors";

// A "time machine" over the rebalance history: pick a date on the left, see
// that rebalance's basket (names + target weights) on the right. The basket is
// drawn as weight bars so the concentration is legible at a glance.
export function PicksHistory({ records }: { records: PickRecord[] }) {
  // Most recent first — the latest basket is the most interesting default.
  const sorted = [...records].sort((a, b) => b.date.localeCompare(a.date));
  const [active, setActive] = useState(0);
  if (sorted.length === 0) return null;

  const rec = sorted[active];
  const basket = Object.entries(rec.weights).sort((a, b) => b[1] - a[1]);
  const maxW = basket.length ? basket[0][1] : 1;

  return (
    <div className="grid gap-4 sm:grid-cols-[200px_1fr]">
      <div className="max-h-[420px] overflow-y-auto rounded-lg border border-hair">
        <ul>
          {sorted.map((r, i) => (
            <li key={`${r.date}-${i}`}>
              <button
                type="button"
                onClick={() => setActive(i)}
                aria-pressed={i === active}
                className={
                  "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs transition-colors " +
                  (i === active
                    ? "bg-accent/15 text-accent"
                    : "text-ink-muted hover:bg-elevated hover:text-ink")
                }
              >
                <span className="num">{shortDate(dateOnly(r.date))}</span>
                <span className="num text-[10px] opacity-70">{r.count}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h4 className="text-sm font-semibold text-ink">
            Basket · {shortDate(dateOnly(rec.date))}
          </h4>
          <span className="num text-xs text-ink-muted">{rec.count} names</span>
        </div>
        <ul className="flex flex-col gap-1.5">
          {basket.map(([ticker, weight]) => (
            <li key={ticker} className="flex items-center gap-3 text-sm">
              <span className="num w-16 shrink-0 text-ink">{ticker}</span>
              <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-elevated">
                <span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{
                    width: `${(weight / maxW) * 100}%`,
                    background: CHART.accent,
                  }}
                />
              </span>
              <span className="num w-14 shrink-0 text-right text-ink-muted">
                {pct(weight)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
