# Subsystem — Darwin → site publish step (Tier 3)

> **Status: stub.** The publish script isn't written yet. It lives in the **Darwin repo**, not this one. This page states what it will own and the contract it must honour.

## What this will own

The single, one-way coupling between Darwin and this website: a script in the **Darwin** repo that selects which king strategies are "deployed to the live site", scrubs them to portable JSON, and pushes them into this repo's `paper_trading/strategies/`.

## Planned shape (in the Darwin repo)

Adapt existing tooling rather than writing from scratch:

- **`scripts/select_on_date_yf.py`** (wrapping `src/backtest/select_on_date.py`) — already
  evaluates a strategy formula on a given date via pure-Python feature computation + keyless
  yfinance (no feature store, no native engine, no secrets). This is the **rebalance
  evaluator** the secured pipeline reuses; it *is* "option A". `scripts/reconcile_portfolio_to_target.py`
  is a secondary reference for turning picks into weights.
- **`scripts/deploy_to_site.py`** (new) — the one-shot deploy action:
  1. Scrub the chosen king to a portable formula JSON (no internal paths / secrets).
  2. Attach non-secret metadata: `portfolio_size`, `base_currency`, `rebalance_cadence_days`,
     `visibility`, `cost_model`, `blurb` (see [data-contract.md](../concepts/data-contract.md)).
  3. Push formula + metadata into the **private** repo's `strategies/` (secured) — or PR into
     the **public** repo's `paper_trading/strategies/` (open).
  4. Stamp the rebalance cadence: write `rebalance_cadence_days` + `next_rebalance_date` so the
     private repo's daily `rebalance.yml` rebalances this strategy when due (per-strategy
     cadence, one shared workflow). See [secured-updater.md](secured-updater.md).

## The contract it must honour

- **One-way push, JSON only.** Darwin writes JSON into this repo; this repo never calls back into Darwin. See [concepts/three-tier-separation.md](../concepts/three-tier-separation.md).
- **Scrubbed output.** The exported JSON contains the DSL tree + portable metadata only — **no** internal absolute paths, **no** internal-only fields, **no** secrets. See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md).
- **This repo never imports Darwin** to read these files. The updater consumes the scrubbed JSON as plain data.

## What this repo guarantees in return

- It treats `paper_trading/strategies/*.json` as an input contract: a stable, documented JSON shape the [updater](paper-trading-updater.md) knows how to evaluate.

## The export format (the exact JSON the site needs)

A deployed strategy is one `*.json` file matching the strategy-spec the updater reads
(`paper_trading/update.py` / the secured `update_secured.py`). Same shape for open and secured;
`visibility` and *where it's pushed* differ. Exact shape:

```json
{
  "id": "balanced_king_v3",
  "name": "Balanced King",
  "visibility": "secured",                       // "open" → public repo; "secured" → private repo
  "blurb": "Balanced risk/return king from epoch 7.",
  "deployed_on": "2026-06-02",                    // LIVE-since marker (forward paper-trading begins)
  "backfill_start": "2018-01-02",                 // optional: curve start for a one-time backfill
                                                  //   (earlier than deployed_on; the sim runs from here)
  "next_rebalance_date": "2026-07-14",            // deployed_on + cadence (secured only needs this)
  "performance": {                                // optional: three single-seed runs (see below)
    "training": {"start": "2018-01-02", "end": "2022-12-30",
                 "windows": [{"start": "2018-01-02", "end": "2020-12-31", "label": "Regime 1"}],
                 "stats": {"cagr": 0.131, "total_return": 0.857, "volatility": 0.171, "sharpe": 0.99,
                           "sortino": 1.42, "calmar": 0.64, "max_dd": -0.205, "alpha": 0.038, "...": 0}},
    "oos": {"start": "2023-01-03", "end": "2025-12-31",
            "stats": {"cagr": 0.131, "sharpe": 0.98, "max_dd": -0.156, "benchmark_beta": 0.82, "...": 0}},
    "combined": {"start": "2018-01-02", "end": "2025-12-31",
                 "stats": {"cagr": 0.131, "sharpe": 0.99, "max_dd": -0.205, "...": 0}}
  },
  "darwin_equity_curve": [{"d": "2018-01-02", "v": 100000.0}],  // optional: combined train+OOS curve
  "active_share": 0.66,                            // king-level liquidity/holdings measures
  "capacity": {"liquidity_usd": 42000000, "impact_usd": 18000000},
  "portfolio_size": 100000,
  "base_currency": "USD",
  "rebalance_cadence_days": 42,
  "cost_model": {                                 // the Darwin run's actual cost config (see below)
    "commission_bps": 5.0, "slippage_bps": 5.0,
    "spread_ref_price": 50.0, "volume_impact_coef": 0.5, "impact_portfolio_size": 1000000,
    "vol_scaled_cost_enable": true, "vol_cost_k": 0.75,
    "vol_cost_realized_window": 63, "vol_cost_long_window": 252, "vol_cost_mult_max": 3.0
  },
  "universe": [],                                 // usually empty → resolves to the shared universe
                                                  //   (see subsystems/universe.md); set a list to pin one
  "formula": { "mode": "top_n", "top_n": 8, "kind": "...", "children": [] },  // BOTH open + secured
  "formula_ref": "/projects/darwin"                // open only: link to the public writeup
}
```

