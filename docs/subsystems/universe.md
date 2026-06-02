# Subsystem — Tradable universe (self-refreshing)

> **Status: built.** `paper_trading/universe.py`, `paper_trading/update_universe.py`,
> `.github/workflows/universe-refresh.yml`, `public/data/universe.json` (built monthly).

## What this owns

The current set of tickers each deployed strategy picks from at every rebalance. It is built
from **public, keyless** sources and the **same filters Darwin uses**, and it refreshes on a
schedule — so it stays current independent of how stale Darwin's data is or how often a king is
(re)deployed.

## Why not snapshot Darwin's universe

A king is evolved against Darwin's curated (Tiingo) universe. Freezing that list at deploy time
would inherit **Darwin's data age**: a king deployed off six-month-old data could never hold a
ticker listed since, and re-deploying just to refresh the universe is the wrong coupling. It
would also pull a keyed paid feed + Darwin's data into the public repo, breaking
[separation-from-darwin](../concepts/separation-from-darwin.md) and
[static-first](../concepts/static-first.md). So the universe is decoupled from Darwin entirely.

## How it's built (three steps, `universe.py`)

1. **Listings — Nasdaq Trader symbol directory.** `nasdaqlisted.txt` + `otherlisted.txt`: every
   NYSE / NASDAQ / AMEX symbol, updated each trading day, free + keyless, with ETF / test-issue
   flags. yfinance has no listing endpoint, so the symbol list comes from the exchanges' own
   files, not yfinance.
2. **Symbol filters.** Drop test issues, warrants / units / rights / preferred, and
   leveraged / inverse products. Regexes are vendored from Darwin's `src/data/ticker_filtering.py`.
3. **Liquidity / price.** Keep last close ≥ `min_price` ($10) and trailing median dollar volume
   ≥ `min_adv` ($5M), rank by liquidity, cap to `cap` (default 1,200). These are Darwin's
   `FinancialRealism` thresholds — the same ones [`darwin_eval/eligibility.py`](paper-trading-updater.md)
   re-applies at **every rebalance**, so names that drift illiquid still drop out between refreshes.

## Cadence — heavy work monthly, daily stays light

`update_universe.py` (the monthly `universe-refresh.yml` cron) does steps 1–3 — fetching bars for
a few thousand names is the expensive part — and commits `public/data/universe.json`. The
**daily** updater never rebuilds it; it just reads the committed file via `resolve_universe`. So
the thousands of fetches happen ~monthly, not daily, keeping the site cheap and CI reliable.

## How a strategy gets its universe

`universe.resolve_universe(spec)`:

- **Explicit** `universe` list on the spec → used verbatim (e.g. the `open_momentum_v1` demo with
  its hand-picked basket).
- **Omitted or empty** (the normal case for a deployed king) → the shared `universe.json`.

So a king is deployed **once**; new tickers flow in via the monthly refresh, not via re-deploying
from stale Darwin. The Darwin "deploy to site" export therefore doesn't need to embed a universe —
leaving it empty resolves to the shared file.

## Fidelity note

This is not bit-identical to Darwin's curated Tiingo universe (different vendor, different
point-in-time) — but it is the same *kind* of universe with the same filters, and being current
is the point: Darwin's frozen universe is the thing that goes stale for a forward paper book.

## `universe.json` shape

```json
{
  "as_of": "2026-06-01",
  "source": "nasdaqtrader",
  "filters": {"min_price": 10.0, "min_median_dollar_volume": 5000000.0, "cap": 1200, "exclude_etf": false},
  "count": 1200,
  "tickers": ["AAPL", "MSFT", "..."]
}
```

It is **updater data**, not part of the site's read contract (`lib/data.ts`) — the public site
never renders it. Env overrides for the build: `UNIVERSE_CAP`, `UNIVERSE_MIN_PRICE`,
`UNIVERSE_MIN_ADV`, `UNIVERSE_EXCLUDE_ETF`, `UNIVERSE_FETCH_CHUNK`, `UNIVERSE_FETCH_PAUSE`.

## Polite fetching + rate-limit handling

The liquidity step is built to stay under Yahoo's rate limit (the `YFRateLimitError` you'll
otherwise see), since yfinance fetches per-ticker and bursts easily:

- **Rate-limited session.** Requests go through a `requests_ratelimiter` session capped at
  `DEFAULT_REQUESTS_PER_SEC` (4/s) — the yfinance-recommended fix. If the package isn't installed
  the build falls back to sequential fetch + pauses (gentler but slower).
- **Sequential, batched, paced.** `threads=False`, `UNIVERSE_FETCH_CHUNK` symbols per batch
  (default 120), `UNIVERSE_FETCH_PAUSE`s between batches (default 1.5).
- **Retry the missing subset.** yfinance doesn't raise on a per-ticker rate-limit — it returns that
  name empty — so the build detects which requested symbols are missing and re-fetches **only
  those** with back-off (default 3 rounds). Rate-limited names recover; genuinely dead ones don't.
- **Retention guard.** If a run yields fewer than `MIN_RETENTION` (60%) of the previous universe's
  tickers, it's treated as a rate-limited failure: the build **raises** rather than overwrite the
  committed `universe.json` with a husk. Re-run (or lower the rate) and it recovers.

## Skip-list — remembering dead symbols

The listings file contains thousands of delisted / preferred / bad symbols (e.g. `AAAD`, `FBYDP`)
that never return data. To avoid re-fetching them every month, symbols that return no usable data
are recorded in **`public/data/universe_skip.json`** as `{symbol: last_failed_date}` and excluded
from the next build's fetch. Entries **expire after `SKIP_TTL_DAYS` (180)** so a symbol that
relists gets re-checked. This is the only cross-run "memory" the builder keeps — the universe
itself is still a full rebuild each month (liquidity must be recomputed from fresh prices). The
monthly workflow commits `universe_skip.json` alongside `universe.json`. The 120-minute job timeout
absorbs the pauses.

## Source files

- `paper_trading/universe.py` — fetch / parse / filter / rank / resolve (built).
- `paper_trading/update_universe.py` — monthly entry point (built).
- `.github/workflows/universe-refresh.yml` — monthly cron (built).
- `paper_trading/tests/test_universe.py` — offline tests for the pure functions (built).
- `public/data/universe.json` — the committed shared universe (written by the monthly job).
- `public/data/universe_skip.json` — persistent skip-list of dead symbols (TTL-pruned).
- Consumed by `paper_trading/update.py` (open) and the private repo's `update_secured.py` (secured).
