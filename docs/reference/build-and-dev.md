# Reference — Build & dev commands

Commands are PowerShell (Windows). The repo is being scaffolded per the plan's build order (§12); commands appear here as the matching code lands.

## Tier 1 — the public site (Next.js)

```powershell
npm install                 # first time / after dependency changes
npm run dev                 # local dev server (hot reload) at http://localhost:3000
npm run build               # production build — MUST pass before deploy
npm run start               # serve the production build locally
npm run lint                # eslint
```

`npm run build` is the gate: Vercel runs it on every push, and a failing build blocks deploy.

## Tier 2 — the paper-trading updater (Python)

```powershell
pip install -r paper_trading/requirements.txt   # first time
python -m paper_trading.update                  # regenerate public/data/*.json locally
python -m paper_trading.update --strategy gen0194  # update one open strategy
```

Run this after changing anything in `paper_trading/`, then inspect the regenerated `public/data/*.json` before committing. Yahoo fetch chunks are cached locally in `.cache/paper_trading/ohlcv` so interrupted local runs can resume completed chunks; use `PAPER_TRADING_PRICE_CACHE=0` to bypass that cache. In production it runs in GitHub Actions on a cron and commits the JSON; see [subsystems/scheduled-job.md](../subsystems/scheduled-job.md).

## AI instruction docs

```powershell
python scripts/sync_ai_docs.py            # regenerate CLAUDE.md / AGENTS.md / copilot-instructions.md
python scripts/sync_ai_docs.py --check    # verify they are in sync (CI gate)
```

Edit `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md`, then run the sync — never hand-edit the generated files.

## Deploy

Deployment is **push-to-deploy**: pushing to the default branch triggers a Vercel build of the site. The open updater (this repo) and the secured updater (private repo) each commit/push new `public/data/*.json` on their schedules, which triggers a redeploy. There is no manual deploy step in the static-first design. See [concepts/static-first.md](../concepts/static-first.md).

## Status

The Next.js app is scaffolded: `npm install`, `npm run dev`, `npm run build`, and `npm run lint` all work today (the build prerenders every route as static). The Python `paper_trading/` updater does not exist yet, so its commands are still the *target*. The sync-docs commands work today.

## Source files

- `package.json` — npm scripts (when built).
- `paper_trading/requirements.txt`, `paper_trading/update.py` — updater entry (when built).
- `scripts/sync_ai_docs.py` — AI-doc sync (exists).
- `.github/workflows/open-strategies-update.yml` — public CI cron (when built).
- Private repo `.github/workflows/{rebalance,daily}.yml` — secured crons (when built).
