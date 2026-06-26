import Link from "next/link";
import { type Benchmark, type Strategy, type StrategyMeta } from "@/lib/data";
import { money, shortDate } from "@/lib/format";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { StatsTable } from "@/components/StatsTable";

function Badge({ visibility }: { visibility: Strategy["visibility"] }) {
  if (visibility === "open") {
    return (
      <span className="rounded border border-gain/40 bg-gain/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-gain">
        Open · formula shown
      </span>
    );
  }
  return (
    <span className="rounded border border-hair bg-elevated px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
      Live paper · positions private
    </span>
  );
}

// Minimum live trading days before the live stats are worth showing; below
// this the segment is too short for a meaningful CAGR/Sharpe.
const MIN_LIVE_POINTS = 10;

// A compact dashboard card: the equity curve plus headline stats and a few
// facts — just enough to scan. The full breakdown (drawdown, basket, formula,
// backtest runs) and the deep analytics live on the linked detail pages.
export function StrategyCard({
  strategy,
  meta,
  benchmark,
}: {
  strategy: Strategy;
  meta?: StrategyMeta;
  benchmark?: Benchmark;
}) {
  const liveSince = strategy.live_since ?? meta?.deployed_on;
  const liveCount = liveSince
    ? strategy.equity_curve.filter((p) => p.d >= liveSince).length
    : 0;
  const liveReady = liveCount >= MIN_LIVE_POINTS;
  // Headline = live stats once there's enough live history, else the backtest
  // segment, else the full-curve stats.
  const headline = liveReady
    ? strategy.stats_live
    : strategy.stats_backtest ?? strategy.stats;
  const headlineLabel = liveReady
    ? `Live · since ${shortDate(liveSince!)}`
    : strategy.stats_backtest
      ? "Backtest · out-of-sample"
      : "Performance";
  const isCapacityCapped = Boolean(meta?.cost_model?.impact_book_cap);

  return (
    <article className="panel flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-ink">{strategy.name}</h3>
          {meta?.blurb ? (
            <p className="mt-1 text-sm text-ink-muted">{meta.blurb}</p>
          ) : null}
        </div>
        <Badge visibility={strategy.visibility} />
      </div>

      <div>
        <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {isCapacityCapped ? "Capacity-capped account equity" : "Account equity"}
        </h4>
        <EquityCurveChart
          points={strategy.equity_curve}
          benchmark={benchmark}
          currency={meta?.base_currency ?? "USD"}
          liveSince={liveSince}
        />
        {isCapacityCapped ? (
          <p className="mt-1 text-[11px] text-ink-muted">
            Excess account value above the capacity estimate remains in cash.
          </p>
        ) : null}
      </div>

      <div>
        <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {headlineLabel}
        </h4>
        <StatsTable stats={headline ?? strategy.stats} />
      </div>

      {meta ? (
        <dl className="grid grid-cols-3 gap-3 border-t border-hair pt-4 text-xs">
          <div>
            <dt className="text-ink-muted">Starting Capital</dt>
            <dd className="num text-ink">
              {money(meta.portfolio_size, meta.base_currency)}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Rebalance</dt>
            <dd className="num text-ink">{meta.rebalance_cadence_days}d</dd>
          </div>
          <div>
            <dt className="text-ink-muted">Costs</dt>
            <dd className="num text-ink">
              {meta.cost_model.commission_bps}/{meta.cost_model.slippage_bps} bps
            </dd>
          </div>
        </dl>
      ) : null}

      <Link
        href={`/astralanx/live/${strategy.id}`}
        className="mt-auto border-t border-hair pt-4 text-sm font-semibold text-accent hover:underline"
      >
        Full breakdown →
      </Link>
    </article>
  );
}
