# Playbook — paper-data deployment and recovery

## Normal operation

The weekday workflow runs once at 22:30 UTC, retries the updater up to three times, runs the Python
suite and `paper_trading.validate_data`, then commits the compatibility files, immutable
`paper_ledger/`, checkpoint in `paper_state/`, and content-addressed public snapshot. The manifest is
written last. All data writers use the `paper-data-writer-main` concurrency group; push-time rebase
detects a writer from another repository instead of silently overwriting it.

GitHub's failed-workflow notification is the failed-update/rebalance alert. A separate weekday
freshness workflow fails when the last good manifest is more than four calendar days old.

## Before deploying a new open strategy

1. Validate the scrubbed spec and run `pytest paper_trading/tests -q`.
2. Run `python -m paper_trading.migrate --strategy <id>`.
3. Review `paper_migration/<id>.candidate.json`: an exact replay is preferred. If the current price
   vendor revision differs, `boundary_reconciled` must be true, the Darwin prefix/fill basket/current
   holdings must match, and the documented scale must reconcile shares/cash exactly to the published
   boundary without changing any public point.
4. A reviewer runs `python -m paper_trading.migrate --strategy <id> --approve --reviewer "Name"`.
5. Run the normal updater and `python -m paper_trading.validate_data` before committing.

## Corrections and recovery

- Never edit a JSONL event or accepted checkpoint by hand.
- Ordinary boundary hashes cover held positions; full-universe input hashes are retained on review
  events. Missing held prices stop the run as retryable data failures. A held-position boundary
  mismatch stops the updater and records a `correction_proposed` event; the failed CI job uploads
  its ledger/checkpoint state as a 14-day review artifact without changing the branch. It exits
  **3** — a status CI never retries, because the same inputs fail identically every time.
- A dividend or other distribution on a held name is **not** a revision: the raw close is unchanged,
  so the updater re-bases share counts, records `basis_rebased`, and continues without review. Only
  a move in the raw closes — a split, or a corrected print — stops the run.
- To clear a boundary price revision:
  1. `python -m paper_trading.migrate --strategy <id> --accept-revision` re-fetches the boundary
     prices, reports the mismatch and its equity delta, and writes nothing. The CI artifact is a
     convenience for reading the proposal — this command reproduces it from live prices, so a
     lapsed artifact does not block recovery.
  2. Confirm the delta is explained. An ex-dividend or split on a held name between the boundary and
     the run rewrites Yahoo's adjusted close for that session, which is benign; an unexplained delta
     is not, and should be investigated instead of accepted.
  3. `... --accept-revision --reviewer "Name"` re-stamps `price_snapshot_id` to the observed basis
     and records an immutable `correction_accepted` event. Cash, shares, and the accepted equity
     mark are left untouched, so the delta appears as a one-session step in the forward curve
     rather than a rewrite of published history. The reviewer name is published in `rebalances.json`.
- An interrupted ledger/checkpoint commit is completed from `paper_state/.transactions/` on the next
  read. Public data is not published until state, compatibility files, hashes, and byte budgets pass.
- To audit without writing, run `python -m paper_trading.audit --strategy <id>`.
- To roll the site back, point `public/data/manifest.json` at a previously committed, validated
  content-addressed snapshot. Preserve the ledger and checkpoint; they are the authoritative record.

## Required repository settings

Protect the default branch and require the `paper-trading` and `frontend` CI jobs. Repository-hosted
settings cannot be encoded in this checkout, so verify them after creating or transferring the repo.
