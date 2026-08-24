# Subsystem — Essays & project writeups (MDX)

> **Status: built.** The MDX pipeline renders `content/essays/*.mdx` and `content/projects/*.mdx` with frontmatter, index pages, and per-slug detail pages.

## What this owns

How writeups are authored and rendered: MDX files in `content/`, the index + dynamic detail routes, the frontmatter schema, and the dark-theme prose styling.

## Shape

- `content/essays/<slug>.mdx`, `content/projects/<slug>.mdx` — one file per writeup; filename `<slug>` is the URL.
- `lib/content.ts` — enumerates files, parses frontmatter (`gray-matter`), returns metadata for index pages and a single doc by slug. Server-only.
- `components/Mdx.tsx` — server component; compiles an MDX string at build via `next-mdx-remote/rsc` + `remark-gfm`, rendered inside `prose prose-invert`.
- `components/ContentList.tsx` — the index list (title, date, summary, tags).
- `app/writing/page.tsx` + `app/writing/[slug]/page.tsx`; `app/projects/page.tsx` + `app/projects/[slug]/page.tsx`. Detail pages use `generateStaticParams` (SSG) and `generateMetadata`.

## Frontmatter schema

```yaml
---
title: "How Darwin backtests and prices trades"
summary: "One-line description shown in the index and as the page intro."
date: "2026-05-15"        # ISO; lists sort newest-first
tags: ["darwin", "methodology"]   # optional
draft: true               # optional; excluded from listings + static params
---
```

## Conventions

- Drafts (`draft: true`) are excluded from both the index and `generateStaticParams`.
- Dark prose tokens live in `tailwind.config.ts` under `typography.invert`; keep them in step with [reference/design-system.md](../reference/design-system.md).
- `params` is a `Promise` in the current App Router — `await` it in detail pages.

## Recipe

Adding a writeup: [tasks/add-project-writeup.md](../tasks/add-project-writeup.md).

## Invariants it must respect

- [Static-first](../concepts/static-first.md): writeups are statically generated at build.
- [Public site is read-only](../concepts/public-site-is-read-only.md).

## Source files

- `lib/content.ts`, `components/Mdx.tsx`, `components/ContentList.tsx`
- `app/writing/page.tsx`, `app/writing/[slug]/page.tsx`, `app/projects/page.tsx`, `app/projects/[slug]/page.tsx`
- `content/essays/*.mdx`, `content/projects/*.mdx`
