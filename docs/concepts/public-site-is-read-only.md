# Concept — The public site is read-only

The single most important property of Tier 1 (the public Next.js site): **it renders, it never acts.**

## What this means concretely

- **No trades.** The site never places, simulates, or routes an order. All trading — even the paper simulation — happens in Tier 2, offline, in CI.
- **No credentials.** The site holds no broker keys, no API keys, no write tokens. There is nothing in the deployed bundle that could move money or mutate external state.
- **No write/order endpoints.** Routes under `app/api/` (if any are ever added) are read-only or absent. There is no endpoint a visitor could POST to that causes a trade, a recompute, or a credentialed call.
- **The site only reads pre-computed JSON.** Dashboard pages load `public/data/*.json` — snapshots that Tier 2 already computed and committed. The site does no market-data fetching of its own at request time.

## Why it's an invariant

A public website is the most-attacked surface you own. If it cannot trade and holds no secret, then a full compromise of the site leaks **nothing of value** and can move **no money**. That property is worth protecting deliberately, not by accident.

## How to keep it

- Before adding any server-side route, ask: does this need a secret, or can it cause a side effect on an external system? If yes, it does **not** belong in Tier 1. Push it to Tier 2 (the CI updater) or Tier 3 (the private Darwin box).
- Keep all data-fetching for the dashboard at **build time / commit time**, not request time.
- If you ever genuinely need request-time dynamic data (the optional upgrade in the plan's §7), it goes in a **separate** service with its own credentials, never folded back into the public site bundle.

## Related

- [three-tier-separation.md](three-tier-separation.md) — where the acting actually happens.
- [paper-trading-only.md](paper-trading-only.md) — even the simulation never touches a broker.
- [separation-from-darwin.md](separation-from-darwin.md) — no secrets in the repo at all.

## Source files

- `app/` — the public site; audit that nothing here reads a credential or writes externally.
- `app/api/` — only if it exists; must stay read-only.
