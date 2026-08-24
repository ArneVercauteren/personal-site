import Link from "next/link";
import { type Benchmark, type StrategySummary, type Visibility } from "@/lib/data";
import { money, pct, shortDate, signedPct } from "@/lib/format";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { StatsTable } from "@/components/StatsTable";

function Badge({ visibility }: { visibility: Visibility }) {
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
  summary,
  benchmark,
}: {
  summary: StrategySummary;
  benchmark?: Benchmark;
}) {
  const liveSince = summary.live_since ?? summary.deployed_on;
  const liveReady = summary.live_observations >= MIN_LIVE_POINTS;
  const isCapacityCapped = Boolean(summary.cost_model?.impact_book_cap);
  const start = summary.live_curve[0]?.v ?? 1;
  const normalized = summary.live_curve.map((point) => ({
    d: point.d,
    v: start > 0 ? (point.v / start) * 100 : 100,
  }));
  const benchmarkWindow = benchmark?.equity_curve.filter(
    (point) => !liveSince || point.d >= liveSince,
  );
  const benchmarkReturn = benchmarkWindow && benchmarkWindow.length > 1
    ? benchmarkWindow.at(-1)!.v / benchmarkWindow[0].v - 1
    : null;
  const relativeReturn = benchmarkReturn == null
    ? null
    : summary.live_total_return - benchmarkReturn;
  const cashWeight = summary.invested_weight == null
    ? null
    : Math.max(0, 1 - summary.invested_weight);

  return (
    <article className="panel flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-ink">{summary.name}</h3>
          {summary.blurb ? (
            <p className="mt-1 text-sm text-ink-muted">{summary.blurb}</p>
          ) : null}
        </div>
        <Badge visibility={summary.visibility} />
      </div>

      <div>
        <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          Live performance · start = 100
        </h4>
        <EquityCurveChart
          points={normalized}
          benchmark={benchmark}
          currency={summary.base_currency ?? "USD"}
          normalized
        />
        {isCapacityCapped ? (
          <p className="mt-1 text-[11px] text-ink-muted">
            Excess account value above the capacity estimate remains in cash.
          </p>
        ) : null}
      </div>

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border border-hair bg-hair sm:grid-cols-4">
        <Metric label="Live return" value={signedPct(summary.live_total_return)} tone={summary.live_total_return} />
        <Metric label="Vs S&P 500" value={relativeReturn == null ? "—" : signedPct(relativeReturn)} tone={relativeReturn} />
        <Metric label="Current DD" value={pct(summary.current_drawdown)} tone={summary.current_drawdown} />
        <Metric label="Live sessions" value={String(summary.live_observations)} />
      </dl>

      {liveReady && summary.stats_live ? (
        <div>
          <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            Risk statistics · since {liveSince ? shortDate(liveSince) : "deployment"}
          </h4>
          <StatsTable stats={summary.stats_live} />
        </div>
      ) : null}

      {summary.portfolio_size != null ? (
        <dl className="grid grid-cols-3 gap-3 border-t border-hair pt-4 text-xs">
          <div>
            <dt className="text-ink-muted">Starting Capital</dt>
            <dd className="num text-ink">
              {money(summary.portfolio_size, summary.base_currency)}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Rebalance</dt>
            <dd className="num text-ink">
              {summary.rebalance_cadence_days} {summary.rebalance_cadence_unit === "trading_days" ? "sessions" : "calendar days"}
            </dd>
          </div>
          <div>
            <dt className="text-ink-muted">Costs</dt>
            <dd className="num text-ink">
              {summary.cost_model?.commission_bps}/{summary.cost_model?.slippage_bps} bps
            </dd>
          </div>
        </dl>
      ) : null}

      <p className="text-xs text-ink-muted">
        {summary.last_review_date ? <>Last review {shortDate(summary.last_review_date)} · </> : null}
        {summary.last_fill_date ? <>last fill {shortDate(summary.last_fill_date)} · </> : null}
        {summary.sessions_until_review != null
          ? `${summary.sessions_until_review} trading sessions to next review`
          : "next review follows the published cadence"}
        {cashWeight != null ? ` · ${pct(cashWeight)} cash` : ""}
      </p>

      <Link
        href={`/astralanx/live/${summary.id}`}
        className="mt-auto border-t border-hair pt-4 text-sm font-semibold text-accent hover:underline"
      >
        Full breakdown →
      </Link>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: number | null }) {
  const color = tone == null ? "text-ink" : tone >= 0 ? "text-gain" : "text-loss";
  return (
    <div className="bg-panel px-3 py-3">
      <dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">{label}</dt>
      <dd className={`num mt-1 text-sm ${color}`}>{value}</dd>
    </div>
  );
}
