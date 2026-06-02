# personal-site — GitHub Copilot instructions

> Same agreement as [CLAUDE.md](../CLAUDE.md) and [AGENTS.md](../AGENTS.md). Keep all three in sync by editing the shared source and re-running `python scripts/sync_ai_docs.py`.

> Generated from [plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md](../plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md) via `python scripts/sync_ai_docs.py`. Edit the shared source, then re-run the sync script. Do not hand-edit this file.

## What this repo is

`personal-site` is a **personal website** with three things on it: (a) writeups about Darwin and other projects, (b) a **live paper-trading dashboard** for selected Darwin "king" strategies, and (c) a general portfolio of other software / non-software work. Stack: **Next.js 15 (App Router) + React 19 + Tailwind**, deployed static-first on **Vercel Hobby** behind Cloudflare, with a **Python paper-trading updater** that runs in GitHub Actions and commits pre-computed JSON snapshots. Budget target: **~$10–20/yr** (domain only). Trading is **paper / simulated only** — no broker, no real money, no order endpoints.

## Required reading

**Start with [docs/INDEX.md](../docs/INDEX.md).** It is the routing map: grep it, then open the one or two pages you need. Do not read the whole `docs/` tree up-front — each page is self-contained.

For a one-read mental scaffold, start at [docs/01-overview.md](../docs/01-overview.md). For depth on a tier or subsystem, follow the routing table in `INDEX.md`.

For trivial changes (typo fix, single-line tweak in an obvious place), the invariants below are enough.

## Non-negotiable invariants (the short list)

These are the things easiest to break by accident. Full discussion in [docs/concepts/](../docs/concepts/).

1. **The public site is read-only.** Tier 1 never executes trades, never holds broker credentials or API keys, and never exposes an order/write endpoint. It only *renders* data that something else computed. See [docs/concepts/public-site-is-read-only.md](../docs/concepts/public-site-is-read-only.md).
2. **Three tiers, strictly separated.** Tier 3 (Darwin engine, private) → Tier 2 (paper-trading updaters: **2a** secured/private repo, **2b** open/public repo) → Tier 1 (public site). Data flows **one way, outward, as JSON only**. No secrets ever travel down the chain. See [docs/concepts/three-tier-separation.md](../docs/concepts/three-tier-separation.md).
3. **Open vs secured strategies — a security boundary.** **Open** strategies (1–2, for advertisement) publish formula + weights + performance from the public repo. **Secured** strategies publish **performance + aggregate sector/asset-class exposure only** — never the formula, never individual ticker weights — and are computed in a **separate private repo** that pushes only the sanitized snapshot here. A `visibility: "secured"` entry must never contain `positions` or a formula. See [docs/concepts/open-vs-secured-strategies.md](../docs/concepts/open-vs-secured-strategies.md).
4. **Paper / simulated only.** The simulator is deterministic and re-runnable. No broker integration, no real money, no live order routing anywhere in this repo. Every live page carries a "simulated paper portfolio, not investment advice" disclaimer. See [docs/concepts/paper-trading-only.md](../docs/concepts/paper-trading-only.md).
5. **Separate from Darwin; no secrets in the repo.** This repo is independent of the Darwin repo and **must not** import or path-reach `src/config/secrets.py`. Secret king formulas and ticker weights live only in the private updater repo — never here, not even in git history. Price-data sources are keyless, or use a GitHub Actions secret — never a committed key. See [docs/concepts/separation-from-darwin.md](../docs/concepts/separation-from-darwin.md).
6. **Static-first.** A paper portfolio that updates a few times a day does not need a running server. Prefer pre-computed JSON committed to the repo and served over the CDN over standing up a backend. That is what keeps this at ~$10/yr. Add a service only when daily snapshots genuinely stop being enough. See [docs/concepts/static-first.md](../docs/concepts/static-first.md).
7. **The data contract is the single source of truth.** The TypeScript types in `lib/data.ts` define the exact JSON shape that Tier 2 writes and Tier 1 reads (gated by `visibility`). Keep it small and stable; change reader and writer(s) in the same commit. See [docs/concepts/data-contract.md](../docs/concepts/data-contract.md).