**Both open and secured exports carry `formula`** — the updater *runs* the tree, so the file the
private repo holds must contain it. The security boundary is enforced **later**, at publish time:
the secured pipeline strips the formula/positions from the *public snapshot* (`assert_sanitized`),
never letting them reach the public site. The only export-time differences are `visibility` and the
open-only public `formula_ref`. The secured file is kept secret simply by living **only in the
private repo**; the open file's formula is published for auditability.

**`backfill_start`, `performance`, `darwin_equity_curve`, `active_share`, and `capacity` are optional
and publish for both visibilities** — they are dates and aggregate performance numbers, never the
formula or weights, so they clear the security boundary. They drive the per-strategy detail page
(continuous training → OOS → live curve with shaded bands, plus detailed stat panels).
`darwin_equity_curve` is the authoritative combined training+OOS curve from Darwin; when it is
present, the updater uses that prefix directly and only fetches Yahoo data from the prefix's final
date onward.

### `performance` — three single-seed runs

To give the site authoritative figures, the exporter runs **three deterministic (single-seed)
backtests** of the frozen king tree, all at the deployed `cost_model`, and records each run's full
diagnostics:

1. **`training`** — over the in-sample window(s) the formula was fit on. Set `windows` to the
   constituent regimes when training spans more than one stretch; `start`/`end` is the envelope.
2. **`oos`** — over the held-out out-of-sample window.
3. **`combined`** — over training **and** OOS together. Run end to end (a fresh backtest over the
   union span), **not** stitched from the two halves — cross-boundary figures like max drawdown and
   Sharpe aren't additive.

The combined run's equity curve is exported as top-level `darwin_equity_curve`, scaled to the
deployed paper `portfolio_size`. The updater stitches later Yahoo-backed simulation onto that curve
instead of re-simulating Darwin's historical training+OOS window with Yahoo prices.

Each run's `stats` is a `DetailedStats` block. Map Darwin's existing backtest diagnostics into it:

| `DetailedStats` field | Darwin source (per-run backtest diagnostic) |
|---|---|
| `cagr`, `total_return`, `volatility`, `max_dd`, `max_dd_duration_days` | core return/risk summary |
| `sharpe`, `sortino`, `calmar` | risk-adjusted ratios |
| `win_rate`, `best_year`, `worst_year` | period/calendar-year breakdown |
| `worst_rolling_3y_cagr`, `worst_rolling_5y_cagr`, `rolling_sharpe_min` | rolling-window stress |
| `benchmark_beta`, `benchmark_corr`, `alpha`, `information_ratio` | benchmark relationship + Fama-French alpha |

`active_share` and `capacity` (`liquidity_usd` / `impact_usd`) are king-level (current basket /
liquidity), emitted once. Omit any field you don't have — the detail page renders only what's present.
See [data-contract.md](../concepts/data-contract.md) and [live-dashboard.md](live-dashboard.md).

