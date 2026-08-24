# Concept — Open vs secured strategies

The live dashboard renders two classes of strategy. The split is a **security boundary**, not a cosmetic label. Get it wrong and you leak the IP the whole private pipeline exists to protect.

## The two classes

| | **Open** (advertisement) | **Secured** (the real kings) |
|---|---|---|
| Count | 1–2 | the rest |
| Formula | published | **private — never published** |
| Ticker weights | published (full positions) | **private — never published** |
| Disclosed | formula + positions + curve + stats | curve + stats + **aggregate exposure only** |
| Runs in | the **public** repo's Actions (Tier 2b) | a **private** repo's Actions (Tier 2a) |
| Purpose | transparent, reproducible — builds trust | show a real track record without leaking the basket |

## What "aggregate exposure only" means

For a secured strategy the site may show **sector / asset-class allocation** — e.g.
"Technology 32%, Healthcare 18%, Energy 9%" — but **never** the individual tickers or their
weights. The private updater maps tickers → sector, sums the weights, and publishes only the
grouped result. The ticker-level vector never leaves the private repo.

Why this is safe: an equity curve and a sector breakdown are both lossy projections of the
underlying weight vector. You cannot reconstruct "AAPL 4.0%, MSFT 3.1%, ..." from "Technology
32%" plus a performance line. The basket stays secret while the performance stays honest.

## The hard rules

1. **A secured entry in `public/data/*.json` must never contain `positions` or any formula.**
   The `visibility` field gates this. See [data-contract.md](data-contract.md).
2. **Secret formulas and weights live only in the private repo.** They never enter the public
   repo, not even in git history. See [separation-from-darwin.md](separation-from-darwin.md).
3. **The private→public push copies only the sanitized snapshot.** It never copies
   `strategies/` or `weights/`.
4. **The evaluation engine is not secret** — only the deployed king formulas and their weights
   are. The engine can live in the public `paper_trading/` package (good advertisement).

## Where each class is computed

- **Open** → `paper_trading/` in the public repo, run by `open-strategies-update.yml`. Full
  JSON committed directly.
- **Secured** → the private repo's `rebalance.yml` (formula → weights) and `daily.yml` (mark to
  market → curve + stats + exposure), which pushes the sanitized JSON to the public repo. See
  [subsystems/secured-updater.md](../subsystems/secured-updater.md).

## Related

- [data-contract.md](data-contract.md) — the `visibility`-gated JSON shape.
- [three-tier-separation.md](three-tier-separation.md) — Tier 2a (private) vs 2b (public).
- [separation-from-darwin.md](separation-from-darwin.md) — secrets stay out of the public repo.
- [paper-trading-only.md](paper-trading-only.md) — both classes are simulated.

## Source files

- `lib/data.ts` — the `visibility` discriminator.
- `paper_trading/` — open-strategy engine.
- Private repo `personal-site-trading` — secured pipeline.
