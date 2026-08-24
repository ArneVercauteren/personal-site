# Task — Add an open deployed strategy

Darwin exports one scrubbed site spec; this repository owns all subsequent paper accounting and publication.
The boundary is JSON-only: do not copy Darwin caches, filesystem paths, credentials, or private strategy data.

## Steps

1. Export the strategy through Darwin's `site-spec` action and place the reviewed JSON at
   `paper_trading/strategies/<strategy-id>.json`. Keep `visibility` set to `open`; secured strategies belong in
   the private updater repository.
2. Run the Python tests. Strategy import rejects malformed schemas, internal paths, and fields outside the
   public contract.
3. Generate a migration candidate without changing accepted state:

   ```bash
   python -m paper_trading.migrate --strategy <strategy-id>
   ```

4. Review `paper_migration/<strategy-id>.candidate.json`: confirm the boundary curve, fill basket, holdings,
   hashes, and any labelled vendor-price delta. Then approve explicitly:

   ```bash
   python -m paper_trading.migrate --strategy <strategy-id> --approve --reviewer "Your Name"
   ```

5. Run `python -m paper_trading.update --strategy <strategy-id>`. It advances only unseen sessions from the
   accepted checkpoint and publishes a validated content-addressed snapshot; it never bootstraps or silently
   rewrites an accepted mark.
6. Run `python -m paper_trading.audit --strategy <strategy-id>`, `python -m paper_trading.validate_data`, and
   the frontend checks in `docs/reference/build-and-dev.md`. Inspect the dashboard and strategy route before
   committing the spec, migration evidence, ledger, checkpoint, and public snapshot together.

## Invariants

- Formula, universe, OHLCV, cost-model, and engine hashes are recorded for every review.
- Existing public history is preserved unless a separately reviewed correction event explains the change.
- The site output must conform to the [data contract](../concepts/data-contract.md).
- [Paper only](../concepts/paper-trading-only.md); disclaimer stays.

## Source files

- `schemas/strategy-spec.schema.json` — input contract.
- `paper_trading/migrate.py`, `paper_trading/update.py`, `paper_trading/audit.py` — lifecycle commands.
- `paper_state/`, `paper_ledger/`, `paper_migration/` — accepted state and review evidence.
- `public/data/manifest.json`, `public/data/snapshots/` — atomic public boundary.
