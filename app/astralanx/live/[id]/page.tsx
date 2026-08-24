import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Disclaimer } from "@/components/Disclaimer";
import { ExposureDonut } from "@/components/ExposureDonut";
import { EquityExplorer } from "@/components/EquityExplorer";
import { type Regime } from "@/components/RegimeEquityChart";
import { FormulaView } from "@/components/FormulaView";
import { Section } from "@/components/Section";
import {
  loadSnapshotBenchmark,
  loadManifest,
  loadStrategyAnalytics,
  loadStrategyDetail,
  loadStrategyIndex,
  loadStrategyRebalances,
  isOpen,
  type LedgerEvent,
  type DetailedStats,
  type PerformanceRun,
  type StrategyMeta,
  type Stats,
} from "@/lib/data";
import { money, pct, signedPct, shortDate } from "@/lib/format";

export function generateStaticParams() {
  return loadStrategyIndex().strategies.map((s) => ({ id: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const s = loadStrategyIndex().strategies.find((x) => x.id === id);
  if (!s) return {};
  return {
    title: `${s.name} · strategy detail`,
    description: s.blurb,
    alternates: { canonical: `/astralanx/live/${s.id}` },
  };
}

// --- detailed stat rendering ----------------------------------------------

const num2 = (n: number) => n.toFixed(2);
type Tone = "gain" | "loss" | "neutral" | "signed";

const STAT_FIELDS: {
  key: keyof DetailedStats;
  label: string;
  fmt: (n: number) => string;
  tone: Tone;
}[] = [
  { key: "cagr", label: "CAGR", fmt: signedPct, tone: "signed" },
  { key: "total_return", label: "Total return", fmt: signedPct, tone: "signed" },
  { key: "volatility", label: "Volatility", fmt: (n) => pct(n), tone: "neutral" },
  { key: "sharpe", label: "Sharpe", fmt: num2, tone: "neutral" },
  { key: "sortino", label: "Sortino", fmt: num2, tone: "neutral" },
  { key: "calmar", label: "Calmar", fmt: num2, tone: "neutral" },
  { key: "max_dd", label: "Max DD", fmt: (n) => pct(n), tone: "loss" },
  { key: "max_dd_duration_days", label: "Max DD length", fmt: (n) => `${Math.round(n)}d`, tone: "neutral" },
  { key: "win_rate", label: "Win rate", fmt: (n) => pct(n, 0), tone: "neutral" },
  { key: "best_year", label: "Best year", fmt: signedPct, tone: "gain" },
  { key: "worst_year", label: "Worst year", fmt: signedPct, tone: "signed" },
  { key: "worst_rolling_3y_cagr", label: "Worst 3y CAGR", fmt: signedPct, tone: "signed" },
  { key: "worst_rolling_5y_cagr", label: "Worst 5y CAGR", fmt: signedPct, tone: "signed" },
  { key: "rolling_sharpe_min", label: "Min rolling Sharpe", fmt: num2, tone: "neutral" },
  { key: "benchmark_beta", label: "Beta vs S&P 500", fmt: num2, tone: "neutral" },
  { key: "benchmark_corr", label: "Corr vs S&P 500", fmt: num2, tone: "neutral" },
  { key: "alpha", label: "Alpha (ann.)", fmt: signedPct, tone: "signed" },
  { key: "information_ratio", label: "Information ratio", fmt: num2, tone: "neutral" },
];

function toneClass(tone: Tone, value: number): string {
  if (tone === "gain") return "text-gain";
  if (tone === "loss") return "text-loss";
  if (tone === "signed") return value >= 0 ? "text-gain" : "text-loss";
  return "text-ink";
}

// Renders every stat the run actually carries — a Stats (3 fields) or a full
// DetailedStats. Used for the live panel and each backtest run.
function DetailedStatsPanel({
  title,
  period,
  windows,
  stats,
  note,
}: {
  title: string;
  period?: string;
  windows?: { start: string; end: string; label?: string }[];
  stats: DetailedStats | Stats;
  note?: string;
}) {
  const s = stats as DetailedStats;
  const present = STAT_FIELDS.filter((f) => s[f.key] != null);
  return (
    <div className="panel p-6">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        {period ? <span className="num text-xs text-ink-muted">{period}</span> : null}
      </div>
      {windows && windows.length > 1 ? (
        <p className="mb-3 font-mono text-[10px] text-ink-muted">
          {windows
            .map((w) => w.label ?? `${shortDate(w.start)}–${shortDate(w.end)}`)
            .join(" · ")}
        </p>
      ) : null}
      {note ? <p className="mb-3 text-sm text-ink-muted">{note}</p> : null}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        {present.map((f) => {
          const v = s[f.key] as number;
          return (
            <div key={f.key} className="flex flex-col">
              <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                {f.label}
              </dt>
              <dd className={`num mt-0.5 text-base ${toneClass(f.tone, v)}`}>
                {f.fmt(v)}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function runPeriod(r: PerformanceRun): string {
  return `${shortDate(r.start)} – ${shortDate(r.end)}`;
}

function Facts({ meta }: { meta: StrategyMeta }) {
  const facts: { label: string; value: string }[] = [
    { label: "Starting Capital", value: money(meta.portfolio_size, meta.base_currency) },
    {
      label: "Rebalance",
      value: `${meta.rebalance_cadence_days} trading days`,
    },
    {
      label: "Costs",
      value: `${meta.cost_model.commission_bps}/${meta.cost_model.slippage_bps} bps`,
    },
    { label: "Live since", value: meta.deployed_on ? shortDate(meta.deployed_on) : "—" },
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-hair bg-hair sm:grid-cols-4">
      {facts.map((f) => (
        <div key={f.label} className="bg-panel px-5 py-4">
          <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            {f.label}
          </dt>
          <dd className="num mt-1 text-sm text-ink">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RebalanceTimeline({ events }: { events: LedgerEvent[] }) {
  const sessions = new Map<string, LedgerEvent[]>();
  for (const event of events) {
    sessions.set(event.session, [...(sessions.get(event.session) ?? []), event]);
  }
  const rows = [...sessions.entries()].sort(([left], [right]) => right.localeCompare(left));
  if (!rows.length) {
    return <p className="text-sm text-ink-muted">No live rebalance has occurred yet.</p>;
  }
  return (
    <ol className="space-y-3" aria-label="Audited rebalance events">
      {rows.map(([session, sessionEvents]) => {
        const target = sessionEvents.find((event) => event.event_type === "targets_computed");
        const fill = sessionEvents.find((event) => event.event_type === "fills_applied");
        const cost = sessionEvents.find((event) => event.event_type === "costs_charged");
        const reviewed = sessionEvents.find((event) => event.event_type === "rebalance_reviewed");
        const weights = target?.payload.weights as Record<string, number> | undefined;
        const trades = fill?.payload.trades as unknown[] | undefined;
        const costAmount = typeof cost?.payload.amount === "number" ? cost.payload.amount : null;
        return (
          <li key={session} className="panel p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="num text-sm text-ink">{shortDate(session)}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                {sessionEvents.map((event) => event.event_type.replaceAll("_", " ")).join(" · ")}
              </span>
            </div>
            <p className="mt-2 text-xs text-ink-muted">
              {weights ? `${Object.keys(weights).length} targets` : "Review recorded"}
              {trades ? ` · ${trades.length} fills` : ""}
              {costAmount != null ? ` · ${money(costAmount, "USD")} estimated costs` : ""}
            </p>
            {reviewed ? (
              <p className="mt-1 break-all font-mono text-[10px] text-ink-faint">
                universe {String(reviewed.payload.universe_snapshot_id).slice(0, 12)} · prices{" "}
                {String(reviewed.payload.price_snapshot_id).slice(0, 12)}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export default async function StrategyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const summary = loadStrategyIndex().strategies.find((s) => s.id === id);
  if (!summary) notFound();
  const detail = loadStrategyDetail(id);
  const strategy = detail.strategy;
  const sp500 = loadSnapshotBenchmark();
  const analytics = loadStrategyAnalytics(id);
  const rebalanceEvents = loadStrategyRebalances(id);
  const meta: StrategyMeta = { ...detail.meta, ...analytics };
  const manifest = loadManifest();
  const liveSince = strategy.live_since ?? meta?.deployed_on;
  const firstD = strategy.equity_curve[0]?.d;
  const lastD = strategy.equity_curve.at(-1)?.d;
  // Real live data exists only once the curve reaches the live date — a strategy
  // deployed today has none yet, so its live stats are "accruing", not 0%.
  const hasLiveData = Boolean(liveSince && lastD && lastD >= liveSince);
  const perf = meta?.performance;

  // Lifecycle chart bands: the in-sample training regime(s), the held-out
  // out-of-sample window, and the live tail — each shaded distinctly behind the
  // curve. A strategy with no training/OOS provenance falls back to shading all
  // pre-live history as a single out-of-sample band.
  // The last curve point strictly before the live date — the boundary the live
  // regime starts at, and where pre-live (out-of-sample) history ends.
  const preLiveEnd = liveSince
    ? [...strategy.equity_curve].reverse().find((p) => p.d < liveSince)?.d
    : lastD;
  const regimes: Regime[] = [];
  if (perf) {
    const trainingWindows = perf.training.windows ?? [
      { start: perf.training.start, end: perf.training.end },
    ];
    for (const w of trainingWindows) {
      regimes.push({ start: w.start, end: w.end, kind: "training", label: w.label });
    }
    // The OOS *backtest run* (perf.oos) ends at Darwin's held-out window end,
    // but the equity curve continues past it with Yahoo-filled simulation right
    // up to the live date. That in-between stretch is still out-of-sample — the
    // frozen formula on prices it was never fit on — so for the lifecycle bands
    // and the OOS viewer we extend the OOS regime to the last pre-live point.
    // (The Backtest stats panel below still reports perf.oos's own window.)
    const oosBandEnd =
      preLiveEnd && preLiveEnd > perf.oos.end ? preLiveEnd : perf.oos.end;
    regimes.push({
      start: perf.oos.start,
      end: oosBandEnd,
      kind: "oos",
      label: "OOS",
    });
  } else if (firstD && preLiveEnd && firstD <= preLiveEnd) {
    regimes.push({ start: firstD, end: preLiveEnd, kind: "oos", label: "OOS" });
  }
  if (liveSince && lastD) {
    regimes.push({ start: liveSince, end: lastD, kind: "live", label: "Live" });
  }

  const cap = meta?.capacity;
  const hasLiquidity =
    meta?.active_share != null || cap?.liquidity_usd != null || cap?.impact_usd != null;
  // Whether the published curve was capped at capacity (compound-then-cap model).
  const impactBookCap = meta?.cost_model?.impact_book_cap;
  const displayedCapacity = impactBookCap ?? cap?.impact_usd ?? cap?.liquidity_usd;
  const investedWeight = isOpen(strategy)
    ? strategy.positions.reduce((sum, p) => sum + p.weight, 0)
    : null;
  const cashWeight =
    investedWeight == null ? null : Math.max(0, 1 - investedWeight);

  // Show the deep-analytics CTA only when some run actually carries the rich
  // open_diagnostics block (open strategies exported from Astralanx).
  const hasAnalytics = perf
    ? [perf.combined, perf.oos, perf.training].some((r) => r?.open_diagnostics)
    : false;

  return (
    <div>
      <p className="mb-4">
        <Link href="/astralanx/live" className="font-mono text-xs text-accent hover:underline">
          ← Back to dashboard
        </Link>
      </p>

      <PageHeader
        eyebrow={isOpen(strategy) ? "Open · formula shown" : "Secured · positions private"}
        title={strategy.name}
        intro={meta?.blurb}
      />

      <div className="mt-6">
        <Disclaimer />
      </div>

      <div className="mt-6">
        <Facts meta={meta ?? defaultMeta(strategy.id, strategy.name)} />
      </div>

      {meta.thesis || meta.expected_behavior || meta.risks?.length || meta.failure_modes?.length ? (
        <Section eyebrow="Plain English" title="Thesis, behaviour & risks">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-4 text-sm text-ink-muted">
              {meta.thesis ? <p><strong className="text-ink">Thesis.</strong> {meta.thesis}</p> : null}
              {meta.expected_behavior ? (
                <p><strong className="text-ink">Expected behaviour.</strong> {meta.expected_behavior}</p>
              ) : null}
            </div>
            <div className="space-y-4">
              {meta.risks?.length ? (
                <div>
                  <h3 className="text-sm font-semibold text-ink">Risks</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
                    {meta.risks.map((risk) => <li key={risk}>{risk}</li>)}
                  </ul>
                </div>
              ) : null}
              {meta.failure_modes?.length ? (
                <div>
                  <h3 className="text-sm font-semibold text-ink">What failure looks like</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
                    {meta.failure_modes.map((failure) => <li key={failure}>{failure}</li>)}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        </Section>
      ) : null}

      {hasAnalytics ? (
        <Link
          href={`/astralanx/live/${strategy.id}/analytics`}
          className="panel panel-hover mt-6 flex items-center justify-between gap-4 px-5 py-4"
        >
          <span>
            <span className="block text-sm font-semibold text-ink">
              Deep analytics →
            </span>
            <span className="mt-0.5 block text-xs text-ink-muted">
              Annual returns, rolling Sharpe, drawdown anatomy, factor &amp;
              sector exposure, capacity, and the full rebalance history.
            </span>
          </span>
          <span aria-hidden className="font-mono text-lg text-accent">
            →
          </span>
        </Link>
      ) : null}

      <Section eyebrow="Lifecycle" title="Training → out-of-sample → live">
        <h3 className="mb-2 text-base font-semibold text-ink">
          {impactBookCap ? "Capacity-capped account equity" : "Account equity"}
        </h3>
        <p className="mb-4 max-w-prose text-sm text-ink-muted">
          The line is total simulated account value, shaded by phase: the in-sample{" "}
          <span className="text-ink">training</span> window(s) it was fit on, the
          held-out <span className="text-ink">out-of-sample</span> window, and{" "}
          <span className="text-ink">live</span> paper-trading after the marker.
          Per-phase stats are in the panels below.
        </p>
        <EquityExplorer
          points={strategy.equity_curve}
          segmentCurves={{
            training: perf?.training.equity_curve,
            oos: perf?.oos.equity_curve,
          }}
          regimes={regimes}
          benchmark={sp500}
          currency={meta?.base_currency ?? "USD"}
          liveSince={liveSince}
        />
        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          <a
            className="text-accent hover:underline"
            href={`/data/snapshots/${manifest.snapshot_id}/strategies/${strategy.id}/live.json`}
            download
          >
            Download live data
          </a>
          <a
            className="text-accent hover:underline"
            href={`/data/snapshots/${manifest.snapshot_id}/strategies/${strategy.id}/research-full.json`}
            download
          >
            Download full-resolution research data
          </a>
        </div>
        {impactBookCap ? (
          <p className="mt-2 max-w-prose text-xs text-ink-muted">
            Full history is a continuous account: above the estimated capacity (
            {money(impactBookCap, meta?.base_currency ?? "USD")}), unsupported capital
            remains cash. Training and out-of-sample presets use their standalone
            replay curves so they match the statistics shown below.
          </p>
        ) : null}
      </Section>

      {strategy.stats_live ? (
        <Section eyebrow="Live" title="Forward paper-trading">
          {hasLiveData ? (
            <DetailedStatsPanel
              title="Live (paper)"
              period={liveSince ? `since ${shortDate(liveSince)}` : undefined}
              stats={strategy.stats_live}
              note="Real forward tracking since the live date using the Yahoo Finance API, and the same cost model as the backtests."
            />
          ) : (
            <div className="panel p-6">
              <h3 className="text-base font-semibold text-ink">Live (paper)</h3>
              <p className="mt-1 text-sm text-ink-muted">
                Accruing — forward paper-trading begins{" "}
                {liveSince ? shortDate(liveSince) : "at the live date"}. Live stats
                appear once a few trading days have passed; everything above is
                out-of-sample backtest history.
              </p>
            </div>
          )}
        </Section>
      ) : null}

      {perf ? (
        <Section eyebrow="Backtest" title="Training, out-of-sample & combined">
          <p className="mb-4 max-w-prose text-sm text-ink-muted">
            Three deterministic single-seed runs of the frozen formula: the
            in-sample <strong>training</strong> window, the held-out{" "}
            <strong>out-of-sample</strong> window, and the two{" "}
            <strong>combined</strong>. Combined figures are computed end to end,
            not stitched from the halves.
          </p>
          <div className="flex flex-col gap-4">
            <DetailedStatsPanel
              title="Out-of-sample"
              period={runPeriod(perf.oos)}
              windows={perf.oos.windows}
              stats={perf.oos.stats}
              note="Never used to train the strategy, the strongest evidence short of live tracking."
            />
            <DetailedStatsPanel
              title="Training (in-sample)"
              period={runPeriod(perf.training)}
              windows={perf.training.windows}
              stats={perf.training.stats}
              note="The strategy was trained on this period, good returns here are not inherently indicative of quality or future performance."
            />
            <DetailedStatsPanel
              title="Combined · training + OOS"
              period={runPeriod(perf.combined)}
              windows={perf.combined.windows}
              stats={perf.combined.stats}
              note="Combined figures are computed end to end, not stitched from the halves."
            />
          </div>
        </Section>
      ) : null}

      {hasLiquidity ? (
        <Section eyebrow="Capacity" title="Capacity & holdings">
          <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-hair bg-hair sm:grid-cols-3">
            {meta?.active_share != null ? (
              <Cell label="Active share" value={pct(meta.active_share)} />
            ) : null}
            {displayedCapacity != null ? (
              <Cell label="Capacity" value={money(displayedCapacity)} />
            ) : null}
          </dl>
        </Section>
      ) : null}

      {isOpen(strategy) && strategy.formula ? (
        <Section eyebrow="Formula" title="How it picks stocks" id="formula">
          <FormulaView
            formula={strategy.formula}
            rebalanceDays={meta?.rebalance_cadence_days}
          />
        </Section>
      ) : null}

      <Section eyebrow="Audit trail" title="Rebalance timeline">
        <p className="mb-4 max-w-prose text-sm text-ink-muted">
          Append-only review, target, next-open fill, and cost events. Short hashes identify
          the point-in-time universe and price inputs used for each decision. Due to the fact that this was the first strategy, the first few review dates do not match the intended strategy cadence.
        </p>
        <RebalanceTimeline events={rebalanceEvents} />
      </Section>

      <Section
        eyebrow={isOpen(strategy) ? "Composition" : "Exposure"}
        title={isOpen(strategy) ? "Current allocation" : "Aggregate sector exposure"}
      >
        {isOpen(strategy) ? (
          <>
            {investedWeight != null && cashWeight != null ? (
              <p className="mb-4 max-w-prose text-sm text-ink-muted">
                Current account allocation:{" "}
                <span className="num text-ink">{pct(investedWeight)}</span>{" "}
                invested, <span className="num text-ink">{pct(cashWeight)}</span>{" "}
                cash / uninvested.
              </p>
            ) : null}
            <ul className="grid grid-cols-2 gap-x-8 gap-y-1 sm:grid-cols-3">
              {[...strategy.positions]
                .sort((a, b) => b.weight - a.weight)
                .map((p) => (
                  <li key={p.ticker} className="flex items-center justify-between text-sm">
                    <span className="num text-ink">{p.ticker}</span>
                    <span className="num text-ink-muted">{pct(p.weight)}</span>
                  </li>
                ))}
              {cashWeight != null && cashWeight > 0.0005 ? (
                <li className="flex items-center justify-between border-t border-hair pt-1 text-sm sm:col-span-3">
                  <span className="text-ink">Cash / uninvested</span>
                  <span className="num text-ink-muted">{pct(cashWeight)}</span>
                </li>
              ) : null}
            </ul>
            <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1">
              {strategy.formula ? (
                <Link href="#formula" className="text-sm text-accent hover:underline">
                  See the full formula ↑
                </Link>
              ) : null}
              {strategy.formula_ref ? (
                <Link
                  href={strategy.formula_ref}
                  className="text-sm text-accent hover:underline"
                >
                  Read the writeup →
                </Link>
              ) : null}
            </div>
          </>
        ) : (
          <ExposureDonut exposure={strategy.exposure} />
        )}
      </Section>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-panel px-5 py-4">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {label}
      </dt>
      <dd className="num mt-1 text-lg text-ink">{value}</dd>
    </div>
  );
}

// Fallback facts when no meta entry exists (shouldn't happen for published
// strategies, but keeps the page resilient).
function defaultMeta(id: string, name: string): StrategyMeta {
  return {
    id,
    name,
    visibility: "open",
    portfolio_size: 0,
    base_currency: "USD",
    rebalance_cadence_days: 0,
    deployed_on: "",
    cost_model: { commission_bps: 0, slippage_bps: 0 },
    blurb: "",
  };
}
