# Concept — The data contract

The boundary between Tier 2 (the Python updater that *writes* JSON) and Tier 1 (the site that *reads* it) is a single, small, stable contract: the JSON shape. The **TypeScript types in `lib/data.ts` are the single source of truth** for that shape.

## The rule

- **`lib/data.ts` defines the shape.** The types there describe exactly what `public/data/*.json` contains. The site loads and types its data through this module; nothing else hand-parses the JSON.
- **Writer and reader change together.** If you change a field, you change the Tier-2 writer (`paper_trading/`) and `lib/data.ts` in the **same commit**. A shape change that lands on only one side is a broken contract.
- **Keep it small and stable.** The contract is a coupling point — every field is a thing both tiers must agree on forever. Add fields deliberately; don't leak internal simulator state into the public JSON.

## The files

| File | Tier | Role |
|---|---|---|
| `public/data/portfolio.json` | published | equity curve, stats, and (open only) positions per strategy |
| `public/data/benchmark.json` | published | S&P 500 benchmark curve for chart overlays |
| `public/data/trades.json` | published | trade log (open strategies) |
| `public/data/strategies.json` | published | metadata per deployed strategy |
| `lib/data.ts` | 1 (reader) | typed loaders + the type definitions |
| `paper_trading/update.py` | 2b (writer) | open-strategy JSON, in the public repo |
| `paper_trading/benchmark.py` | 2b (writer) | fetches the SPY-backed S&P 500 curve, or converts a local CSV, into `benchmark.json` |
| private repo `daily.yml` | 2a (writer) | secured sanitized JSON, pushed to the public repo |

How an open strategy computes its weights — a lightweight momentum `signal` or a real Darwin
`formula` (DSL tree) run through the vendored evaluator — is an implementation detail of the
writer. It does **not** change this contract: both paths emit the same `portfolio.json` /
`strategies.json` / `trades.json` shape, so `lib/data.ts` is unaffected.

## `visibility` gates the shape

Every strategy entry carries `visibility: "open" | "secured"`, and that field decides which
fields are allowed. This is a **security boundary** — see
[open-vs-secured-strategies.md](open-vs-secured-strategies.md).

- **open** → may include `positions` (full ticker weights), the `formula` DSL score tree
  (published for auditability and rendered on the detail page by `components/FormulaView.tsx`),
  and a `formula_ref`.
- **secured** → may include `exposure` (aggregate sector/asset-class only). **Must never
  include `positions` or any formula.** The leak guard
  `paper_trading/secured.py::assert_sanitized` rejects `positions`/`formula`/`formula_ref` on a
  secured entry.

## Example: `portfolio.json` (mixed open + secured)

```json
{
  "as_of": "2026-06-01",
  "base_currency": "USD",
  "strategies": [
    {
      "id": "open_momentum_v1",
      "name": "Momentum (Open)",
      "visibility": "open",
      "equity_curve": [{"d": "2024-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.081, "sharpe": 0.65, "max_dd": -0.12},
      "live_since": "2026-01-02",
      "stats_backtest": {"cagr": 0.090, "sharpe": 0.70, "max_dd": -0.15},
      "stats_live": {"cagr": 0.034, "sharpe": 0.55, "max_dd": -0.04},
      "positions": [{"ticker": "AAPL", "weight": 0.04}],
      "formula_ref": "/writing/open-momentum"
    },
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.094, "sharpe": 0.71, "max_dd": -0.10},
      "exposure": [{"group": "Technology", "weight": 0.32},
                   {"group": "Healthcare", "weight": 0.18}]
    }
  ]
}
```

Notes on the shape:
- Keys are kept **short** (`d`/`v` for date/value) because the equity curve is the largest array — small keys keep the payload CDN-friendly.
- `as_of` is the snapshot date; the site shows it so a reader knows how fresh the data is.
- Money values are plain numbers in `base_currency`; the site formats them via `lib/format.ts`.
- `exposure[].group` is a sector / asset-class label, never a ticker.

## `benchmark.json` - S&P 500 overlay