The `formula` tree is exactly what `paper_trading`'s vendored evaluator already consumes, so the
exporter should reuse Darwin's existing serializer **`src/dsl/serialize.py::to_dict(strategy)`**
(it emits the `{mode, top_n, kind, name, params, children}` tree, including the top-level
selection mode) rather than hand-building JSON.

### cost_model — pull from the run, don't hard-code

To stay faithful to the backtest the king was selected on, the exporter reads the **actual** cost
config of that run, not literals:

| Field | Darwin source |
|---|---|
| `commission_bps` | the run's `--cost-bps` (CLI default **5.0**) |
| `slippage_bps` | the run's `--slip-bps` (CLI default **5.0**) |
| `spread_ref_price`, `volume_impact_coef`, `impact_portfolio_size` | `cfg.realism` (defaults 50.0, 0.5, **$1,000,000**) |
| `vol_scaled_cost_enable`, `vol_cost_k`, `vol_cost_realized_window`, `vol_cost_long_window`, `vol_cost_mult_max` | `cfg.backtest_diag` (defaults true, 0.75, 63, 252, 3.0) |

**Impact sizing (resolved).** The volume-impact term sizes trades against the authoritative
`cost_model.impact_portfolio_size`, **not** the strategy's traded `portfolio_size`. The export
emits it from `cfg.realism.portfolio_size` (Darwin's **$1,000,000** default), so live paper impact
matches the backtest regardless of the displayed book. Override it per-spec only if you deliberately
want a different impact assumption.

## UI export button (Darwin frontend)

The Darwin UI already has a generic export dropdown — **`ui/frontend/components/ExportMenu.tsx`** —
whose items are either a synchronous backend download (`path`) or an async job. Adding "deploy to
site" is small:

1. **Backend (FastAPI):** `GET /api/strategies/{id}/site-spec` in **`ui/backend/routes/exports.py`**,
   backed by **`ui/backend/exports/site.py`**. It loads the king (`adapters.get_strategy`), uses the
   strategy's round-trippable `raw_json` tree, reads the engine's cost config + `rebalance_days`
   metadata, and returns the spec above as a JSON download. Query params: `visibility=open|secured`,
   `universe` (comma-separated), `portfolio_size`, `commission_bps`, `slippage_bps`, `blurb`,
   `formula_ref`. Both variants include `formula`; secured just omits the public `formula_ref`.
2. **Frontend:** two `ExportItem`s under a "Deploy to site" group in `StrategyDrawer.tsx`'s
   `ExportMenu` — "Open strategy (public repo)" and "Secured strategy (private repo)" — each a
   direct download from the endpoint with the matching `visibility`.
3. **Where it lands:** the downloaded file is dropped into the **public** repo's
   `paper_trading/strategies/` (open) or the **private** repo's `strategies/` (secured). A later
   `scripts/deploy_to_site.py` can automate that placement; the button gives the correct file today.
   `universe` is normally left empty — it resolves to the shared self-refreshing universe
   ([universe.md](universe.md)) so a king deployed once stays current; set a list only to pin one.
   `portfolio_size` is the deploy-time book size the operator sets in the file.

**Status: built** (Darwin repo) — `ui/backend/exports/site.py`, the `site-spec` route, and the two
`StrategyDrawer` menu items. This keeps Darwin's UI as the single deploy surface and produces the
*exact* spec the updater already runs — no second format to maintain.

## To fill this in

When `scripts/deploy_to_site.py` / the `fmt=site` endpoint are written (in Darwin), document here:
how a king is marked "deployed", and the push mechanism (commit vs. artifact). Keep the
authoritative implementation notes in the Darwin repo; this page records the *contract* from the
website's side.

## Source files

- Darwin repo: `scripts/deploy_to_site.py` (new, when built), `scripts/select_on_date_yf.py` + `src/backtest/select_on_date.py` (adapted for the rebalance eval).
- Private repo: `strategies/<king>.json` + metadata — the received, scrubbed secured exports.
- This repo: `paper_trading/strategies/*.json` — open exports; `public/data/strategies.json` — published metadata.
