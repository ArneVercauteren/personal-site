# personal-site — Overview

A 5-minute read. Get the mental scaffold; then jump into [concepts/](concepts/) or [subsystems/](subsystems/) for depth.

## What this is

A **personal website**, dark/technical in theme, with these sections:

- **Darwin** — the flagship: what the genetic-programming engine is, how it works, and **specific results**.
- **Live** — a paper-trading dashboard (equity curves, stats, exposure) for selected Darwin strategies, run as a **simulated** portfolio (no broker, no real money).
- **Writing** — essays (MDX).
- **Studio** — music + art.
- **Projects** — other software / non-software work (MDX).
- **About** — bio + résumé.

Nav is grouped to ~6 items: `Home · About · Darwin · Live · Writing · Studio · Projects`. Full IA: [reference/site-map.md](reference/site-map.md). Theme tokens: [reference/design-system.md](reference/design-system.md).

The whole thing runs on **free tiers**, so the only real cost is the domain (~$10–20/yr). It stays that cheap by being **static-first**: the heavy lifting happens in scheduled jobs that commit pre-computed JSON, and the site just serves that JSON over a CDN.

## The three tiers

The defining idea is a strict, one-way separation. Data flows **outward only**, as JSON, and secrets never travel with it.

```
TIER 3 — Darwin engine (your PC, PRIVATE)
   Picks king strategies; deploys one ONCE by pushing its scrubbed
   formula to the private updater repo. Never publicly reachable.
        │  one-way push, only when (re)deploying a king
        ▼
TIER 2 — Paper-trading updaters (GitHub Actions, free)
   2a SECURED (private repo): holds secret formulas + weights; rebalances
      and marks to market; pushes ONLY curve+stats+exposure to the public repo.
   2b OPEN    (public repo):  runs public formulas; writes full JSON incl. positions.
        │  commits/pushes data/*.json
        ▼
TIER 1 — Public website (Next.js on Vercel, free)
   Static content (MDX) + dashboard pages that read the JSON.
   Auto-deploys on git push.
```

Why no always-on backend: scheduled jobs recompute snapshots and commit them; Vercel redeploys automatically; the site serves static JSON. That is $0/mo beyond the domain. A real service is an *optional later upgrade* (intraday refresh), explicitly out of scope for v1. See [concepts/three-tier-separation.md](concepts/three-tier-separation.md) and [concepts/static-first.md](concepts/static-first.md).

**Why the Tier-2 split:** the only sensitive assets are the deployed king *formulas* and the *weights* they produce. Those live in a **private** repo (2a) that publishes only a sanitized performance + aggregate-exposure snapshot. **Open** strategies (1–2, for advertisement) have nothing to hide and run in the public repo (2b). See [concepts/open-vs-secured-strategies.md](concepts/open-vs-secured-strategies.md).

## The stack

| Concern | Choice | Notes |
|---|---|---|
| Frontend | Next.js 15 (App Router) + React 19 + Tailwind | Darwin UI is React 18; Next 15 + MDX needs 19 |
| Content | MDX | Writeups as Markdown with embedded React |
| Charts | Recharts | Equity curve, drawdown |
| Hosting | Vercel Hobby (free) | Push-to-deploy from GitHub |
| DNS / TLS / CDN | Cloudflare (free) | |
| Data store | Static JSON in `public/data/` | Tiny payloads, CDN-cached |
| Scheduled job | GitHub Actions cron | Runs the Tier-2 updater |
| Price data | yfinance to start (keyless) | Swappable adapter behind one module |

Choices are pinned to avoid bikeshedding — see the plan's §3 for the rationale: [plans_and_text_files/PERSONAL_WEBSITE_PLAN.md](../plans_and_text_files/PERSONAL_WEBSITE_PLAN.md).

## The non-negotiable invariants (the short list)

Each is cheap to break by accident and expensive to debug. Long versions in [concepts/](concepts/).

1. **The public site is read-only.** It renders data; it never trades and never holds credentials.
2. **Three tiers, strictly separated.** One-way outward JSON push (Tier 2 = 2a private + 2b public). No secrets flow down.
3. **Open vs secured strategies.** Open = fully public for advertisement; secured = performance + aggregate exposure only, computed in a private repo. Never publish a secured strategy's positions or formula.
4. **Paper / simulated only.** Deterministic, re-runnable, with a standing "not investment advice" disclaimer.
5. **Separate from Darwin; no secrets in the repo.** No reach into `src/config/secrets.py`; secret formulas/weights live only in the private repo.
6. **Static-first.** Pre-computed JSON over a live server until daily snapshots genuinely aren't enough.
7. **The data contract is the single source of truth.** `lib/data.ts` types define the JSON (gated by `visibility`); change reader and writer(s) together.

## The data contract

The one piece of coupling between Tier 2 (writer) and Tier 1 (reader) is the JSON shape, defined once by the TypeScript types in `lib/data.ts`. A `visibility` field gates which fields appear:

```json
{
  "as_of": "2026-06-01",
  "base_currency": "USD",
  "strategies": [
    { "id": "open_momentum_v1", "name": "Momentum (Open)", "visibility": "open",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.081, "sharpe": 0.65, "max_dd": -0.12},
      "positions": [{"ticker": "AAPL", "weight": 0.04}] },
    { "id": "balanced_king_v3", "name": "Balanced King", "visibility": "secured",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.094, "sharpe": 0.71, "max_dd": -0.10},
      "exposure": [{"group": "Technology", "weight": 0.32}] }
  ]
}
```

Secured entries carry `exposure` (aggregate) and never `positions` or a formula. Keep it small and stable. See [concepts/data-contract.md](concepts/data-contract.md).

## Planned layout on disk

```
personal-site/              (PUBLIC repo)
├─ app/                 # Next.js App Router — home, about, darwin, live, writing, studio, projects
├─ components/          # Nav, charts (equity/drawdown/exposure), cards, stats, studio media
├─ content/             # essays/*.mdx, projects/*.mdx
├─ lib/                 # data.ts (contract), content.ts (MDX), format.ts (helpers)
├─ public/              # data/*.json snapshots, resume.pdf, art/, audio/
├─ paper_trading/       # Tier-2b ENGINE + OPEN strategies (not secret)
├─ .github/workflows/   # open-strategies-update cron
├─ docs/                # this tree
├─ plans_and_text_files/# plan + shared AI-instructions source
└─ scripts/             # sync_ai_docs.py and operator scripts

personal-site-trading/      (PRIVATE repo — Tier 2a)
├─ strategies/  weights/  ticker_sectors.json   # secret
└─ .github/workflows/{rebalance,daily}.yml      # pushes sanitized JSON to the public repo
```

Full layout: [reference/file-layout.md](reference/file-layout.md). This is the *target* — the repo is scaffolded incrementally per the plan's build order (§12).

## What to read next

- **Want the architecture rules?** [concepts/three-tier-separation.md](concepts/three-tier-separation.md), then [concepts/data-contract.md](concepts/data-contract.md).
- **Want to make a change?** Find your task in [INDEX.md](INDEX.md) → "Routing" → open the linked subsystem page, then the relevant `tasks/` recipe.
- **Just here to run things?** [reference/build-and-dev.md](reference/build-and-dev.md).

## Source files

- `plans_and_text_files/PERSONAL_WEBSITE_PLAN.md` — full design rationale and build order.
- `lib/data.ts` — the data contract (when built).
- `app/`, `components/` — Tier 1 site (when built).
- `paper_trading/` — Tier 2 updater (when built).
