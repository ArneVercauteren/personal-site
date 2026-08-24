# Reference — File layout on disk

The implemented layout. Optional media/content entries remain labelled planned; the site, paper engine,
ledger, schemas, snapshots, and workflows are live code.

```
personal-site/                          (PUBLIC repo)
├─ README.md
├─ package.json
├─ next.config.mjs  tailwind.config.ts  postcss.config.mjs  tsconfig.json  .eslintrc.json
├─ CLAUDE.md  AGENTS.md                  # generated — AI working agreement
├─ .github/
│  ├─ copilot-instructions.md           # generated — same content for Copilot
│  └─ workflows/
│     ├─ open-strategies-update.yml     # incremental weekday writer
│     ├─ universe-refresh.yml           # monthly point-in-time universe writer
│     └─ stale-data-alert.yml           # freshness alert
├─ app/                                 # Next.js App Router — Tier 1
│  ├─ layout.tsx                        # nav, footer, dark theme
│  ├─ page.tsx                          # home
│  ├─ about/page.tsx                    # bio + résumé
│  ├─ darwin/page.tsx                   # Darwin explainer + results
│  ├─ darwin/live/page.tsx              # LIVE paper-trading dashboard
│  ├─ writing/{page.tsx,[slug]/page.tsx}   # essays
│  ├─ studio/page.tsx                   # music + art hub
│  └─ projects/{page.tsx,[slug]/page.tsx}  # portfolio  ([slug] planned)
├─ content/                             # MDX writeups (seeded with samples)
│  ├─ essays/*.mdx
│  └─ projects/*.mdx
├─ components/                          # Nav, Footer, PageHeader, Disclaimer built
│  ├─ Nav.tsx  Footer.tsx  PageHeader.tsx  Disclaimer.tsx
│  ├─ EquityCurveChart.tsx  DrawdownChart.tsx  ExposureDonut.tsx   (planned)
│  ├─ StatsTable.tsx  StrategyCard.tsx                              (planned)
│  └─ studio/{MusicPlayer.tsx,ArtGallery.tsx}                       (planned)
├─ lib/                                 # site.ts, format.ts built
│  ├─ site.ts                          # nav + site config
│  ├─ data.ts                          # THE DATA CONTRACT — typed loaders
│  ├─ content.ts                       # MDX/frontmatter loading
│  └─ format.ts                        # %, $, date helpers
├─ paper_trading/                       Tier-2b ENGINE + OPEN strategies (not secret)
│  ├─ requirements-lock.txt  update.py  prices.py  portfolio.py  signals.py
│  ├─ contracts.py  deployment.py  conformance.py  ledger.py  migrate.py  audit.py  publish.py  validate_data.py
│  ├─ conformance_vectors/              # required Darwin-independent deployment fixtures
│  ├─ costs.py  secured.py             # Darwin cost model; secured sanitizer + leak guard
│  ├─ universe.py  update_universe.py  ticker_sectors.json  # self-refreshing universe + sector map
│  ├─ darwin_eval/                     # vendored Darwin DSL evaluator
│  ├─ tests/                           # pytest suite
│  └─ strategies/                      # OPEN (public) formulas only
├─ public/
│  ├─ data/manifest.json                # active content-addressed snapshot pointer
│  ├─ data/snapshots/<hash>/            # index + per-route strategy/benchmark payloads
│  ├─ data/{portfolio.json,trades.json,strategies.json,universe.json}  # writer compatibility boundary
│  ├─ resume.pdf                       (planned)
│  └─ art/  audio/                     (planned) static media for Studio
├─ docs/                                # this tree
├─ paper_state/<id>.json                # accepted incremental checkpoints
├─ paper_ledger/<id>.jsonl              # append-only audited events
├─ paper_migration/                     # reviewed migration evidence
├─ schemas/                             # versioned portable JSON contracts
├─ plans_and_text_files/                # plan + shared AI-instructions source
└─ scripts/sync_ai_docs.py             # renders CLAUDE/AGENTS/copilot from the shared source

personal-site-trading/                  (PRIVATE repo — Tier 2a, NOT this repo)
├─ strategies/  weights/  ticker_sectors.json     # secret formulas, weights, sector map
└─ .github/workflows/{rebalance.yml,daily.yml}    # crons; push sanitized JSON to public repo
```

## The boundary artifacts

These are the cross-tier interfaces — treat them as contracts, not incidental files:

- **`public/data/*.json`** — the Tier 2 → Tier 1 boundary. Shape defined by `lib/data.ts`, gated by `visibility`. Written by the open updater (this repo) and the secured updater (private repo). See [concepts/data-contract.md](../concepts/data-contract.md).
- **`paper_trading/strategies/*.json`** (public) — versioned OPEN deployment bundles; formulas plus public-safe
  provenance and hashes only. Matching fixtures live in `paper_trading/conformance_vectors/`.
- **The private repo's `strategies/` + `weights/`** — secured formulas and weights. The Tier 3 → Tier 2a boundary (scrubbed king exports from Darwin) and the secret the public repo must never contain. See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md) and [concepts/open-vs-secured-strategies.md](../concepts/open-vs-secured-strategies.md).

## Generated vs hand-edited

- **Generated (never hand-edit):** `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`. Source: `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md` + `scripts/sync_ai_docs.py`.
- **Hand-edited:** everything else, including this `docs/` tree.

## Source files

- `scripts/sync_ai_docs.py` — defines which files are generated and from where.
- `plans_and_text_files/PERSONAL_WEBSITE_PLAN.md` — the authoritative layout (§4).
