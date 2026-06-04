# Subsystem — Live paper-trading dashboard (Tier 1)

> **Status: built (v3).** The dashboard renders real data from the contract: per-strategy cards with a Recharts equity curve (split into a muted out-of-sample **backfill** segment and a solid **live** segment at the `live_since` marker), split live/backtest stats, a drawdown chart, and positions (open) / exposure donut (secured). Each card links to a **per-strategy detail page** (`/astralanx/live/[id]`) with a continuous OOS/backtest → live shaded-band chart, regime stat cards, and the validity battery. A trade-log view is the planned next increment.

## What this owns

The reader side of the live data: the dashboard page and the chart/stat components that render `public/data/*.json` through `lib/data.ts`.

## Shape (built)

- `app/astralanx/live/page.tsx` — loads `portfolio.json` + `strategies.json` via `lib/data.ts`, shows the `as_of` date and the disclaimer, then renders strategies in two labelled sections — **Open strategies** (formula + positions shown) and **Secured strategies** (performance + exposure only) — splitting on `isOpen`. One `StrategyCard` per strategy.
- `app/astralanx/live/[id]/page.tsx` — **per-strategy detail page** (statically generated from the published ids). Header + key facts, the continuous `RegimeEquityChart` that groups every pre-live curve point as OOS/backtest history, the live (forward) stats, then a **Backtest** section with three detailed-stat panels — **Out-of-sample**, **Training (in-sample)**, and **Combined (training + OOS)** — driven by `meta.performance` (the three single-seed runs), a king-level **Capacity & holdings** block (`active_share`, `capacity`), and the composition (basket for open, exposure donut for secured). The `DetailedStatsPanel` helper renders whichever of the ~18 `DetailedStats` fields a run carries; degrades gracefully when provenance is absent.
- `components/StrategyCard.tsx` — per-strategy summary card: name, open/secured badge, equity curve, split live/backtest stats, drawdown chart, positions table (open) or exposure donut (secured), metadata, and a "Full breakdown →" link to the detail page.
- `components/EquityCurveChart.tsx` — Recharts area/line equity curve. With `liveSince` it renders two-tone: a muted/dashed out-of-sample backfill segment and a solid live segment, with a "Live" `ReferenceLine` marker and a small legend. Client component.
- `components/RegimeEquityChart.tsx` — Recharts equity curve with translucent `ReferenceArea` bands behind it for OOS/backtest history and live paper-trading (boundaries snapped to the nearest curve date), the live marker, and a regime legend. Detail-page only. Client component.
- `components/FormulaView.tsx` — renders an **open** strategy's published `formula` DSL tree (from `lib/data.ts`) as a readable, math-like expression: indicator pills with window subscripts, infix operators (`×`, `÷`, `|·|`), the `top_n`/cadence summary, the `exit_root` rule, and an auto-generated indicator glossary. Pure server component (no Recharts, no client JS). Rendered in a `#formula` section on the detail page for open strategies that carry a formula; absent for signal-only open strategies and never shown for secured.
- `components/DrawdownChart.tsx` — Recharts underwater plot derived from the equity curve (`value / running-peak − 1`); takes an optional `liveSince` marker. Client component.
- `components/charts/CompositionDonut.tsx` — shared Recharts donut + legend for any set of labelled weighted slices that sum to ~1. The single rendering used by both the secured exposure donut and the open analytics sector-mix pie. Client component.
- `components/ExposureDonut.tsx` — secured sector/asset-class exposure; a thin wrapper over `CompositionDonut` that maps `{group, weight}` slices and adds the secured heading/footnote. Client component.
- `components/charts/chartColors.ts` — shared palette mirroring the Tailwind tokens (charts are client components and can't read Tailwind at runtime).
- `components/StatsTable.tsx` — CAGR / Sharpe / max drawdown, mono/tabular. Reused for each regime card.
- `components/Disclaimer.tsx` — the standing paper-only disclaimer.

Recharts loads only on `/astralanx/live` and `/astralanx/live/[id]` (code-split), so the rest of the site keeps its small bundle.

The summary equity cards and per-strategy lifecycle graph both read `public/data/benchmark.json`
through `lib/data.ts` and show a default-on S&P 500 overlay toggle. The overlay is rebased to the
visible strategy window, so zooming the lifecycle explorer compares relative growth over that
selected range. It remains static-first: no browser-side market-data fetch.

## Planned (next increment)

- A trade-log view fed by `trades.json`.

## Two strategy classes

The page renders both [open and secured](../concepts/open-vs-secured-strategies.md) strategies,
keyed off `visibility`:

- **open** → badge "Open · formula shown", full **positions** table, and (when the entry carries a `formula`) a rendered **Formula** section on the detail page via `FormulaView` — the actual DSL score tree, exit rule, and indicator glossary. The card's "View the formula →" link jumps to that `#formula` section.
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

- `public/data/benchmark.json`, `paper_trading/benchmark.py`, `components/charts/benchmarkOverlay.ts`
- `app/astralanx/live/page.tsx`, `app/astralanx/live/[id]/page.tsx`, `components/StrategyCard.tsx`, `components/EquityCurveChart.tsx`, `components/RegimeEquityChart.tsx`, `components/DrawdownChart.tsx`, `components/ExposureDonut.tsx`, `components/charts/CompositionDonut.tsx`, `components/FormulaView.tsx`, `components/charts/chartColors.ts`, `components/StatsTable.tsx`, `components/Disclaimer.tsx`, `lib/data.ts`.
