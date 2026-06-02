# Subsystem — Live paper-trading dashboard (Tier 1)

> **Status: built (v2).** The dashboard renders real data from the contract: per-strategy cards with a Recharts equity curve, stats, a drawdown chart, and positions (open) / exposure donut (secured). A trade-log view is the planned next increment.

## What this owns

The reader side of the live data: the dashboard page and the chart/stat components that render `public/data/*.json` through `lib/data.ts`.

## Shape (built)

- `app/darwin/live/page.tsx` — loads `portfolio.json` + `strategies.json` via `lib/data.ts`, shows the `as_of` date and the disclaimer, then renders strategies in two labelled sections — **Open strategies** (formula + positions shown) and **Secured strategies** (performance + exposure only) — splitting on `isOpen`. One `StrategyCard` per strategy.
- `components/StrategyCard.tsx` — per-strategy card: name, open/secured badge, equity curve, stats, drawdown chart, and positions table (open) or exposure donut (secured) + metadata (capital, cadence, costs).
- `components/EquityCurveChart.tsx` — Recharts area/line equity curve (gain/loss colored, faint grid, hover tooltip). Client component.
- `components/DrawdownChart.tsx` — Recharts underwater plot derived from the equity curve (`value / running-peak − 1`). Client component.
- `components/ExposureDonut.tsx` — Recharts donut + legend for secured sector/asset-class exposure. Client component.
- `components/charts/chartColors.ts` — shared palette mirroring the Tailwind tokens (charts are client components and can't read Tailwind at runtime).
- `components/StatsTable.tsx` — CAGR / Sharpe / max drawdown, mono/tabular.
- `components/Disclaimer.tsx` — the standing paper-only disclaimer.

Recharts loads only on `/darwin/live` (code-split), so the rest of the site keeps its small bundle.

## Planned (next increment)

- A trade-log view fed by `trades.json`.

## Two strategy classes

The page renders both [open and secured](../concepts/open-vs-secured-strategies.md) strategies,
keyed off `visibility`:

- **open** → badge "Open · formula shown", full **positions** table, link to the formula.
- **secured** → badge "Live paper · positions held private", **exposure donut** (sector/asset-class) instead of a positions table. Never render `positions` for a secured entry — the field isn't there, and the UI must not invent one.

## Invariants it must respect

- **Reads through the [data contract](../concepts/data-contract.md).** All data comes from `lib/data.ts`; no hand-parsing of JSON in components.
- **Honour `visibility`.** Positions/formula render only for open strategies; secured strategies show exposure only.
- **[Paper-only disclaimer](../concepts/paper-trading-only.md) is mandatory** on every page that shows portfolio data.
- **[Read-only](../concepts/public-site-is-read-only.md), [static-first](../concepts/static-first.md)** — data is read from committed JSON at build time, never fetched live from a market source.
- Show `as_of` so a visitor knows how fresh the snapshot is.

## Adding a chart / stat

See the recipe: [tasks/add-dashboard-chart.md](../tasks/add-dashboard-chart.md).

## Source files

- `app/darwin/live/page.tsx`, `components/StrategyCard.tsx`, `components/EquityCurveChart.tsx`, `components/DrawdownChart.tsx`, `components/ExposureDonut.tsx`, `components/charts/chartColors.ts`, `components/StatsTable.tsx`, `components/Disclaimer.tsx`, `lib/data.ts`.
