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
pip install -r paper_trading/requirements-lock.txt  # deterministic CI/updater environment
python -m paper_trading.validate_data               # verify the committed publication
python -m paper_trading.update                      # process unseen sessions only
python -m paper_trading.update --strategy gen0194  # update one open strategy
python -m paper_trading.audit --strategy gen0194   # read-only full replay comparison
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

## First deployment of a strategy

The updater deliberately refuses to invent a checkpoint. Generate a migration candidate, review its
exact curve/hash report, then approve it with a named reviewer:

```powershell
python -m paper_trading.migrate --strategy gen0194
python -m paper_trading.migrate --strategy gen0194 --approve --reviewer "Your Name"
```

After approval, routine updates are idempotent and incremental.

## Source files

- `package.json` — npm scripts.
- `paper_trading/requirements-lock.txt`, `paper_trading/update.py` — updater environment and entry.
- `scripts/sync_ai_docs.py` — AI-doc sync (exists).
- `.github/workflows/open-strategies-update.yml` — public CI cron.
- Private repo `.github/workflows/{rebalance,daily}.yml` — secured crons.
