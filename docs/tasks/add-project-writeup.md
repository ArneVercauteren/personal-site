# Task — Add a writeup (essay or project)

The MDX pipeline is built ([subsystems/content-mdx.md](../subsystems/content-mdx.md)). To add a writeup:

## Steps

1. Create the file:
   - Essay → `content/essays/<slug>.mdx`
   - Project → `content/projects/<slug>.mdx`

   The `<slug>` becomes the URL (`/writing/<slug>` or `/projects/<slug>`).
2. Add frontmatter:
   ```yaml
   ---
   title: "Title shown as the page heading"
   summary: "One line — used in the index and as the page intro."
   date: "2026-06-01"          # ISO; lists sort newest-first
   tags: ["tag-a", "tag-b"]    # optional
   draft: true                 # optional; hides it until removed
   ---
   ```
3. Write the body in Markdown/MDX (GitHub-flavoured markdown is enabled; tables, etc.).
4. Run `npm run dev` and confirm it appears in the index and renders at its slug.
5. `npm run build` — detail routes are SSG via `generateStaticParams`, so a broken frontmatter date or missing field shows up here.

## Notes

- Leave `draft: true` while writing — drafts are excluded from the index and from the static build.
- Prose styling is automatic (`prose prose-invert`); no per-page styling needed.

## Invariants

- [Static-first](../concepts/static-first.md): writeups are statically generated; no request-time fetching.
- No secrets, no external side effects — it's [read-only](../concepts/public-site-is-read-only.md) content.

## Source files

- `content/essays/*.mdx`, `content/projects/*.mdx`, `lib/content.ts`, `components/Mdx.tsx`.
