# Concept — Static-first

A paper portfolio that updates a few times a day does not need a running server. The default design is **static**: pre-compute JSON, commit it, serve it over the CDN. This is the single decision that keeps the site at ~$10/yr.

## The principle

- **Compute ahead of time, not at request time.** Tier 2 (GitHub Actions) recomputes the portfolio snapshots on a schedule and commits `public/data/*.json`. Vercel redeploys on the push. The site serves static files.
- **No always-on backend in v1.** There is no FastAPI service, no database, no request-time market-data fetch. Those cost money and add attack surface.
- **The CDN does the scaling.** Static JSON is tiny and cache-friendly. Cloudflare/Vercel serve it for free at any traffic level you'll realistically see.

## Why this is the right default

| Property | Static-first gives you |
|---|---|
| Cost | $0/mo beyond the domain |
| Security | no server to exploit; nothing to credential |
| Simplicity | no service to deploy, monitor, or keep alive |
| Reproducibility | every snapshot is a committed artifact you can diff |

A daily (or few-times-daily) paper portfolio simply doesn't need more.

## When to break it (and how)

Add a service **only** when daily/static snapshots genuinely stop being enough — the plan's §7 lists the upgrade path:

| Want | Add | Cost |
|---|---|---|
| Intraday / on-demand refresh | small FastAPI service on Fly.io/Railway | ~$5–7/mo |
| Real DB as history grows | SQLite → Postgres (Neon free) | $0+ |

When you do add a service, it is **separate** from the public site, with its own credentials, and the public site still stays [read-only](public-site-is-read-only.md). You do not fold a backend into Tier 1.

Until then: if a feature seems to need a server, first ask whether a pre-computed snapshot would do. It almost always does.

## Related

- [three-tier-separation.md](three-tier-separation.md) — Tier 2 does the work offline so Tier 1 can be static.
- [public-site-is-read-only.md](public-site-is-read-only.md)
- [subsystems/scheduled-job.md](../subsystems/scheduled-job.md) — the cron that recomputes snapshots.

## Source files

- `.github/workflows/open-strategies-update.yml` — the public scheduled update.
- `public/data/*.json` — the committed snapshots the site serves.
