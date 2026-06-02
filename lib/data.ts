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
  stats: Stats;
}

export interface OpenStrategy extends StrategyBase {
  visibility: "open";
  positions: Position[];
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
