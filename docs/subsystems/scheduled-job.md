# Subsystem — Scheduled job / CI cron (Tier 2b, public)

> **Status: built.** See `.github/workflows/open-strategies-update.yml`.

## What it owns

The **public** GitHub Actions workflow that runs the [open-strategy updater](paper-trading-updater.md) on a schedule and commits the refreshed `public/data/*.json` back to the repo — which triggers a Vercel redeploy. This is the mechanism that makes the [static-first](../concepts/static-first.md) design work without a server.

The **secured** strategies have their *own* crons (`rebalance.yml`, `daily.yml`) in the private repo — see [secured-updater.md](secured-updater.md). This page is only the public, open-strategy job.

## Shape

- **Triggers:** one weekday cron at `30 22 * * 1-5` (UTC, after the regular US session and normal data finalization), plus manual `workflow_dispatch`.
- **Concurrency:** the shared `paper-data-writer-main` group with `cancel-in-progress: false`, also used by the universe writer. A pull/rebase immediately before push detects writers from other repositories.
- **Permissions:** `contents: write` (the job pushes a data commit).
- **Steps:** pinned checkout/setup-python actions → install `requirements-lock.txt` → retry the incremental updater up to three times → run the Python suite and public-data validator → stage compatibility data, manifest/snapshots, ledger, checkpoint, and migration evidence → rebase → commit/push only when changed.
- **Bot identity:** commits as `paper-trading-bot <actions@users.noreply.github.com>`, message `data: refresh open-strategy paper portfolio [skip ci]` (the `[skip ci]` tag avoids retriggering CI on the data commit).

## Invariants it respects

- **No committed secret.** The price source is keyless. If a keyed source were ever used, the key would be a GitHub Actions repo secret referenced as `${{ secrets.NAME }}` — never inlined. See [reference/env-vars.md](../reference/env-vars.md).
- **Commits data/state only.** The job stages `public/data`, `paper_state`, `paper_ledger`, and reviewed migration evidence; it never touches application code.
- **Idempotent / no-op safe.** If a run produces no change, the `git diff --staged --quiet` guard commits nothing.
- **Alerts without partial publication.** Native failed-workflow notifications cover updater/rebalance failure. `stale-data-alert.yml` separately fails on an old manifest, while the manifest continues to reference the last validated snapshot.

## Source files

- `.github/workflows/open-strategies-update.yml` — the workflow.
- `paper_trading/update.py` — what the job runs.
- Private repo `.github/workflows/{rebalance,daily}.yml` — the secured counterparts (see [secured-updater.md](secured-updater.md)).
