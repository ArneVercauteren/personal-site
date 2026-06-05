# Subsystem — Scheduled job / CI cron (Tier 2b, public)

> **Status: built.** See `.github/workflows/open-strategies-update.yml`.

## What it owns

The **public** GitHub Actions workflow that runs the [open-strategy updater](paper-trading-updater.md) on a schedule and commits the refreshed `public/data/*.json` back to the repo — which triggers a Vercel redeploy. This is the mechanism that makes the [static-first](../concepts/static-first.md) design work without a server.

The **secured** strategies have their *own* crons (`rebalance.yml`, `daily.yml`) in the private repo — see [secured-updater.md](secured-updater.md). This page is only the public, open-strategy job.

## Shape

- **Triggers:** two weekday crons — `30 11 * * 1-5` and `30 22 * * 1-5` (UTC; the evening run is after US market close) — plus manual `workflow_dispatch`.
- **Concurrency:** a `open-strategies-update` group with `cancel-in-progress: false`, so two runs never race to commit.
- **Permissions:** `contents: write` (the job pushes a data commit).
- **Steps:** checkout → `actions/setup-python@v5` (3.12, pip cache) → `pip install -r paper_trading/requirements.txt` → `python -m paper_trading.update` → stage `public/data/{portfolio,trades,strategies,benchmark}.json` → commit + push **only if** `git diff --staged` shows a change.
- **Bot identity:** commits as `paper-trading-bot <actions@users.noreply.github.com>`, message `data: refresh open-strategy paper portfolio [skip ci]` (the `[skip ci]` tag avoids retriggering CI on the data commit).

## Invariants it respects

- **No committed secret.** The price source is keyless. If a keyed source were ever used, the key would be a GitHub Actions repo secret referenced as `${{ secrets.NAME }}` — never inlined. See [reference/env-vars.md](../reference/env-vars.md).
- **Commits data only.** The job stages only `public/data/*.json`; it never touches application code.
- **Idempotent / no-op safe.** If a run produces no change, the `git diff --staged --quiet` guard commits nothing.

## Source files

- `.github/workflows/open-strategies-update.yml` — the workflow.
- `paper_trading/update.py` — what the job runs.
- Private repo `.github/workflows/{rebalance,daily}.yml` — the secured counterparts (see [secured-updater.md](secured-updater.md)).
