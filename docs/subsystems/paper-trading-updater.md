# Subsystem — Paper-trading updater / engine (Tier 2b, public)

> **Status: built.** The open-strategy engine lives in `paper_trading/` and is run by [`open-strategies-update.yml`](scheduled-job.md).

## What it owns

The Python simulator engine, and the **open**-strategy writer that runs it in the public repo.
It turns deployed strategies + price data into the JSON the site reads — the **writer** side
of the [data contract](../concepts/data-contract.md) for `visibility: "open"` entries, and the
only thing in the public repo that "trades" (on paper, in CI, no public endpoint).

The **engine is not secret** and may be open source. Secured strategies reuse this same engine
from a private repo — see [secured-updater.md](secured-updater.md) and
[open-vs-secured-strategies.md](../concepts/open-vs-secured-strategies.md).

## Module responsibilities

- `paper_trading/update.py` — entry point (`python -m paper_trading.update`). Loads strategy
  specs, runs the sim, and **merges** the results into `public/data/*.json` by id (see
  "Merge, not overwrite" below). Run locally or by GitHub Actions. For local debugging, pass
  `--strategy <id>` (repeatable / comma-separated) or set `PAPER_TRADING_STRATEGY=<id>` to update
  only selected open entries.
- `paper_trading/benchmark.py` — builds `public/data/benchmark.json`. The scheduled updater
  refreshes the SPY-backed S&P 500 curve from the same keyless price adapter; the CLI still accepts
  a local CSV for one-off historical imports.
