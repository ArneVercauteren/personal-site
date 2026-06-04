import "server-only";
import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// THE DATA CONTRACT — single source of truth for public/data/*.json.
// Tier 2 (paper_trading/ + the private updater repo) writes JSON to match these
// types; Tier 1 reads only through here. See docs/concepts/data-contract.md.
// `visibility` gates the shape: secured entries MUST NOT carry positions/formula.
// ---------------------------------------------------------------------------

export type Visibility = "open" | "secured";

export interface EquityPoint {
  /** ISO date, YYYY-MM-DD. */
  d: string;
  /** Portfolio value in base currency. */
  v: number;
}

export interface Stats {
  cagr: number;
  sharpe: number;
  /** Max drawdown, as a negative fraction (e.g. -0.12). */
  max_dd: number;
}

export interface Position {
  ticker: string;
  weight: number;
}

export interface ExposureSlice {
  /** A sector / asset-class label — never a ticker. */
  group: string;
  weight: number;
}

interface StrategyBase {
  id: string;
  name: string;
  visibility: Visibility;
  equity_curve: EquityPoint[];
  /** Stats over the full displayed curve (backfill + live). */
  stats: Stats;
  /**
   * Optional one-time backfill support. The equity curve may start before the
   * strategy went live; `live_since` (ISO date) marks where real forward
   * paper-trading begins. Everything before it is an out-of-sample backtest.
   * `stats_backtest` covers the pre-live segment, `stats_live` the post-live
   * one. All three are optional so pre-backfill data still renders. A segment
   * with < 2 points reports zeros (treated as "accruing" in the UI).
   */
  live_since?: string;
  stats_backtest?: Stats;
  stats_live?: Stats;
}

/**
 * One node of a Darwin DSL formula tree — the scrubbed score expression an open
 * strategy publishes. A discriminated-ish union keyed on `kind`; every variant's
 * extra fields are optional so the reader stays tolerant of trees it renders but
 * doesn't evaluate. This is **open-only**: a secured entry must never carry it
 * (enforced by `paper_trading/secured.py::assert_sanitized`).
 */
export interface FormulaNode {
  kind:
    | "number"
    | "indicator"
    | "transform"
    | "arithmetic"
    | "comparison"
    | "logic"
    | "conditional";
  /** Operator / indicator / transform name (absent for `number`). */
  name?: string;
  /** Literal value (`number` nodes only). */
  value?: number;
  /** Indicator / transform params, e.g. `{ window: 60 }`. */
  params?: Record<string, number | string>;
  /** The single operand of a `transform`. */
  child?: FormulaNode;
  /** Operands of an `arithmetic` (n-ary) or `logic` node. */
  children?: FormulaNode[];
  /** `comparison` operands. */
  left?: FormulaNode;
  right?: FormulaNode;
  third?: FormulaNode;
  /** Alternate `logic` operand list. */
  clauses?: FormulaNode[];
  /** `conditional` branches. */
  cases?: { condition?: FormulaNode; result?: FormulaNode; else?: FormulaNode }[];
}

/**
 * The published formula for an open strategy: the score expression (a
 * `FormulaNode` root) plus the top-level selection knobs Darwin attaches —
 * `top_n` (how many names it holds), an optional `exit_root` rule, and the
 * native `rebalance_interval`. Carries no secrets: open formulas are published
 * for auditability. See docs/concepts/open-vs-secured-strategies.md.
 */
export interface StrategyFormula extends FormulaNode {
  /** Number of names held each rebalance (top-N selection). */
  top_n?: number;
  /** Optional exit rule evaluated against held names. */
  exit_root?: FormulaNode;
  /** Native rebalance cadence label, e.g. "2M". */
  rebalance_interval?: string;
}

export interface OpenStrategy extends StrategyBase {
  visibility: "open";
  positions: Position[];
  /** The full DSL score tree, rendered on the detail page (open only). */
  formula?: StrategyFormula;
  /** Optional link to a longer public writeup of the formula. */
  formula_ref?: string;
}

export interface SecuredStrategy extends StrategyBase {
  visibility: "secured";
  exposure: ExposureSlice[];
}

export type Strategy = OpenStrategy | SecuredStrategy;

export interface PortfolioFile {
  /** Snapshot date, ISO. */
  as_of: string;
  base_currency: string;
  strategies: Strategy[];
}

export interface CostModel {
  commission_bps: number;
  slippage_bps: number;
  /**
   * Optional Darwin cost-model parameters. Omitted fields fall back to Darwin's
   * engine defaults in paper_trading/costs.py, so older specs keep working.
   * See docs/concepts/data-contract.md and the Darwin methodology section.
   */
  /** Reference share price for price-scaled slippage (default 50). */
  spread_ref_price?: number;
  /** sqrt market-impact coefficient (default 0.5). */
  volume_impact_coef?: number;
  /** Authoritative book size the volume-impact term sizes trades against
   *  (default Darwin's $1,000,000), independent of the traded portfolio_size. */
  impact_portfolio_size?: number;
  /** Crisis-aware vol cost scaling (defaults: enabled, k=0.75, 63/252d, max 3). */
  vol_scaled_cost_enable?: boolean;
  vol_cost_k?: number;
  vol_cost_realized_window?: number;
  vol_cost_long_window?: number;
  vol_cost_mult_max?: number;
}

