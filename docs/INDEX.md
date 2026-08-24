# personal-site docs — Index

> **AI: this file is your map. Don't read the whole `docs/` tree — grep this index, then open the one or two pages you need.** Each page is self-contained and ends with pointers to the source it documents.

## How this is organised

| Tier | Folder | Purpose |
|---|---|---|
| Overview | [01-overview.md](01-overview.md) | What the site is and how the three tiers fit, in one read. Start here. |
| Concepts | [concepts/](concepts/) | The *why*: invariants, contracts, the architecture rules. Stable. |
| Subsystems | [subsystems/](subsystems/) | The *how*: each tier and feature — data flow, entry points, gotchas. |
| Tasks | [tasks/](tasks/) | Recipes for common changes (add a writeup, add a strategy, add a chart). |
| Reference | [reference/](reference/) | Lookups: file layout, build/deploy commands, env vars. |
| Playbook | [playbook/](playbook/) | Working agreement: doc/test maintenance rules, AI workflow. |

`CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md` in the repo root hold the short non-negotiable invariants and point at this file. They are **generated** from `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md` via `python scripts/sync_ai_docs.py` — edit the shared source, never the generated files.

The full design rationale lives in [plans_and_text_files/PERSONAL_WEBSITE_PLAN.md](../plans_and_text_files/PERSONAL_WEBSITE_PLAN.md).

## Routing — when working on X, read Y

| If you are touching… | Read |
|---|---|
| The public site shell (nav, layout, theme) | [subsystems/site-shell.md](subsystems/site-shell.md) → [reference/design-system.md](reference/design-system.md), [concepts/static-first.md](concepts/static-first.md) |
| Site structure / routes / nav order | [reference/site-map.md](reference/site-map.md) |
| Colors / type / chart styling | [reference/design-system.md](reference/design-system.md) |
| Essays / project writeups in MDX | [subsystems/content-mdx.md](subsystems/content-mdx.md) → [tasks/add-project-writeup.md](tasks/add-project-writeup.md) |
| Music / art (Studio) | [subsystems/studio.md](subsystems/studio.md) |
| The live paper-trading dashboard | [subsystems/live-dashboard.md](subsystems/live-dashboard.md) → [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md), [concepts/data-contract.md](concepts/data-contract.md) |
| The JSON shape the site reads/writes | [concepts/data-contract.md](concepts/data-contract.md) |
| Open vs secured strategies (security boundary) | [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md) |
| The open-strategy simulator/engine (Tier 2b) | [subsystems/paper-trading-updater.md](subsystems/paper-trading-updater.md) → [concepts/paper-trading-only.md](concepts/paper-trading-only.md) |
| The tradable universe (self-refreshing) | [subsystems/universe.md](subsystems/universe.md) |
| The secured pipeline (private repo, Tier 2a) | [subsystems/secured-updater.md](subsystems/secured-updater.md) → [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md) |
| The scheduled GitHub Actions job | [subsystems/scheduled-job.md](subsystems/scheduled-job.md) → [concepts/static-first.md](concepts/static-first.md) |
| The Darwin → site publish step (Tier 3) | [subsystems/darwin-publish.md](subsystems/darwin-publish.md) → [concepts/separation-from-darwin.md](concepts/separation-from-darwin.md) |
| Anything that could touch secrets / keys / weights | [concepts/separation-from-darwin.md](concepts/separation-from-darwin.md), [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md), [concepts/public-site-is-read-only.md](concepts/public-site-is-read-only.md) |
| Build / deploy commands | [reference/build-and-dev.md](reference/build-and-dev.md) → [playbook/deployment-runbook.md](playbook/deployment-runbook.md) |
| Where files live on disk | [reference/file-layout.md](reference/file-layout.md) |
| Env vars / CI secrets | [reference/env-vars.md](reference/env-vars.md) |

## Routing — by "I want to add X"

| Goal | Recipe |
|---|---|
| New project writeup | [tasks/add-project-writeup.md](tasks/add-project-writeup.md) |
| New deployed strategy on the dashboard | [tasks/add-deployed-strategy.md](tasks/add-deployed-strategy.md) |
| New dashboard chart / stat | [tasks/add-dashboard-chart.md](tasks/add-dashboard-chart.md) |

## Concepts (read once, refer back)

- [concepts/public-site-is-read-only.md](concepts/public-site-is-read-only.md) — the public site only renders; it never trades or holds credentials.
- [concepts/three-tier-separation.md](concepts/three-tier-separation.md) — Darwin engine → updaters (2a private / 2b public) → site; one-way JSON push.
- [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md) — the security boundary: open strategies are fully public; secured strategies publish performance + aggregate exposure only.
- [concepts/paper-trading-only.md](concepts/paper-trading-only.md) — simulated only, deterministic, with a standing disclaimer.
- [concepts/separation-from-darwin.md](concepts/separation-from-darwin.md) — separate repo, no secrets, no reach into Darwin internals.
- [concepts/static-first.md](concepts/static-first.md) — pre-computed JSON over a live server; what the $10/yr budget buys.
- [concepts/data-contract.md](concepts/data-contract.md) — `lib/data.ts` types are the single source of truth for the JSON shape.

## Maintenance

- [playbook/doc-maintenance.md](playbook/doc-maintenance.md) — when your change invalidates a doc claim, update the doc in the same change.
- [playbook/test-maintenance.md](playbook/test-maintenance.md) — when your change shifts a contract a test pins, update the test in the same change. Never silence with `.skip`/`xfail`.
- [playbook/ai-workflow.md](playbook/ai-workflow.md) — workflow for an AI making changes: locate the tier, respect the contract, keep secrets out, build.
- [playbook/deployment-runbook.md](playbook/deployment-runbook.md) — migration approval, scheduled publication, alerts, and recovery.

## Status

The site, paper updater, immutable ledger, versioned publication, and scheduled workflows are built.
Some optional content routes remain intentionally sparse; their subsystem pages state that explicitly.

## How to find a specific source-code claim

Every page ends with a **"Source files"** block listing the modules it documents. No line numbers — they drift. Use `grep` / Glob for the specific symbol once you know the file.
