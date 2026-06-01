# Task — Add a dashboard chart or stat

The [dashboard](../subsystems/live-dashboard.md) is built (v1: cards + sparkline + stats + exposure bars). To add a chart or stat:

## Steps

1. **Does the data already exist in the contract?**
   - **Yes:** read it through `lib/data.ts` and build the component. No Tier-2 change needed.
   - **No:** you're changing the [data contract](../concepts/data-contract.md). Update `lib/data.ts` (reader) **and** the `paper_trading/` writer **and** the sample `public/data/*.json` in the same commit.
2. Add the component under `components/` (Recharts for richer time-series — note it needs `"use client"`; the current `Sparkline` is a dependency-free SVG server component you can follow for static charts).
3. Render it inside `components/StrategyCard.tsx` or on `app/darwin/live/page.tsx`, fed from the typed loader — never hand-parse JSON.
4. Keep the paper-only disclaimer on the page. See [concepts/paper-trading-only.md](../concepts/paper-trading-only.md).
5. Update or add a test pinning any new contract field (see [playbook/test-maintenance.md](../playbook/test-maintenance.md)).
6. `npm run build`.

## Invariants

- Components read via the [data contract](../concepts/data-contract.md), not raw fetch/parse.
- Any shape change is a both-sides, same-commit change.
- [Read-only](../concepts/public-site-is-read-only.md), [static-first](../concepts/static-first.md).

## Source files

- `components/StrategyCard.tsx`, `components/Sparkline.tsx`, `components/StatsTable.tsx`, `app/darwin/live/page.tsx`, `lib/data.ts`.