/**
 * A full per-run stat block from one deterministic (single-seed) Darwin
 * backtest. Extends the headline `Stats` (cagr/sharpe/max_dd) with the richer
 * diagnostics Darwin records. Every extra field is optional — the detail page
 * renders whatever the export provides. Numbers only; nothing secret, so this
 * publishes for secured strategies too.
 */
export interface DetailedStats extends Stats {
  /** Total cumulative return over the window (fraction). */
  total_return?: number;
  /** Annualized volatility (fraction). */
  volatility?: number;
  /** Sortino ratio (downside-only risk adjustment). */
  sortino?: number;
  /** Calmar ratio (CAGR / |max drawdown|). */
  calmar?: number;
  /** Longest peak-to-recovery drawdown, in calendar days. */
  max_dd_duration_days?: number;
  /** Fraction of rebalance periods with a positive return. */
  win_rate?: number;
  /** Best / worst calendar-year return over the window (fraction). */
  best_year?: number;
  worst_year?: number;
  /** Worst rolling 3-year / 5-year CAGR over the window (negative ok). */
  worst_rolling_3y_cagr?: number;
  worst_rolling_5y_cagr?: number;
  /** Minimum rolling annualized Sharpe. */
  rolling_sharpe_min?: number;
  /** Beta / correlation vs the S&P 500 benchmark. */
  benchmark_beta?: number;
  benchmark_corr?: number;
  /** Annualized Fama-French alpha (fraction, e.g. 0.04 = 4%/yr). */
  alpha?: number;
  /** Information ratio vs the benchmark. */
  information_ratio?: number;
}

/** A `{ name, value }` pair — a labelled magnitude (sector weight, tilt, …). */
export interface NamedValue {
  name: string;
  value: number;
}

/**
 * The worst peak-to-trough drawdown over a run, with its anatomy: the dates of
 * the prior peak, the trough, and the recovery (null if never recovered), plus
 * the calendar-day duration. Each numeric/date field is self-documented by an
 * entry in `metric_explanations`.
 */
export interface MaxDrawdownDetail {
  /** Most negative peak-to-trough drawdown (negative fraction). */
  value: number;
  peak_date: string;
  trough_date: string;
  /** ISO date, or null / "Not Recovered" when the curve never regained the peak. */
  recovery_date: string | null;
  duration_days: number;
  metric_explanations?: Record<string, string>;
}

/** Sector-tilt diagnostics vs an equal-weight eligible universe. Numbers only —
 *  the internal `sector_map_source` path the exporter attaches is never read. */
export interface SectorNeutrality {
  status: string;
  methodology?: string;
  rebalance_observations: number;
  average_sector_active_share: number;
  median_sector_active_share: number;
  worst_sector_active_share: number;
  best_sector_active_share: number;
  average_max_sector_abs_deviation: number;
  average_mapped_portfolio_weight_ratio: number;
  average_mapped_universe_name_ratio: number;
  average_portfolio_sector_count: number;
  average_universe_sector_count: number;
  average_effective_sector_count: number;
  worst_rebalance_date: string;
  best_rebalance_date: string;
  top_average_portfolio_sectors: NamedValue[];
  top_average_universe_sectors: NamedValue[];
  top_average_sector_overweights: NamedValue[];
  top_average_sector_underweights: NamedValue[];
  metric_explanations?: Record<string, string>;
}

/** One capacity estimate (heuristic liquidity-screen or impact-model). The
 *  shared rebalance-percentile fields plus method-specific knobs. */
export interface CapacityMethod {
  method: string;
  median_capacity_usd: number;
  p25_capacity_usd: number;
  worst_rebalance_capacity_usd: number;
  rebalance_observations: number;
  median_capacity_estimated_impact_bps: number;
  p25_capacity_estimated_impact_bps: number;
  worst_rebalance_capacity_estimated_impact_bps: number;
  // Heuristic-only knobs.
  participation_rate?: number;
  adv_lookback_days?: number;
  execution_days_cap?: number;
  // Impact-model-only knobs and current-size diagnostics.
  volume_impact_coef?: number;
  max_allowed_single_name_impact_bps?: number;
  current_portfolio_size_usd?: number;
  current_size_vs_median_capacity?: number;
  current_worst_name_impact_bps_median?: number;
  current_worst_name_impact_bps_p75?: number;
  current_worst_name_impact_bps_max?: number;
  metric_explanations?: Record<string, string>;
}

export interface CapacityAnalysis {
  heuristic_capacity: CapacityMethod;
  impact_model_capacity: CapacityMethod;
  metric_explanations?: Record<string, string>;
}

/** Fama-French factor regression of the strategy's returns: factor betas, the
 *  residual alpha, and fit quality, each with a plain-English explanation. */
