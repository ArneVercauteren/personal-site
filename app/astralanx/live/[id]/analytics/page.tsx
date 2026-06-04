import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { Disclaimer } from "@/components/Disclaimer";
import { Section } from "@/components/Section";
import { HelpTip } from "@/components/HelpTip";
import { AnnualReturnsChart } from "@/components/AnnualReturnsChart";
import { RollingSharpeChart } from "@/components/RollingSharpeChart";
import { DivergingBarChart, type DivergingDatum } from "@/components/DivergingBarChart";
import { CompositionDonut, type CompositionSlice } from "@/components/charts/CompositionDonut";
import { PicksHistory } from "@/components/PicksHistory";
import {
  loadPortfolio,
  loadStrategyMeta,
  type CapacityMethod,
  type OpenDiagnostics,
  type PerformanceRun,
  type PickRecord,
} from "@/lib/data";
import { money, pct, signedPct, shortDate } from "@/lib/format";

export function generateStaticParams() {
  return loadPortfolio()
    .strategies.filter((s) => s.visibility === "open")
    .map((s) => ({ id: s.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const s = loadPortfolio().strategies.find((x) => x.id === id);
  return s ? { title: `${s.name} · analytics` } : {};
}

// The run that carries the richest diagnostics — combined spans training + OOS,
// so it's the full-history view; fall back if a future export omits it.
function pickRun(meta: { performance?: { training: PerformanceRun; oos: PerformanceRun; combined: PerformanceRun } }) {
  const p = meta.performance;
  if (!p) return undefined;
  for (const run of [p.combined, p.oos, p.training]) {
    if (run?.open_diagnostics) return run;
  }
  return undefined;
}

// --- small presentational helpers ----------------------------------------

const num2 = (n: number) => n.toFixed(2);
const bps = (n: number) => `${Math.round(n)} bps`;

function StatCell({
  label,
  value,
  help,
  tone,
}: {
  label: string;
  value: string;
  help?: string;
  tone?: "gain" | "loss";
}) {
  const color = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-ink";
  return (
    <div className="bg-panel px-4 py-3">
      <dt className="flex items-center font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {label}
        <HelpTip text={help} />
      </dt>
      <dd className={`num mt-1 text-base ${color}`}>{value}</dd>
    </div>
  );
}

function StatGrid({ children, cols = 3 }: { children: ReactNode; cols?: 2 | 3 | 4 }) {
  const colClass =
    cols === 4
      ? "sm:grid-cols-4"
      : cols === 2
        ? "sm:grid-cols-2"
        : "sm:grid-cols-3";
  return (
    <dl className={`grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-hair bg-hair ${colClass}`}>
      {children}
    </dl>
  );
}

function CapacityCard({
  title,
  intro,
  m,
}: {
  title: string;
  intro: string;
  m: CapacityMethod;
}) {
  const ex = m.metric_explanations ?? {};
  // Method knobs, surfaced as a compact footnote. The impact model exposes the
  // square-root coefficient + worst-name cap; the heuristic exposes its ADV
  // participation rule.
  const params: { label: string; value: string; help?: string }[] = [];
  if (m.volume_impact_coef != null) {
    params.push({ label: "impact coef", value: num2(m.volume_impact_coef), help: ex.volume_impact_coef });
  }
  if (m.max_allowed_single_name_impact_bps != null) {
    params.push({ label: "worst-name cap", value: bps(m.max_allowed_single_name_impact_bps), help: ex.max_allowed_single_name_impact_bps });
  }
  if (m.participation_rate != null) {
    params.push({ label: "ADV participation", value: pct(m.participation_rate, 0), help: ex.participation_rate });
  }
  if (m.adv_lookback_days != null) {
    params.push({ label: "ADV lookback", value: `${m.adv_lookback_days}d`, help: ex.adv_lookback_days });
  }
  if (m.execution_days_cap != null) {
    params.push({ label: "exec days", value: `${m.execution_days_cap}d`, help: ex.execution_days_cap });
  }
  return (
    <div className="panel p-5">
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      <p className="mt-1 mb-4 text-xs text-ink-muted">{intro}</p>
      <StatGrid cols={3}>
        <StatCell label="Median capacity" value={money(m.median_capacity_usd)} help={ex.median_capacity_usd} />
        <StatCell label="25th pct" value={money(m.p25_capacity_usd)} help={ex.p25_capacity_usd} />
        <StatCell label="Tightest" value={money(m.worst_rebalance_capacity_usd)} help={ex.worst_rebalance_capacity_usd} />
        <StatCell label="Impact @ median" value={bps(m.median_capacity_estimated_impact_bps)} help={ex.median_capacity_estimated_impact_bps} />
        <StatCell label="Impact @ 25th" value={bps(m.p25_capacity_estimated_impact_bps)} help={ex.p25_capacity_estimated_impact_bps} />
        <StatCell label="Rebalances" value={String(m.rebalance_observations)} help={ex.rebalance_observations} />
      </StatGrid>
      {params.length > 0 ? (
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {params.map((p) => (
            <span key={p.label}>
              {p.label} <span className="text-ink">{p.value}</span>
              <HelpTip text={p.help} />
            </span>
          ))}
        </p>
      ) : null}
      {m.current_worst_name_impact_bps_median != null &&
      m.current_worst_name_impact_bps_max != null ? (
        <p className="mt-3 text-xs text-ink-muted">
          At the current{" "}
          {m.current_portfolio_size_usd != null ? money(m.current_portfolio_size_usd) : "book"} size,
          the worst-name modeled impact runs{" "}
          <span className="num text-ink">{bps(m.current_worst_name_impact_bps_median)}</span>{" "}
          (median) to{" "}
          <span className="num text-ink">{bps(m.current_worst_name_impact_bps_max)}</span> (max).
        </p>
      ) : null}
    </div>
  );
}

// Basket churn, derived from the sequence of target-weight baskets (the cost
// model's turnover = Σ|wₜ − wₜ₋₁| over the union of names; a full rotation =
// 2.0 = "two-way"). One-way is half that. Annualized using the rebalance
// cadence so it's comparable to fund-reported turnover figures.
function computeTurnover(records: PickRecord[], cadenceDays?: number) {
  const sorted = [...records].sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length < 2) return null;
  let sumGross = 0;
  let n = 0;
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1].weights;
    const curr = sorted[i].weights;
    const names = new Set([...Object.keys(prev), ...Object.keys(curr)]);
    let gross = 0;
    for (const t of names) gross += Math.abs((curr[t] ?? 0) - (prev[t] ?? 0));
    sumGross += gross;
    n += 1;
  }
  const twoWay = sumGross / n;
  const perYear = cadenceDays && cadenceDays > 0 ? 365.25 / cadenceDays : null;
  return {
    twoWay,
    oneWay: twoWay / 2,
    annualTwoWay: perYear ? twoWay * perYear : null,
    annualOneWay: perYear ? (twoWay / 2) * perYear : null,
    transitions: n,
  };
}

