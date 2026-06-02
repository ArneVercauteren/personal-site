import Link from "next/link";
import { isOpen, type Strategy, type StrategyMeta } from "@/lib/data";
import { pct, money } from "@/lib/format";
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

export function StrategyCard({
  strategy,
  meta,
}: {
  strategy: Strategy;
  meta?: StrategyMeta;
}) {
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
      />

      <StatsTable stats={strategy.stats} />

      <DrawdownChart points={strategy.equity_curve} />

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

      {isOpen(strategy) && strategy.formula_ref ? (
        <Link
          href={strategy.formula_ref}
          className="text-sm text-accent hover:underline"
        >
          View the formula →
        </Link>
      ) : null}
    </div>
  );
}
