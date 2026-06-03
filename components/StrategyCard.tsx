import Link from "next/link";
import { isOpen, type Strategy, type StrategyMeta } from "@/lib/data";
import { pct, money, shortDate } from "@/lib/format";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { ExposureDonut } from "@/components/ExposureDonut";
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

function PositionsTable({
  positions,
}: {
  positions: { ticker: string; weight: number }[];
}) {
  const sorted = [...positions].sort((a, b) => b.weight - a.weight);
  return (
    <div>
      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        Positions
      </h4>
      <ul className="flex flex-col gap-1">
        {sorted.map((p) => (
          <li
            key={p.ticker}
            className="flex items-center justify-between text-sm"
          >
            <span className="num text-ink">{p.ticker}</span>
            <span className="num text-ink-muted">{pct(p.weight)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Minimum live trading days before the live stats are worth showing; below
// this the segment is too short for a meaningful CAGR/Sharpe.
const MIN_LIVE_POINTS = 10;

function StatBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {label}
      </h4>
      {children}
    </div>
  );
}

export function StrategyCard({
  strategy,
  meta,
}: {
  strategy: Strategy;
  meta?: StrategyMeta;
}) {
  const liveSince = strategy.live_since ?? meta?.deployed_on;
  const liveCount = liveSince
    ? strategy.equity_curve.filter((p) => p.d >= liveSince).length
    : 0;
  const livePending = liveCount < MIN_LIVE_POINTS;
  // Show the split only when the writer provided both segments and a boundary.
  const showSplit = Boolean(
    liveSince && strategy.stats_backtest && strategy.stats_live,
  );

  return (
    <div className="panel flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-ink">{strategy.name}</h3>
          {meta ? (
            <p className="mt-1 text-sm text-ink-muted">{meta.blurb}</p>
          ) : null}
        </div>
        <Badge visibility={strategy.visibility} />
      </div>

      <EquityCurveChart
        points={strategy.equity_curve}
        currency={meta?.base_currency ?? "USD"}
        liveSince={liveSince}
      />

      {showSplit ? (
        <div className="flex flex-col gap-4">
          <StatBlock
            label={
              liveSince && !livePending
                ? `Live · since ${shortDate(liveSince)}`
                : "Live"
            }
          >
            {livePending ? (
              <p className="text-sm text-ink-muted">
                Accruing{liveSince ? ` since ${shortDate(liveSince)}` : ""} —
                live stats appear once enough trading days pass.
              </p>
            ) : (
              <StatsTable stats={strategy.stats_live!} />
            )}
          </StatBlock>
          <StatBlock label="Backtest · out-of-sample">
            <StatsTable stats={strategy.stats_backtest!} />
          </StatBlock>
        </div>
      ) : (
        <StatsTable stats={strategy.stats} />
      )}

      <DrawdownChart points={strategy.equity_curve} liveSince={liveSince} />

      {isOpen(strategy) ? (
        <PositionsTable positions={strategy.positions} />
      ) : (
        <ExposureDonut exposure={strategy.exposure} />
      )}

      {meta ? (
        <dl className="grid grid-cols-3 gap-3 border-t border-hair pt-4 text-xs">
          <div>
            <dt className="text-ink-muted">Capital</dt>
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

      <div className="flex items-center justify-between border-t border-hair pt-4">
        <Link
          href={`/astralanx/live/${strategy.id}`}
          className="text-sm font-semibold text-accent hover:underline"
        >
          Full breakdown →
        </Link>
        {isOpen(strategy) && strategy.formula_ref ? (
          <Link
            href={strategy.formula_ref}
            className="text-sm text-ink-muted hover:text-ink"
          >
            View the formula →
          </Link>
        ) : null}
      </div>
    </div>
  );
}
