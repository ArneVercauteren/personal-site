# Concept — Paper / simulated only

The trading on this site is **simulated**. There is no broker, no real money, and no live order routing anywhere in this repo. This is both a safety property and a correctness property.

## What "paper only" means

- **No broker integration.** No Alpaca/IBKR/etc. credentials, no order endpoints, nothing that can place a real trade. (Real-money trading is listed in the plan as an explicit *out-of-scope, separate, private* future thing — it never lives here.)
- **No real money.** The portfolio starts from a configured cash balance and is marked to market against historical/daily price bars. The numbers are a simulation, not an account.
- **Deterministic and re-runnable.** Given the same deployed strategy JSONs, the same starting capital, the same cost assumptions, and the same price data, the simulator produces the same equity curve. A run can be reproduced and audited.
- **Honest costs.** Fills apply simple, explicit commission + slippage assumptions so the equity curve is realistic rather than frictionless.

## The disclaimer is part of the contract

**Every page that shows live portfolio data must carry a clear disclaimer:** *"Simulated paper portfolio, not investment advice."* This is not optional polish — it is a standing requirement from the plan's hygiene checklist. If you build or restyle a dashboard page, the disclaimer ships with it.

## Why it matters

A public page showing trading performance invites two failure modes: someone thinks it's a real track record, or someone thinks they can act on it. The disclaimer addresses the first; the "no broker, no orders" invariant addresses the second. Keep both intact.

## Where the simulation lives

All of it is **Tier 2** (`paper_trading/`), run in GitHub Actions, never on a public server:

- `prices.py` — swappable price-data adapter (keyless source to start).
- `signals.py` — evaluate each deployed strategy's signal → target holdings.
- `portfolio.py` — apply fills with costs, advance the equity curve, recompute stats.
- `update.py` — entry point; writes `public/data/*.json`.

See [subsystems/paper-trading-updater.md](../subsystems/paper-trading-updater.md).

## Related

- [public-site-is-read-only.md](public-site-is-read-only.md) — the site renders these results but never computes them.
- [three-tier-separation.md](three-tier-separation.md) — the simulation is Tier 2, offline.

## Source files

- `paper_trading/update.py`, `paper_trading/portfolio.py`, `paper_trading/signals.py`, `paper_trading/prices.py` (when built).
- The dashboard components that render the disclaimer (when built).