The dashboard also publishes a separate benchmark snapshot:

```json
{
  "as_of": "2026-03-13",
  "base_currency": "USD",
  "benchmarks": [
    {
      "id": "sp500",
      "name": "S&P 500",
      "equity_curve": [{"d": "1993-01-29", "v": 1000000.0}]
    }
  ]
}
```

`equity_curve[].v` is a benchmark value normalized by `paper_trading/benchmark.py` from a
keyless SPY price fetch, with the legacy CSV import still available for one-off historical loads.
Tier 1 charts rebase that curve again to the visible strategy window before overlaying it, so the
comparison reads as relative growth over the selected range. This is still static-first: the
browser never fetches market data. Scheduled refreshes preserve the already-published prefix and
append newly available bars, avoiding historical churn from tiny adjusted-price source revisions.

### Backfill & the live marker

The equity curve may start **before** a strategy went live — a one-time historical backfill so the
site has evidence on day one rather than after months of waiting. Three **optional** fields describe
this (open and secured alike); all are backward-compatible, so older entries without them still render
as a single curve with one stat set:

- `live_since` — ISO date where real forward paper-trading begins. The site draws a marker here and
  renders the pre-live curve muted/dashed. Everything before it is an **out-of-sample backtest**, not
  live evidence; the copy says so.
- `stats_backtest` — stats over the pre-live segment `[curve start, live_since)`.
- `stats_live` — stats over the post-live segment `[live_since, last bar]`. Reports zeros while the
  segment is shorter than a handful of bars; the UI shows "accruing" until then.

`stats` stays the full-curve summary. When `cost_model.impact_book_cap` is set, the curve models a
disciplined investor: target weights are scaled so invested capital stays at capacity and excess
equity remains cash, so the curve never assumes trading past capacity. The detail
page notes the cap on the lifecycle chart. On the Tier-2 **writer** side, the curve start is set per-king by
a `backfill_start` field in the strategy spec (an updater input, *not* part of this published
contract); if Darwin also provides `darwin_equity_curve`, that training+OOS curve is used as the
authoritative prefix and Yahoo-backed simulation starts only at the prefix's final date.
`deployed_on` in `strategies.json` is the live-since date. See
[subsystems/paper-trading-updater.md](../subsystems/paper-trading-updater.md).

When `performance.training.equity_curve` or `performance.oos.equity_curve` is present, the
corresponding chart preset uses that standalone replay curve. This keeps the chart consistent with
the preset's CAGR and other statistics. The full-history chart still uses the continuous lifecycle
curve, whose capacity cap and accumulated account size can produce different returns.

## `strategies.json` — per-strategy metadata

A separate file carries non-secret descriptive metadata for every strategy (open and secured),
set when the strategy is deployed from Darwin and shown on the site:

```json
{
  "as_of": "2026-06-01",
  "strategies": [
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "portfolio_size": 100000,
      "base_currency": "USD",
      "rebalance_cadence_days": 42,
      "deployed_on": "2026-05-01",
      "cost_model": {"commission_bps": 1.0, "slippage_bps": 5.0,
                     "spread_ref_price": 50.0, "volume_impact_coef": 0.5,
                     "impact_portfolio_size": 1000000,
                     "vol_scaled_cost_enable": true, "vol_cost_k": 0.75,
                     "vol_cost_realized_window": 63, "vol_cost_long_window": 252,
                     "vol_cost_mult_max": 3.0},
      "blurb": "Balanced risk/return king from epoch 7.",
      "performance": {
        "training": {"start": "2018-01-02", "end": "2022-12-30",
                     "windows": [{"start": "2018-01-02", "end": "2020-12-31", "label": "Regime 1"}],
                     "stats": {"cagr": 0.131, "volatility": 0.171, "sharpe": 0.99,
                               "sortino": 1.42, "calmar": 0.64, "max_dd": -0.205, "alpha": 0.038}},
        "oos": {"start": "2023-01-03", "end": "2025-12-31",
                "stats": {"cagr": 0.131, "sharpe": 0.98, "max_dd": -0.156, "benchmark_beta": 0.82}},
        "combined": {"start": "2018-01-02", "end": "2025-12-31",
                     "stats": {"cagr": 0.131, "sharpe": 0.99, "max_dd": -0.205}}
      },
      "active_share": 0.66,
      "capacity": {"liquidity_usd": 42000000, "impact_usd": 18000000}
    }
  ]
}
```

