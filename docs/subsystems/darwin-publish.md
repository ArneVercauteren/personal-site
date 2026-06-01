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

## To fill this in

When the publish script is written (in Darwin), document here: the exact scrubbed JSON shape, how a king is marked "deployed", and the push mechanism (commit vs. artifact). Keep the authoritative implementation notes in the Darwin repo; this page records the *contract* from the website's side.

## Source files

- Darwin repo: `scripts/deploy_to_site.py` (new, when built), `scripts/select_on_date_yf.py` + `src/backtest/select_on_date.py` (adapted for the rebalance eval).
- Private repo: `strategies/<king>.json` + metadata — the received, scrubbed secured exports.
- This repo: `paper_trading/strategies/*.json` — open exports; `public/data/strategies.json` — published metadata.
