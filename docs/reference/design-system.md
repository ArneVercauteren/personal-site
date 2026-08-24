# Reference — Design system (dark / technical)

The site is **dark and technical throughout** — a cohesive quant-terminal aesthetic. Data-dense and precise for Darwin/Live; the creative sections carry warmth through large media on the same dark canvas, not through a different palette.

These are target tokens. When the Tailwind theme is wired (`tailwind.config.ts` + global CSS), keep this page in lockstep with the actual values.

## Color tokens

| Token | Value | Use |
|---|---|---|
| `bg.base` | `#0a0c10` | page background (near-black) |
| `bg.panel` | `#11151c` | cards, panels |
| `bg.elevated` | `#161b22` | popovers, elevated surfaces |
| `border` | `#222a35` | hairline borders, grid lines |
| `text.primary` | `#e6edf3` | body text |
| `text.muted` | `#9da7b3` | secondary text, captions |
| `accent` | `#39d0d8` | links, highlights, focus (one brand cyan) |
| `gain` | `#3fb950` | positive P&L, up moves |
| `loss` | `#f85149` | negative P&L, down moves |

Use `gain`/`loss` **only** for financial direction, never decoratively — they carry meaning on the dashboard.

## Typography

| Role | Family | Notes |
|---|---|---|
| Prose / UI | Inter (sans) | essays, body, nav |
| Data / numbers / code | JetBrains Mono or IBM Plex Mono | **all numbers** in tables and charts; tabular figures, right-aligned |

Numbers are always monospace and tabular-aligned so columns line up like a terminal.

## Charts (Recharts)

- Thin lines (~1.5px), faint grid using `border`, minimal axes.
- Equity/P&L colored with `gain`/`loss`; exposure donut uses a restrained categorical ramp off `accent`.
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