export interface FamaFrenchRegression {
  alpha_daily: number;
  alpha_annualized: number;
  betas: Record<string, number>;
  r_squared: number;
  observations: number;
  factors_used: string[];
  excess_return_regression: boolean;
  metric_explanations?: Record<string, string>;
  factor_explanations?: Record<string, string>;
}

/** Summary of the rolling 3-year annualized Sharpe over a run. */
export interface RollingSharpeSummary {
  min: number;
  min_date: string;
  max: number;
  max_date: string;
  avg: number;
  current: number;
}

/** One point of the rolling-Sharpe series. `date` may carry a time suffix. */
export interface RollingSharpePoint {
  date: string;
  sharpe: number;
}

/** One historical rebalance basket: the names held and their target weights. */
export interface PickRecord {
  label: string;
  /** Rebalance date; may carry a " 00:00:00" suffix from the exporter. */
  date: string;
  count: number;
  tickers: string[];
  weights: Record<string, number>;
}

/**
 * The rich, optional analytics block the open Darwin exporter attaches to a
 * run. Everything here is numbers / labels published for auditability — no
 * secret formula or internal path is ever read (the exporter's
 * `sector_map_source` and the duplicate `artifacts`/`holdings` payloads are
 * intentionally untyped and undisplayed). Rendered on the per-strategy
 * analytics page; see docs/concepts/data-contract.md.
 */
export interface OpenDiagnostics {
  /** Calendar-year returns keyed by year string, e.g. `{ "2008": -0.36 }`. */
  annual_returns?: Record<string, number>;
  max_drawdown?: MaxDrawdownDetail;
  sector_neutrality?: SectorNeutrality;
  capacity_analysis?: CapacityAnalysis;
  fama_french_regression?: FamaFrenchRegression;
  rolling_3y_sharpe?: RollingSharpeSummary;
  rolling_3y_sharpe_series?: RollingSharpePoint[];
  picks_records?: PickRecord[];
}

/**
 * One of the three single-seed runs the Darwin exporter records. `start`/`end`
 * is the window envelope; `windows` optionally lists sub-windows (e.g. the
 * training regimes) for display when the run spans more than one stretch.
 */
export interface PerformanceRun {
  /** ISO date, inclusive. */
  start: string;
  /** ISO date, inclusive. */
  end: string;
  /** Optional sub-windows (e.g. training's constituent regimes), display only. */
  windows?: { start: string; end: string; label?: string }[];
  stats: DetailedStats;
  /** Optional rich analytics for the deep-dive page (open strategies). */
  open_diagnostics?: OpenDiagnostics;
}

/**
 * The three runs Darwin computes for a deployed king: the in-sample training
 * window, the held-out out-of-sample window, and the two combined. Each is a
 * separate single-seed backtest, so the combined figures (Sharpe, max DD across
 * the boundary) are authoritative rather than stitched from the two halves.
 */
export interface StrategyPerformance {
  training: PerformanceRun;
  oos: PerformanceRun;
  combined: PerformanceRun;
}

export interface StrategyMeta {
  id: string;
  name: string;
  visibility: Visibility;
  portfolio_size: number;
  base_currency: string;
  rebalance_cadence_days: number;
  deployed_on: string;
  cost_model: CostModel;
  blurb: string;
  /**
   * Optional provenance from Darwin (Tier 3), shown on the per-strategy detail
   * page. `performance` carries the three single-seed runs (training, OOS,
   * combined) each with detailed stats; `active_share` and `capacity` are
   * king-level liquidity/holdings measures. All optional and backward
   * compatible — entries without them simply omit the breakdown.
   */
  performance?: StrategyPerformance;
  /** Active share vs an equal-weight eligible universe (fraction). */
  active_share?: number;
  /** Capacity estimates (USD): liquidity-screen and stricter impact-consistent. */
  capacity?: { liquidity_usd?: number; impact_usd?: number };
}

export interface StrategiesFile {
  as_of: string;
  strategies: StrategyMeta[];
}

export interface Trade {
  strategy_id: string;
  /** ISO date. */
  d: string;
  ticker: string;
  side: "buy" | "sell";
  weight: number;
}

export interface TradesFile {
  as_of: string;
  trades: Trade[];
}

// ---------------------------------------------------------------------------
// Loaders. Static-first: JSON is read from public/data at build time.
// ---------------------------------------------------------------------------

function readJson<T>(file: string): T {
  const p = path.join(process.cwd(), "public", "data", file);
  return JSON.parse(fs.readFileSync(p, "utf8")) as T;
}

export function loadPortfolio(): PortfolioFile {
  return readJson<PortfolioFile>("portfolio.json");
}

export function loadStrategyMeta(): StrategiesFile {
  return readJson<StrategiesFile>("strategies.json");
}

export function loadTrades(): TradesFile {
  return readJson<TradesFile>("trades.json");
}

export function getMetaById(id: string): StrategyMeta | undefined {
  return loadStrategyMeta().strategies.find((s) => s.id === id);
}

/** Type guard: narrow a Strategy to the open variant. */
export function isOpen(s: Strategy): s is OpenStrategy {
  return s.visibility === "open";
}