export default async function StrategyAnalyticsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const strategy = loadPortfolio().strategies.find((s) => s.id === id);
  const meta = loadStrategyMeta().strategies.find((m) => m.id === id);
  if (!strategy || !meta) notFound();

  const run = meta.performance ? pickRun(meta) : undefined;
  const d: OpenDiagnostics | undefined = run?.open_diagnostics;
  if (!run || !d) notFound();

  const dd = d.max_drawdown;
  const rs = d.rolling_3y_sharpe;
  const ff = d.fama_french_regression;
  const sn = d.sector_neutrality;
  const cap = d.capacity_analysis;

  const factorData: DivergingDatum[] = ff
    ? ff.factors_used.map((f) => ({
        label: f,
        value: ff.betas[f] ?? 0,
        help: ff.factor_explanations?.[f],
      }))
    : [];

  const sectorTilts: DivergingDatum[] = sn
    ? [...sn.top_average_sector_overweights, ...sn.top_average_sector_underweights]
        .map((s) => ({ label: s.name, value: s.value }))
        .sort((a, b) => b.value - a.value)
    : [];

  // Average sector composition of the basket over the backtest. The export only
  // carries the top sectors, so any residual weight is folded into an "Other
  // sectors" slice to keep the pie summing to ~100%.
  const sectorMix: CompositionSlice[] = sn
    ? (() => {
        const top = sn.top_average_portfolio_sectors.map((s) => ({
          label: s.name,
          value: s.value,
        }));
        const named = top.reduce((sum, s) => sum + s.value, 0);
        const other = 1 - named;
        return other > 0.005 ? [...top, { label: "Other sectors", value: other }] : top;
      })()
    : [];

  const turnover = d.picks_records
    ? computeTurnover(d.picks_records, meta.rebalance_cadence_days)
    : null;

  return (
    <div>
      <p className="mb-4 flex flex-wrap gap-x-4 gap-y-1">
        <Link href={`/astralanx/live/${id}`} className="font-mono text-xs text-accent hover:underline">
          ← Back to {strategy.name}
        </Link>
        <Link href="/astralanx/live" className="font-mono text-xs text-ink-muted hover:text-ink">
          Dashboard
        </Link>
      </p>

      <PageHeader
        eyebrow="Deep analytics"
        title={`${strategy.name} — under the hood`}
        intro={`Risk, factor, sector and capacity diagnostics computed over the full single-seed backtest (training + out-of-sample), ${shortDate(run.start)} – ${shortDate(run.end)}.`}
      />

      <div className="mt-6">
        <Disclaimer />
      </div>

      {d.annual_returns ? (
        <Section
          eyebrow="Returns"
          title="Calendar-year returns"
          intro="Each bar is one calendar year of the simulated strategy — green for a gain, red for a loss."
        >
          <AnnualReturnsChart returns={d.annual_returns} />
        </Section>
      ) : null}

      {rs && d.rolling_3y_sharpe_series ? (
        <Section
          eyebrow="Risk-adjusted"
          title="Rolling 3-year Sharpe"
          intro="Annualized Sharpe over a trailing three-year window — how steady the risk-adjusted return has been, not just the headline average."
        >
          <RollingSharpeChart series={d.rolling_3y_sharpe_series} />
          <div className="mt-4">
            <StatGrid cols={4}>
              <StatCell label="Current" value={num2(rs.current)} tone={rs.current >= 0 ? "gain" : "loss"} />
              <StatCell label="Average" value={num2(rs.avg)} />
              <StatCell label="Best" value={`${num2(rs.max)} · ${shortDate(rs.max_date)}`} tone="gain" />
              <StatCell label="Worst" value={`${num2(rs.min)} · ${shortDate(rs.min_date)}`} tone={rs.min >= 0 ? undefined : "loss"} />
            </StatGrid>
          </div>
        </Section>
      ) : null}

      {dd ? (
        <Section
          eyebrow="Risk"
          title="Worst drawdown anatomy"
          intro="The single deepest peak-to-trough decline of the backtest, and how long the climb back took."
        >
          <StatGrid cols={4}>
            <StatCell label="Depth" value={pct(dd.value)} help={dd.metric_explanations?.value} tone="loss" />
            <StatCell label="Peak" value={shortDate(dd.peak_date)} help={dd.metric_explanations?.peak_date} />
            <StatCell label="Trough" value={shortDate(dd.trough_date)} help={dd.metric_explanations?.trough_date} />
            <StatCell
              label="Recovered"
              value={dd.recovery_date ? shortDate(dd.recovery_date) : "Not recovered"}
              help={dd.metric_explanations?.recovery_date}
            />
          </StatGrid>
          <p className="mt-3 text-xs text-ink-muted">
            Peak to recovery spanned{" "}
            <span className="num text-ink">{dd.duration_days.toLocaleString()} days</span>
            <HelpTip text={dd.metric_explanations?.duration_days} />.
          </p>
        </Section>
      ) : null}

      {ff ? (
        <Section
          eyebrow="Attribution"
          title="Factor exposure (Fama–French)"
          intro="Regressing the strategy's returns on standard risk factors shows what it's really tilted toward. Bars are factor betas; alpha is the return left unexplained."
        >
          <DivergingBarChart data={factorData} format="ratio" />
          <div className="mt-4">
            <StatGrid cols={3}>
              <StatCell
                label="Alpha (ann.)"
                value={signedPct(ff.alpha_annualized)}
                help={ff.metric_explanations?.alpha_annualized}
                tone={ff.alpha_annualized >= 0 ? "gain" : "loss"}
              />
              <StatCell label="R²" value={num2(ff.r_squared)} help={ff.metric_explanations?.r_squared} />
              <StatCell label="Observations" value={ff.observations.toLocaleString()} help={ff.metric_explanations?.observations} />
            </StatGrid>
          </div>
        </Section>
      ) : null}

      {sn ? (
        <Section
          eyebrow="Positioning"
          title="Sector tilts"
          intro="How the basket leans versus an equal-weight eligible universe — the sectors it persistently over- and under-weights."
        >
          <StatGrid cols={4}>
            <StatCell label="Avg active share" value={pct(sn.average_sector_active_share)} help={sn.metric_explanations?.average_sector_active_share} />
            <StatCell label="Median" value={pct(sn.median_sector_active_share)} help={sn.metric_explanations?.median_sector_active_share} />
            <StatCell label="Max deviation" value={pct(sn.average_max_sector_abs_deviation)} help={sn.metric_explanations?.average_max_sector_abs_deviation} />
            <StatCell label="Eff. sectors" value={num2(sn.average_effective_sector_count)} help={sn.metric_explanations?.average_effective_sector_count} />
          </StatGrid>
          {sectorMix.length > 0 ? (
            <div className="mt-5">
              <p className="mb-3 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                Average sector mix
              </p>
              <CompositionDonut
                slices={sectorMix}
                footnote="Average share of the basket by SEC SIC-derived sector across the backtest; sectors outside the top holdings are grouped as “Other sectors.”"
              />
            </div>
          ) : null}
          {sectorTilts.length > 0 ? (
            <div className="mt-5">
              <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                Average tilt vs universe (overweight ▸ / ◂ underweight)
              </p>
              <DivergingBarChart data={sectorTilts} format="signed-pct" />
            </div>
          ) : null}
        </Section>
      ) : null}

      {cap ? (
        <Section
          eyebrow="Liquidity"
          title="Capacity"
          intro="How much capital the strategy could deploy before its own trading moved prices — estimated two ways."
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <CapacityCard
              title="Liquidity screen"
              intro="Participating in a fixed slice of each name's average daily volume over a few execution days."
              m={cap.heuristic_capacity}
            />
            <CapacityCard
              title="Impact model"
              intro="The capital at which the square-root impact model hits the configured worst-name impact cap."
              m={cap.impact_model_capacity}
            />
          </div>
        </Section>
      ) : null}

      {turnover ? (
        <Section
          eyebrow="Trading"
          title="Turnover"
          intro="Average basket churn between rebalances, measured from the target-weight baskets below. Two-way counts both buys and sells (a full rotation = 200%); one-way is half that."
        >
          <StatGrid cols={4}>
            <StatCell
              label="Two-way / rebalance"
              value={pct(turnover.twoWay, 0)}
              help="Average gross change in weights between consecutive rebalances — buys plus sells. A full portfolio rotation is 200%."
            />
            <StatCell
              label="One-way / rebalance"
              value={pct(turnover.oneWay, 0)}
              help="Half the two-way figure — the share of the book actually replaced each rebalance."
            />
            {turnover.annualTwoWay != null ? (
              <StatCell
                label="Two-way / year"
                value={pct(turnover.annualTwoWay, 0)}
                help={`Per-rebalance two-way turnover annualized at the ${meta.rebalance_cadence_days}-day cadence (~${(365.25 / meta.rebalance_cadence_days).toFixed(1)} rebalances/yr).`}
              />
            ) : null}
            {turnover.annualOneWay != null ? (
              <StatCell
                label="One-way / year"
                value={pct(turnover.annualOneWay, 0)}
                help="One-way turnover annualized at the rebalance cadence — comparable to fund-reported turnover."
              />
            ) : null}
          </StatGrid>
          <p className="mt-3 text-xs text-ink-muted">
            Derived from {turnover.transitions.toLocaleString()} rebalance
            transitions across the baskets below.
          </p>
        </Section>
      ) : null}

      {d.picks_records && d.picks_records.length > 0 ? (
        <Section
          eyebrow="Holdings"
          title="Rebalance history"
          intro={`Every basket the strategy held, rebalance by rebalance — ${d.picks_records.length} in all. Pick a date to see that day's names and target weights.`}
        >
          <PicksHistory records={d.picks_records} />
        </Section>
      ) : null}
    </div>
  );
}
