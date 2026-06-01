# Subsystem — Scheduled job / CI cron (Tier 2b, public)

> **Status: stub.** The workflow isn't written yet. This page states what it will own; fill it in the same change that builds it.

## What this will own

The **public** GitHub Actions workflow that runs the [open-strategy updater](paper-trading-updater.md) on a schedule and commits the refreshed `public/data/*.json` back to the repo — which triggers a Vercel redeploy. This is the mechanism that makes the [static-first](../concepts/static-first.md) design work without a server.

The **secured** strategies have their *own* crons (`rebalance.yml`, `daily.yml`) in the private repo — see [secured-updater.md](secured-updater.md). This page is only the public, open-strategy job.

## Planned shape

- `.github/workflows/open-strategies-update.yml` — cron-triggered (a few times a day), plus manual `workflow_dispatch`.
- Steps: checkout → set up Python → `pip install -r paper_trading/requirements.txt` → `python -m paper_trading.update` → commit `public/data/*.json` if changed → push.

## Invariants it must respect

- **No committed secret.** If a keyed price source is ever used, the key is a GitHub Actions repo secret referenced as `${{ secrets.NAME }}` — never inlined. See [reference/env-vars.md](../reference/env-vars.md).
- **Commits data only.** The job writes `public/data/*.json` and nothing else; it never touches application code.
- **Idempotent / no-op safe.** If a run produces no change, it commits nothing.

## To fill this in

Replace this stub when the workflow exists. Document the cron cadence, the exact commit/push step, the bot identity used for commits, and any concurrency guard.

## Source files

- `.github/workflows/open-strategies-update.yml` (when built).
- `paper_trading/update.py` — what the job runs.
- Private repo `.github/workflows/{rebalance,daily}.yml` — the secured counterparts (see [secured-updater.md](secured-updater.md)).
