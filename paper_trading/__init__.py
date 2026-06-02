"""Tier-2b open-strategy paper-trading engine (public).

This package is the *open* writer of the data contract (see `lib/data.ts` and
`docs/concepts/data-contract.md`). It evaluates published strategy formulas
against keyless daily price data, simulates a deterministic paper portfolio
(no broker, no real money, no order endpoint), and writes the open-strategy
entries of `public/data/*.json`.

The engine is intentionally *not* secret — only deployed king formulas and their
ticker weights are, and those live solely in the private secured-updater repo.
"""