- `paper_trading/prices.py` — keyless price adapter. `get_ohlcv(...)` → long-format OHLCV (what
  the DSL evaluator consumes); `get_price_history(...)` → adjusted `(opens, closes)` wide frames
  (the simulator's accounting). `PAPER_TRADING_SYNTHETIC=1` swaps in deterministic synthetic bars
  for offline dev/tests; CI never sets it, so committed data always comes from real prices. Yahoo
  fetch chunks are cached under `.cache/paper_trading/ohlcv` by default so interrupted local runs can
  resume completed chunks; set `PAPER_TRADING_PRICE_CACHE=0` to bypass it or
  `PAPER_TRADING_PRICE_CACHE_DIR=<path>` to move it.
- `paper_trading/signals.py` — two evaluation paths. `evaluate(signal, closes, asof)` is the
  built-in **option A** momentum rule (`cross_sectional_momentum`). `evaluate_formula(...)` runs a
  real Darwin king's **DSL tree** via the vendored evaluator; `formula_state_features(...)` reports
  which portfolio-state features a formula needs.
- `paper_trading/darwin_eval/` — the **vendored, scrubbed copy of Darwin's pure-Python evaluator**
  (`select_on_date` + `select_helpers` + `tree_eval` + `eligibility` + `indicator_constants` +
  `dsl_compat`). A copy, not an import (see [separation-from-darwin.md](../concepts/separation-from-darwin.md)).
  `select_tickers_on_date` gains a `portfolio_state_override` hook for injected state.
- `paper_trading/portfolio_state.py` — `PortfolioState`, an exact port of the engine's
  (`native_eval.c`) path-dependent feature semantics: drawdown, invested/cash/holdings, and the
  trailing turnover/volatility/hit-rate ring buffers (cap 64, sample-std, hit-rate).
- `paper_trading/portfolio.py` — `simulate(strategy, opens, closes, prices_long=None)` dispatches
  on the spec: a `formula` (DSL tree) → `_simulate_dsl` (real evaluator + engine-faithful state
  threading); a `signal` block → `_simulate_signal` (momentum). Both rebalance on cadence (filled
  at the **next** open), mark daily, and return curve/stats/positions/trades.
- `paper_trading/strategies/<id>.json` — open strategy specs (a `formula` DSL tree *or* a `signal`
  block, plus §6.4 metadata and a `universe`). Open formulas only; secured kings never live here.
- `paper_trading/requirements.txt` — yfinance, pandas, numpy. `requirements-dev.txt` adds pytest.

## DSL path — real king formulas + engine-faithful state

For a `formula` spec the simulator evaluates the **actual Darwin DSL tree** each rebalance via the
vendored `select_tickers_on_date`. The "prior weights" fed in are the **drifted actual** holdings
(shares×price/equity) at the rebalance bar — exactly how the engine carries weights buy-and-hold
between rebalances. Path-dependent **portfolio-state features** are computed by `PortfolioState`
(turnover pushed at each rebalance, period-return + equity peak at each period close) and injected
via `portfolio_state_override`, so a formula referencing `current_portfolio_drawdown`,
`trailing_portfolio_turnover_6`, etc. sees engine-consistent values.

**Parity boundary (what's guaranteed):** selection + target weights are *bit-exact* with Darwin's
own evaluator (gated by `tests/test_evaluator_parity.py`); portfolio-state features match the
engine's definitions (gated by `tests/test_portfolio_state.py`). The **equity curve** now charges
Darwin's full cost model — turnover-scaled commission, price-scaled slippage, sqrt volume impact,
and the crisis-aware volatility multiplier (`costs.py`, gated by `tests/test_costs.py`) — so paper
costs match the backtest the strategy was selected on. Market segmentation is disabled (global
cross-sectional rank); `market_*` features need a benchmark series (v1 passes none → those features
are NaN, handled).

## How a run works

1. For each spec in `paper_trading/strategies/*.json`, resolve its universe
   (`universe.resolve_universe` — the spec's explicit list, else the shared self-refreshing
   `public/data/universe.json`; see [universe.md](universe.md)) and choose the Yahoo-backed
   simulation start. If Darwin exported `darwin_equity_curve`, that authoritative training+OOS
   prefix is used directly and Yahoo starts at the prefix's final date; otherwise Yahoo starts at
   `backfill_start` or `deployed_on`. Daily bars are fetched over `[simulation_start − warmup,
   today]` via `prices.get_ohlcv`. DSL warmup is sized from the formula's longest feature window.
   Each successful Yahoo chunk is written to the local OHLCV cache immediately, before simulation
   starts, so an interrupted fetch phase can reuse completed chunks on the next run.
2. Re-evaluate on each rebalance date → target holdings: the DSL tree via the vendored evaluator
   (`signals.evaluate_formula`) or the momentum rule (`signals.evaluate`).
3. Apply fills at the next bar's open, then charge the Darwin cost haircut for that rebalance
   (`portfolio.simulate` + `costs.py`).
4. Mark to market daily; stitch onto any Darwin curve prefix; recompute CAGR / Sharpe / max-DD.
5. Merge the open entries into `public/data/{portfolio,strategies,trades}.json`.
6. Refresh `public/data/benchmark.json` from the SPY-backed S&P 500 proxy through the same end date.
7. (In CI) commit the JSON if it changed → Vercel redeploys.

## Cost model

Darwin-faithful, in `paper_trading/costs.py` (ported from Darwin's `native_eval.c` cost block and
`cost_models.py`). At each rebalance the simulator fills to target weights cost-free at the open,
then applies a multiplicative **equity haircut**:

```
turnover    = Σ |target_w − prev_w|
haircut      = (commission_bps·m + slippage_bps·m·price_scale)/1e4 · turnover   # commission + price-scaled slippage
             + Σ_j dw_j · volume_impact_coef · sqrt(dw_j·impact_portfolio_size / adv_j)   # sqrt market impact
equity      *= (1 − haircut)
```

where `price_scale = max(spread_ref_price / harmonic_mean_price, 0.1)` (cheaper books pay more),
`adv_j` is the review-date dollar volume (`raw_close × volume`), and `m` is the crisis-aware
volatility multiplier `clip(1 + k·sqrt(realized_vol/long_vol), 1, mult_max)`. Parameters come from
each spec's `cost_model`; omitted ones use Darwin's engine defaults. These are the **same**
assumptions the Darwin Methodology page documents (plan §6.5).

## Rebalance cadence

Per strategy, via `rebalance_cadence_days` in its spec. `portfolio.simulate` snaps each
scheduled calendar date to the next trading day. (The private secured pipeline drives cadence
the same way via a daily cron — see [secured-updater.md](secured-updater.md).)

## Merge, not overwrite

`portfolio.json`, `strategies.json`, and `trades.json` are **shared** between the open writer
(this repo) and the secured writer (the private repo). `update.py` only rewrites entries whose
`id` belongs to a local open spec and preserves all others, so the two writers never clobber
each other's data. The file-level `as_of` advances to the latest open bar date.

## Determinism

Historical daily bars are fixed once published, so a given price history always yields the same
curve, stats, and positions — the only non-determinism is the moving "today" edge of the data.
Verified offline with `PAPER_TRADING_SYNTHETIC=1` (two runs produce byte-identical JSON).

## Invariants it respects

- **[Paper only](../concepts/paper-trading-only.md):** no broker, no real money, deterministic and re-runnable.
- **[Separate from Darwin](../concepts/separation-from-darwin.md):** the DSL evaluator is a *vendored, scrubbed copy* (`darwin_eval/`), not an import into the live Darwin tree; the only Darwin import is the test-only, skipped-in-CI parity gate.
- **Writes the [data contract](../concepts/data-contract.md) exactly:** matches the types in `lib/data.ts`; any shape change updates the reader in the same commit.
- **No committed secret:** keyless price source (a GitHub Actions secret would be used if a keyed source were ever needed).

## Tests

- `paper_trading/tests/test_evaluator_parity.py` — bit-exact vs Darwin's `select_tickers_on_date` (skipped without a local Darwin checkout; set `DARWIN_REPO`).
- `paper_trading/tests/test_portfolio_state.py` — `PortfolioState` semantics vs the `native_eval.c` definitions.
- `paper_trading/tests/test_simulate_dsl.py` — DSL sim integration, determinism, and state injection.
- Run: `python -m pytest paper_trading/tests/ -q`.

## Source files

- `paper_trading/update.py`, `paper_trading/benchmark.py`, `paper_trading/prices.py`, `paper_trading/signals.py`, `paper_trading/portfolio.py`, `paper_trading/portfolio_state.py`
- `paper_trading/darwin_eval/` — vendored scrubbed DSL evaluator.
- `paper_trading/strategies/open_momentum_v1.json` — the first open spec (momentum).
- `paper_trading/requirements.txt`, `paper_trading/requirements-dev.txt`
