# personal-site

A personal website with three things on it:

1. **Writeups** about [Darwin](https://github.com/) and other projects (MDX).
2. A **live paper-trading dashboard** for selected Darwin "king" strategies — *simulated only, not investment advice*.
3. A **portfolio** of other software / non-software work.

Stack: **Next.js 15 (App Router) + React 19 + Tailwind**, deployed static-first on **Vercel Hobby** behind Cloudflare, with a **Python paper-trading updater** that runs in GitHub Actions and commits pre-computed JSON snapshots. Budget target: ~$10–20/yr (domain only).

## Architecture in one picture

```
Darwin engine (private)  →  paper-trading updater (CI)  →  public site (Vercel)
   Tier 3                      Tier 2                        Tier 1
   picks kings,                runs the paper sim,           renders the
   publishes scrubbed JSON     writes public/data/*.json     committed JSON
        └──────────── one-way, JSON only, no secrets ────────────┘
```

Trading is **paper / simulated only** — no broker, no real money, no order endpoints.

## Documentation

- **AI agents:** read `CLAUDE.md` / `AGENTS.md` (the working agreement) and start from [docs/INDEX.md](docs/INDEX.md).
- **Humans:** [docs/01-overview.md](docs/01-overview.md) for the mental scaffold; [plans_and_text_files/PERSONAL_WEBSITE_PLAN.md](plans_and_text_files/PERSONAL_WEBSITE_PLAN.md) for the full design and build order.

The root AI-instruction files (`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`) are **generated** from `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md` and are **git-ignored** (kept local, not published). Regenerate them after cloning:

```powershell
python scripts/sync_ai_docs.py            # regenerate
python scripts/sync_ai_docs.py --check    # verify in sync
```

## Build & dev

See [docs/reference/build-and-dev.md](docs/reference/build-and-dev.md). The site is scaffolded incrementally per the plan's build order — not all commands exist yet.

```powershell
npm install
npm run dev                     # Next.js dev server (Tier 1)
npm run build                   # production build
python -m paper_trading.update  # regenerate public/data/*.json (Tier 2)
```

## License

- **Code** — [MIT](LICENSE). The application, scripts, and tooling are free to reuse.
- **Content** — essays/writeups (`content/`) and any art/music are licensed under
  [CC BY-NC-ND 4.0](LICENSE-content.md): share and cite with credit; no commercial
  use or distribution of adaptations without permission.

## Security

No secrets in this repo. Price-data sources are keyless or use a CI secret; `.env*` is git-ignored; the public site is read-only and holds no credentials. See [docs/concepts/separation-from-darwin.md](docs/concepts/separation-from-darwin.md).
