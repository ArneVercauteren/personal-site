# Reference — Env vars & CI secrets

The static-first, read-only design means there is **very little** to configure, and **nothing secret in the repo**. This page is the lookup for what configuration exists and where it lives.

## Principles

- **No committed secrets, ever.** `.env*` is git-ignored. Any credential is supplied at runtime by the host (Vercel/Cloudflare) or by CI (GitHub Actions secrets). See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md).
- **Tier 1 needs no secret** to function — it serves static JSON. A public analytics ID or site URL is the most it ever holds.
- **Tier 2 prefers keyless price sources.** A credential appears only if you switch to a source that requires one, and then it is a **GitHub Actions secret**, never a committed value.

## Where each kind of config lives

| Kind | Lives in | Committed? |
|---|---|---|
| Public site config (site URL, public analytics ID) | Vercel/Cloudflare env vars, or `NEXT_PUBLIC_*` build vars | values: no |
| Price-data credential (only if a keyed source is chosen) | GitHub Actions repo secret, read in `paper_trading/` | never |
| Anything else secret | host/CI secret store | never |

## Current vars

None defined yet. When the first env var or CI secret is introduced, add a row here with its name, which tier reads it, and where it's set — in the same change that introduces it (see [playbook/doc-maintenance.md](../playbook/doc-maintenance.md)).

## Source files

- `.gitignore` — must ignore `.env*`.
- `.github/workflows/open-strategies-update.yml` (public) and the private repo's `{rebalance,daily}.yml` — where CI secrets are referenced (when built).
