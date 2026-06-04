# Reference — Site map (information architecture)

The route tree and what each page owns. Theme tokens are in [design-system.md](design-system.md).

## Top-level navigation

**Studio** and **Projects** are temporarily hidden from the nav (their routes still exist and build; re-add them in `lib/site.ts` and the home-page tiles when ready). The **Studio** hub combines music + art.

```
Home  ·  About  ·  Darwin  ·  Live  ·  Writing  ·  Contact
```

## Routes

| Route | Page owns | Notes |
|---|---|---|
| `/` | Home | Hero (one-line identity), one featured Darwin result, links into each section. |
| `/about` | Bio | Product-style bio: hero, capabilities, an at-a-glance spec sheet (incl. an auto-updating age derived from `site.birthDate`), placeholder profile photo (`public/profile.png`). Résumé deferred. |
| `/contact` | Contact | Email contact (`site.email`) with a `mailto:` CTA. Surfaced as its own nav item. |
| `/darwin` | Darwin explainer + **Methodology** | What Darwin is (a high-performance GP search — kept deliberately high-level), the **Tiingo** data source, the investable **universe & filters**, the **backtesting model** (daily bars, next-open fills, regimes, metrics), the **cost model** (commission/slippage/impact bps), and **out-of-sample testing & validity measures** (train/OOS firewall, rolling stress, factor decomposition, capacity). The most prominent action links to `/darwin/live`. The flagship section; results themselves live on the dashboard. |
| `/darwin/live` | Live dashboard | Open + secured strategies, in two labelled sections (open broken out first). Standing paper-only disclaimer. Reads `public/data/*.json`. Also surfaced as its own nav item ("Live"). |
| `/darwin/live/[id]` | Strategy detail | Per-strategy deep dive (statically generated per published id): key facts, a continuous OOS/backtest → live shaded-band equity chart, live stats, three detailed-stat panels (training / OOS / combined), capacity & holdings, and the basket (open) / exposure donut (secured). Provenance comes from `strategies.json` (`performance` — the three single-seed runs — plus `active_share` / `capacity`). |
| `/writing` | Essay index | Lists essays from `content/essays/*.mdx`. |
| `/writing/[slug]` | Essay reader | Renders one essay. |
| `/studio` | Music + Art hub | Music: embeds or self-hosted players. Art: image galleries with lightbox. **Hidden from nav for now.** |
| `/projects` | Portfolio index | Lists `content/projects/*.mdx` (software + non-software). **Hidden from nav for now.** |
| `/projects/[slug]` | Project writeup | Renders one writeup. |

## Section ownership → subsystem docs

| Section | Subsystem page |
|---|---|
| Nav, layout, theme | [subsystems/site-shell.md](../subsystems/site-shell.md) |
| Writing + Projects (MDX) | [subsystems/content-mdx.md](../subsystems/content-mdx.md) |
| Live dashboard | [subsystems/live-dashboard.md](../subsystems/live-dashboard.md) |
| Studio (music/art) | [subsystems/studio.md](../subsystems/studio.md) |

## Conventions

- **Live** is a sub-route of Darwin (`/darwin/live`) but appears as its own nav entry.
- Content sections (About, Writing, Studio, Projects) are **static, no moving parts** — build them first (plan §12).
- Every page that shows portfolio data carries the paper-only disclaimer. See [concepts/paper-trading-only.md](../concepts/paper-trading-only.md).

## Source files

- `app/**/page.tsx` — the routes above (when built).
- `components/Nav.tsx` — the nav order (when built).
- `plans_and_text_files/PERSONAL_WEBSITE_PLAN.md` §4 — the authoritative IA.
