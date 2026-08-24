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
  its ledger/checkpoint state as a 14-day review artifact without changing the branch.
- An interrupted ledger/checkpoint commit is completed from `paper_state/.transactions/` on the next
  read. Public data is not published until state, compatibility files, hashes, and byte budgets pass.
- To audit without writing, run `python -m paper_trading.audit --strategy <id>`.
- To roll the site back, point `public/data/manifest.json` at a previously committed, validated
  content-addressed snapshot. Preserve the ledger and checkpoint; they are the authoritative record.

## Required repository settings

Protect the default branch and require the `paper-trading` and `frontend` CI jobs. Repository-hosted
settings cannot be encoded in this checkout, so verify them after creating or transferring the repo.
