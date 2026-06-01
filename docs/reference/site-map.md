# Reference — Site map (information architecture)

The route tree and what each page owns. Theme tokens are in [design-system.md](design-system.md).

## Top-level navigation

Grouped to ~6 items; the **Studio** hub combines music + art.

```
Home  ·  About  ·  Darwin  ·  Live  ·  Writing  ·  Studio  ·  Projects
```

## Routes

| Route | Page owns | Notes |
|---|---|---|
| `/` | Home | Hero (one-line identity), one featured Darwin result, links into each section. |
| `/about` | Bio + résumé | Web view + a downloadable `public/resume.pdf`. |
| `/darwin` | Darwin explainer + **Methodology** | What Darwin is (a high-performance GP search — kept deliberately high-level), the **Tiingo** data source, the investable **universe & filters**, the **backtesting model** (daily bars, next-open fills, regimes, metrics), the **cost model** (commission/slippage/impact bps), and **out-of-sample testing & validity measures** (train/OOS firewall, rolling stress, factor decomposition, capacity). The most prominent action links to `/darwin/live`. The flagship section; results themselves live on the dashboard. |
| `/darwin/live` | Live dashboard | Open + secured strategies, in two labelled sections (open broken out first). Standing paper-only disclaimer. Reads `public/data/*.json`. Also surfaced as its own nav item ("Live"). |
| `/writing` | Essay index | Lists essays from `content/essays/*.mdx`. |
| `/writing/[slug]` | Essay reader | Renders one essay. |
| `/studio` | Music + Art hub | Music: embeds or self-hosted players. Art: image galleries with lightbox. |
| `/projects` | Portfolio index | Lists `content/projects/*.mdx` (software + non-software). |
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