`performance` is **optional provenance** from Darwin's discovery run, shown on the per-strategy detail
page (`/astralanx/live/[id]`). It holds **three single-seed runs** — `training` (in-sample, with
optional `windows` for its regimes), `oos` (held-out), and `combined` (both, run end to end) — each
with a `DetailedStats` block (CAGR, volatility, Sharpe/Sortino/Calmar, max DD, rolling stress,
benchmark beta/correlation, Fama-French alpha, …). `active_share` and `capacity` are king-level. All
are dates + aggregate stats only — never the formula or weights — so they publish for **secured**
strategies too. Entries without them simply omit the breakdown. See
[subsystems/live-dashboard.md](../subsystems/live-dashboard.md) and
[subsystems/darwin-publish.md](../subsystems/darwin-publish.md).

This metadata is **not sensitive** — it describes *how the sim is run* (capital, cadence, cost
assumptions), not the formula or the basket — so it is published for secured strategies too.
`cost_model` here is the same assumption the Darwin section's Methodology page documents, so the
two stay consistent.

`cost_model` carries the full **Darwin cost model** (`paper_trading/costs.py`): `commission_bps`
and `slippage_bps` are required; `spread_ref_price`, `volume_impact_coef`, `impact_portfolio_size`,
and the `vol_*` crisis-scaling fields are optional and fall back to Darwin's engine defaults. The
simulator charges these as a per-rebalance equity haircut (turnover-scaled commission +
price-scaled slippage + sqrt volume impact), matching how the strategy was backtested in Darwin.
`impact_portfolio_size` is the **authoritative** book size the volume-impact term sizes trades
against (default Darwin's $1,000,000) — kept separate from the strategy's traded `portfolio_size`
so the impact magnitude matches the backtest regardless of the displayed capital.

## Changing the contract — checklist

1. Edit the type in `lib/data.ts`.
2. Edit the **open** writer in `paper_trading/` to emit the new shape.
3. Edit the **secured** sanitizer in `paper_trading/secured.py` (`build_secured_entry`) to match
   — and re-confirm `assert_sanitized` still rejects any `positions`/formula on secured entries.
   The private repo's `daily.yml` calls this, so the shape stays locked to `lib/data.ts` here.
4. Update any sample/fixture JSON in `public/data/`.
5. Update the tests that pin the shape (see [playbook/test-maintenance.md](../playbook/test-maintenance.md)).
6. Update this page if the contract's meaning changed.

All in one commit (the private-repo writer in its own repo, kept in lockstep).

## Related

- [open-vs-secured-strategies.md](open-vs-secured-strategies.md) — what `visibility` protects.
- [three-tier-separation.md](three-tier-separation.md) — the contract is the Tier 2 → Tier 1 boundary.
- [subsystems/live-dashboard.md](../subsystems/live-dashboard.md) — the reader side.
- [subsystems/paper-trading-updater.md](../subsystems/paper-trading-updater.md) — the open writer.
- [subsystems/secured-updater.md](../subsystems/secured-updater.md) — the secured (private) writer.

## Source files

- `public/data/benchmark.json` - the published S&P 500 benchmark snapshot.
- `paper_trading/benchmark.py` - the benchmark writer for `benchmark.json`.
- `lib/data.ts` — type definitions + typed loaders (the source of truth) (built).
- `lib/format.ts` — `%`, `$`, date formatting helpers (built).
- `public/data/portfolio.json`, `public/data/trades.json`, `public/data/strategies.json` — the published artifacts (sample data committed).
- `paper_trading/update.py` — the open writer that must match (when built).
