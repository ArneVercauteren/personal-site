# Subsystem — Site shell (Tier 1)

> **Status: built (v1 shell).** The Next.js 15 App Router shell is scaffolded with the dark/technical theme. Content/dashboard internals still land per the build order.

## What this owns

The chrome around every page: the App Router root layout, navigation, footer, the dark theme, global Tailwind styles, and fonts. The structural frame that content and dashboard pages render inside.

## Shape

- `app/layout.tsx` — root layout: loads Inter + JetBrains Mono as CSS-variable fonts, renders `Nav` + `main` + `Footer`, sets base bg/text.
- `app/globals.css` — Tailwind layers + the `.panel` / `.num` component utilities.
- `tailwind.config.ts` — the design tokens (mirror of [reference/design-system.md](../reference/design-system.md)).
- `components/Nav.tsx` — client component; grouped nav from `lib/site.ts`, active-route highlight via `usePathname` (note: `/darwin` is not "active" while on `/darwin/live`).
- `components/Footer.tsx` — static footer carrying the standing paper-only note.
- `components/PageHeader.tsx` — shared eyebrow/title/intro header used by every section page.
- `lib/site.ts` — site name, tagline, and the nav order (single source for nav).

Section pages exist as styled placeholders: `app/{about,darwin,darwin/live,writing,studio,projects}/page.tsx`.

## Conventions

- Nav order lives **only** in `lib/site.ts` — add/reorder tabs there, not in `Nav.tsx`.
- All financial figures use the `.num` utility (mono + tabular). See [reference/design-system.md](../reference/design-system.md).
- Theme is dark-only (`color-scheme: dark`); there is no light mode toggle.

## Invariants it must respect

- [Public site is read-only](../concepts/public-site-is-read-only.md) — the shell holds no credential and triggers no side effect.
- [Static-first](../concepts/static-first.md) — pages prerender static (the build confirms all routes are `○ Static`); no request-time data fetching in the shell.

## Source files

- `app/layout.tsx`, `app/globals.css`, `app/page.tsx`
- `components/Nav.tsx`, `components/Footer.tsx`, `components/PageHeader.tsx`, `components/Disclaimer.tsx`
- `lib/site.ts`, `tailwind.config.ts`
