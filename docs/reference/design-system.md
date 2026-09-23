# Reference — Design system (dark / warm)

The site is **dark throughout, with warm neutrals and a muted steel-blue accent** — precise like a research terminal, but set in a serif so the writing reads as writing. Data-dense and precise for Darwin/Live; the creative sections carry warmth through large media on the same dark canvas, not through a different palette.

These are target tokens. When the Tailwind theme is wired (`tailwind.config.ts` + global CSS), keep this page in lockstep with the actual values.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `bg.base` | `#0d0c0a` | page background (near-black) |
| `bg.panel` | `#151411` | cards, panels |
| `bg.elevated` | `#1c1a16` | popovers, elevated surfaces |
| `border` | `#2a2823` | hairline borders, grid lines |
| `text.primary` | `#ece7dd` | body text |
| `text.muted` | `#a69f92` | secondary text, captions |
| `accent` | `#86a6c4` | links, highlights, focus (one brand steel blue) |
| `gain` | `#3fb950` | positive P&L, up moves |
| `loss` | `#f85149` | negative P&L, down moves |

Use `gain`/`loss` **only** for financial direction, never decoratively — they carry meaning on the dashboard.

## Typography

| Role | Family | Notes |
|---|---|---|
| Display / prose | Newsreader (serif) | page titles, section headings, wordmark, essay body |
| UI | Inter (sans) | nav links, labels, eyebrows, dashboard text |
| Data / numbers / code | JetBrains Mono or IBM Plex Mono | **all numbers** in tables and charts; tabular figures, right-aligned |

Numbers are always monospace and tabular-aligned so columns line up like a terminal.

## Charts (Recharts)

- Thin lines (~1.5px), faint grid using `border`, minimal axes.
- Equity/P&L colored with `gain`/`loss`; benchmark uses a soft amber (`#d0ad6a`) so it never reads as the steel accent; exposure donut uses a restrained categorical ramp starting from `accent`.
- No drop shadows, no gradients-as-decoration. It should read like a trading terminal, not a marketing page.

## Creative sections (Studio)

- Same dark frame and type, but media goes large / full-bleed.
- Minimal chrome so art and music embeds dominate; color comes from the media itself.

## Accessibility

- Maintain WCAG AA contrast on `bg.base` (the tokens above clear it for body text).
- `gain`/`loss` must never be the *only* signal — pair with sign, arrow, or label for color-blind readers.

## Source files

- `tailwind.config.ts`, global CSS — the real tokens.
- `components/` chart + table components — consume these tokens.
- `plans_and_text_files/PERSONAL_WEBSITE_PLAN.md` §5 — theme rationale.
