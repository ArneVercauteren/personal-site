# Subsystem — Paper-trading updater / engine (Tier 2b, public)

> **Status: stub.** The updater isn't built yet. This page states what it will own; fill it in the same change that builds it.

## What this will own

The Python simulator engine, and the **open**-strategy writer that runs it in the public repo.
It turns deployed strategies + price data into the JSON the site reads — the **writer** side
of the [data contract](../concepts/data-contract.md) for `visibility: "open"` entries, and the
only thing in the public repo that "trades" (on paper, in CI, no public endpoint).

The **engine is not secret** and may be open source. Secured strategies reuse this same engine
from a private repo — see [secured-updater.md](secured-updater.md) and
[open-vs-secured-strategies.md](../concepts/open-vs-secured-strategies.md).

## Planned shape

- `paper_trading/update.py` — entry point (run locally and by GitHub Actions); writes `public/data/*.json`.
- `paper_trading/prices.py` — swappable price-data adapter (keyless source to start, e.g. yfinance).
- `paper_trading/signals.py` — evaluate each deployed strategy's signal → target holdings.
- `paper_trading/portfolio.py` — apply fills with commission/slippage, advance the equity curve, recompute CAGR/Sharpe/max-DD.
- `paper_trading/strategies/<king>.json` — scrubbed king exports pushed from Darwin (Tier 3).
- `paper_trading/requirements.txt`.

## How a run works (planned, from plan §5)

1. Fetch latest daily bars for the universe (`prices.py`).
2. Re-evaluate each strategy's signal → target holdings (`signals.py`).
3. Apply fills at the next bar's open with simple costs (`portfolio.py`).
4. Append today's mark-to-market equity point; recompute stats.
5. Write `public/data/*.json`.
6. (In CI) commit the JSON → Vercel redeploys.

## Invariants it must respect

- **[Paper only](../concepts/paper-trading-only.md):** no broker, no real money, deterministic and re-runnable.
- **[Separate from Darwin](../concepts/separation-from-darwin.md):** signal evaluation is a pure-Python re-implementation (plan's option A) or a vendored, scrubbed copy — never an import into the live Darwin tree.
- **Writes the [data contract](../concepts/data-contract.md) exactly:** any shape change updates `lib/data.ts` in the same commit.
- **No committed secret:** keyless price source, or a GitHub Actions secret.

## Signal evaluation: A vs B

The plan offers two ways to evaluate signals: (A) a lightweight pure-Python re-implementation for the small deployed set, or (B) vendoring Darwin's compiler/backtester for true parity. **Default to (A)**; defer (B) unless parity drift bites. Document which one is in use when you build this.

## To fill this in

Replace this stub when `paper_trading/` exists. Document the actual module responsibilities, the cost model, the rebalance cadence, and the determinism guarantee.

## Source files

- `paper_trading/update.py`, `paper_trading/prices.py`, `paper_trading/signals.py`, `paper_trading/portfolio.py` (when built).
