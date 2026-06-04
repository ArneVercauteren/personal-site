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
  loadPortfolio,
  loadStrategyMeta,
  isOpen,
  type DetailedStats,
  type PerformanceRun,
  type StrategyMeta,
  type Stats,
} from "@/lib/data";
import { money, pct, signedPct, shortDate } from "@/lib/format";

export function generateStaticParams() {
  return loadPortfolio().strategies.map((s) => ({ id: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const s = loadPortfolio().strategies.find((x) => x.id === id);
  if (!s) return {};
  return { title: `${s.name} · strategy detail` };
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
    { label: "Capital", value: money(meta.portfolio_size, meta.base_currency) },
    { label: "Rebalance", value: `${meta.rebalance_cadence_days}d` },
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

export default async function StrategyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const strategy = loadPortfolio().strategies.find((s) => s.id === id);
  if (!strategy) notFound();

  const meta = loadStrategyMeta().strategies.find((m) => m.id === id);
  const liveSince = strategy.live_since ?? meta?.deployed_on;
  const firstD = strategy.equity_curve[0]?.d;
  const lastD = strategy.equity_curve.at(-1)?.d;
  const perf = meta?.performance;

  // Lifecycle chart bands: everything before the live date is displayed as
  // out-of-sample/backtest evidence. The original Darwin training/OOS split is
  // still shown in the detailed stat panels below.
  const regimes: Regime[] = [];
  const firstLiveD = liveSince
    ? strategy.equity_curve.find((p) => p.d >= liveSince)?.d
    : undefined;
  const preLiveEnd = liveSince
    ? [...strategy.equity_curve].reverse().find((p) => p.d < liveSince)?.d
    : lastD;
  if (firstD && preLiveEnd && firstD <= preLiveEnd) {
    regimes.push({ start: firstD, end: preLiveEnd, kind: "oos", label: "OOS" });
  }
  if (firstLiveD && lastD) {
    regimes.push({ start: firstLiveD, end: lastD, kind: "live", label: "Live" });
  }

  const cap = meta?.capacity;
  const hasLiquidity =
    meta?.active_share != null || cap?.liquidity_usd != null || cap?.impact_usd != null;

  // Show the deep-analytics CTA only when some run actually carries the rich
  // open_diagnostics block (open strategies exported from Darwin).
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

      <Section eyebrow="Lifecycle" title="Out-of-sample → live">
        <p className="mb-4 max-w-prose text-sm text-ink-muted">
          Everything before the live marker is grouped as out-of-sample backtest
          history on this chart; the Darwin training/OOS breakdown remains in
          the stat panels below.
        </p>
        <EquityExplorer
          points={strategy.equity_curve}
          regimes={regimes}
          currency={meta?.base_currency ?? "USD"}
          liveSince={liveSince}
        />
      </Section>

      {strategy.stats_live ? (
        <Section eyebrow="Live" title="Forward paper-trading">
          <DetailedStatsPanel
            title="Live (paper)"
            period={liveSince ? `since ${shortDate(liveSince)}` : undefined}
            stats={strategy.stats_live}
            note="Real forward tracking since the live date — the only segment with no benefit of hindsight."
          />
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
              note="Never fit on — the strongest evidence short of live tracking."
            />
            <DetailedStatsPanel
              title="Training (in-sample)"
              period={runPeriod(perf.training)}
              windows={perf.training.windows}
              stats={perf.training.stats}
              note="The years the formula was fit on. In-sample by definition — context, not evidence."
            />
            <DetailedStatsPanel
              title="Combined · training + OOS"
              period={runPeriod(perf.combined)}
              windows={perf.combined.windows}
              stats={perf.combined.stats}
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
            {cap?.liquidity_usd != null ? (
              <Cell label="Capacity · liquidity" value={money(cap.liquidity_usd)} />
            ) : null}
            {cap?.impact_usd != null ? (
              <Cell label="Capacity · impact" value={money(cap.impact_usd)} />
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

      <Section
        eyebrow={isOpen(strategy) ? "Composition" : "Exposure"}
        title={isOpen(strategy) ? "Current basket" : "Aggregate sector exposure"}
      >
        {isOpen(strategy) ? (
          <>
            <ul className="grid grid-cols-2 gap-x-8 gap-y-1 sm:grid-cols-3">
              {[...strategy.positions]
                .sort((a, b) => b.weight - a.weight)
                .map((p) => (
                  <li key={p.ticker} className="flex items-center justify-between text-sm">
                    <span className="num text-ink">{p.ticker}</span>
                    <span className="num text-ink-muted">{pct(p.weight)}</span>
                  </li>
                ))}
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
