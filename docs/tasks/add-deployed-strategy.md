# Task — Add a deployed strategy to the dashboard

> **Status: stub** until the [updater](../subsystems/paper-trading-updater.md) and [publish step](../subsystems/darwin-publish.md) exist. The intended recipe:

## Steps (planned)

1. **In Darwin (Tier 3):** mark the king as deployed and run the publish script, which writes a scrubbed `paper_trading/strategies/<king>.json` into this repo. See [subsystems/darwin-publish.md](../subsystems/darwin-publish.md).
2. **Verify the export is scrubbed** — DSL tree + portable metadata only, no internal paths or secrets. See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md).
3. **Run the updater locally:** `python -m paper_trading.update`. Confirm the new strategy appears in the regenerated `public/data/portfolio.json` (and `strategies.json`, `trades.json`) per the [data contract](../concepts/data-contract.md).
4. **Check the dashboard** renders the new strategy (`npm run dev`), with the paper-only disclaimer intact.
5. Commit the new strategy JSON + regenerated `public/data/*.json` together.

## Invariants

- The strategy JSON must conform to the Tier-3 → Tier-2 input contract.
- The site output must conform to the [data contract](../concepts/data-contract.md).
- [Paper only](../concepts/paper-trading-only.md); disclaimer stays.

## To fill this in

Replace with concrete field names and the exact "mark as deployed" mechanism once the updater and publish step are built.

## Source files

- `paper_trading/strategies/<king>.json`, `paper_trading/update.py`, `public/data/*.json` (when built).
