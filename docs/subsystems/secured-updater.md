# Subsystem — Secured updater (Tier 2a, private repo)

> **Status: stub.** Lives in a **separate private repo** (`personal-site-trading`), not this one. This page records the contract it must honour from the public side.

## What this owns

The secured half of the paper-trading pipeline: it holds the secret king formulas and the
weights they produce, runs both the rebalance and the daily mark automatically, and publishes
**only a sanitized snapshot** (equity curve + stats + aggregate exposure) into the public
repo. It is the writer for every `visibility: "secured"` entry in the [data contract](../concepts/data-contract.md).

## Planned shape (private repo)

```
personal-site-trading/   (PRIVATE)
├─ strategies/            # secret king formulas + per-strategy metadata (optionally encrypted)
├─ weights/              # computed target weights (committed privately)
├─ ticker_sectors.json   # ticker → sector/asset-class map
└─ .github/workflows/
   ├─ rebalance.yml       # DAILY cron: rebalance strategies whose next_rebalance_date is due
   └─ daily.yml           # DAILY cron: mark to market → sanitize → push to public repo
```

The evaluation engine is **reused from the public repo's `paper_trading/`** (submodule or
`pip install git+…`) — the engine is not secret. The rebalance specifically reuses Darwin's
**`src/backtest/select_on_date.py`** logic (the same code `select_on_date_yf.py` wraps): pure
Python, keyless yfinance, no feature store. The private repo adds only data (formulas, weights,
metadata, sector map) and the two workflows.

**The sanitizer is also in the shared engine, not the private repo.** Turning ticker `positions`
into aggregate `exposure` is not secret (only the formulas/weights are), and the data contract
requires it to stay version-locked to `lib/data.ts`. So it lives in `paper_trading/secured.py`
— `aggregate_exposure()`, `build_secured_entry()`, and an `assert_sanitized()` leak guard — unit
tested in the open (`paper_trading/tests/test_secured.py`). `daily.yml` just calls
`build_secured_entry(sim, spec, sector_map)` and pushes the result. The per-strategy cadence
check (`is_rebalance_due` / `advance_next_rebalance`) lives there too.

## Per-strategy cadence (no global rebalance schedule)

Each strategy carries `rebalance_cadence_days` + `next_rebalance_date` in its metadata (stamped
at deploy time — see [darwin-publish.md](darwin-publish.md)). `rebalance.yml` runs **daily** and
rebalances exactly the strategies whose `next_rebalance_date` is due, then advances each by its
cadence. One workflow serves many strategies at independent ~1–2-month cadences.

## The contract it must honour

1. **Publish performance + aggregate exposure only.** Map tickers → sector, sum weights, drop
   the ticker-level vector. The sanitized JSON has **no** `positions`, **no** formula. See
   [open-vs-secured-strategies.md](../concepts/open-vs-secured-strategies.md).
2. **Push only the sanitized snapshot** to the public repo (via deploy key / fine-grained PAT
   in an Actions secret). Never push `strategies/` or `weights/`.
3. **Match the [data contract](../concepts/data-contract.md)** for secured entries; keep the
   sanitizer in lockstep with `lib/data.ts`.
4. **Stay automatic and PC-independent.** Both crons run in GitHub Actions; the rebalance
   re-evaluates a *fixed* formula, so Darwin (Tier 3) is involved only when a king is deployed.

## To fill this in

When the private repo exists, document: the cron cadences, the sanitizer, the sector-mapping
source, the encryption-at-rest choice, and the push mechanism. Keep the authoritative
implementation notes in the private repo; this page records the *contract* from the public
side.

## Source files

- Private repo `personal-site-trading`: `strategies/`, `weights/`, `ticker_sectors.json`, `.github/workflows/{rebalance,daily}.yml` (when built).
- This repo: `paper_trading/` (the shared engine), `paper_trading/secured.py` (sanitizer + cadence helpers, built), `paper_trading/tests/test_secured.py` (the leak-boundary tests, built), `public/data/*.json` (the received sanitized snapshot).