## Maintenance rules

**If your work invalidates any claim in `docs/`, update the doc in the same change.** Stale docs are worse than no docs. Full rule: [docs/playbook/doc-maintenance.md](../docs/playbook/doc-maintenance.md).

**If your change shifts a contract a test pins (the data-contract shape, a formatting helper, a snapshot fixture), update the test in the same change.** Never silence with `.skip`/`xfail`/`--ignore`. Full rule: [docs/playbook/test-maintenance.md](../docs/playbook/test-maintenance.md).

## Workflow for AI making changes

Condensed in [docs/playbook/ai-workflow.md](../docs/playbook/ai-workflow.md). Summary:

1. Locate the tier — site (Tier 1), updater (Tier 2), or publish step (Tier 3). Name it before editing.
2. Read the relevant `docs/subsystems/` page and any `docs/concepts/` it links.
3. If you touch the JSON shape, change `lib/data.ts` (reader) and the writer(s) — the open updater in `paper_trading/` and the secured updater in the private repo (which calls the shared sanitizer `paper_trading/secured.py`) — in lockstep. The contract is the coupling point.
4. Confirm no secret, key, broker path, formula, or ticker weight entered the public repo.
5. Confirm the public site stays read-only, secured entries expose no `positions`/formula, and the paper-only disclaimer is intact.
6. Run lint + build (and the updater locally if you touched `paper_trading/`).

## Build & test (PowerShell)

```powershell
npm install                     # first time
npm run dev                     # Next.js dev server (Tier 1)
npm run build                   # production build — must pass before deploy
npm run lint                    # eslint

# Tier 2 paper-trading updater (Python)
python -m paper_trading.update  # regenerate public/data/*.json locally
```

Full build / dev commands: [docs/reference/build-and-dev.md](../docs/reference/build-and-dev.md).

## Quick file map

| Want to change… | Start here |
|---|---|
| Site layout / nav / theme | [docs/subsystems/site-shell.md](../docs/subsystems/site-shell.md), [docs/reference/design-system.md](../docs/reference/design-system.md) |
| Site structure / routes | [docs/reference/site-map.md](../docs/reference/site-map.md) |
| Essays / project writeups (MDX) | [docs/subsystems/content-mdx.md](../docs/subsystems/content-mdx.md) |
| Music / art (Studio) | [docs/subsystems/studio.md](../docs/subsystems/studio.md) |
| Live dashboard pages / charts | [docs/subsystems/live-dashboard.md](../docs/subsystems/live-dashboard.md) |
| Open vs secured strategies | [docs/concepts/open-vs-secured-strategies.md](../docs/concepts/open-vs-secured-strategies.md) |
| The JSON the site reads | [docs/concepts/data-contract.md](../docs/concepts/data-contract.md) |
| Open-strategy simulator/engine (Tier 2b) | [docs/subsystems/paper-trading-updater.md](../docs/subsystems/paper-trading-updater.md) |
| Tradable universe (self-refreshing) | [docs/subsystems/universe.md](../docs/subsystems/universe.md) |
| Secured pipeline (private repo, Tier 2a) | [docs/subsystems/secured-updater.md](../docs/subsystems/secured-updater.md) |
| Scheduled job / CI cron | [docs/subsystems/scheduled-job.md](../docs/subsystems/scheduled-job.md) |
| Darwin → site publish step (Tier 3) | [docs/subsystems/darwin-publish.md](../docs/subsystems/darwin-publish.md) |
| File layout on disk | [docs/reference/file-layout.md](../docs/reference/file-layout.md) |
| Build / deploy commands | [docs/reference/build-and-dev.md](../docs/reference/build-and-dev.md) |

Several `docs/subsystems/` and `docs/tasks/` pages are **stubs** until the corresponding code is built. The stub states what the page will own. Fill it in the same change that lands the code.

## Secrets

There are **no secrets in this repo.** Price-data sources are keyless; anything that ever needs a credential uses a GitHub Actions secret or a Vercel/Cloudflare env var — never a committed value. `.env*` is git-ignored. This repo must not reach into the Darwin repo's `src/config/secrets.py`.
