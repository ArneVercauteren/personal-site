# Concept — Separate from Darwin; no secrets in the repo

This repo is **independent** of the Darwin repo, and it contains **no secrets**. These two properties protect each other.

## Separate repo, separate deployment

`personal-site` is its own repository with its own deployment. It is not a subfolder of Darwin and does not share Darwin's Python environment.

- **No import path into Darwin internals.** Nothing here imports `src/config/secrets.py`, `src/...` modules, or otherwise path-reaches into the Darwin tree. If Tier 2 needs to evaluate a strategy signal, it does so via a small re-implementation or a *vendored, scrubbed* copy — never by reaching across into the live Darwin repo. (See the plan's §5 options A/B; A is the default.)
- **The only coupling is one-way JSON.** Darwin's publish step (Tier 3) writes portable king JSON into this repo's `paper_trading/strategies/`. That is the entire interface.

## No secrets in the repo

- **Price-data sources are keyless** to start (yfinance / stooq). If a source ever needs a credential, it comes from a **GitHub Actions secret** (for Tier 2) or a **Vercel/Cloudflare env var** (for Tier 1) — never a committed value.
- **`.env*` is git-ignored.** No credential file is ever committed.
- **Published strategy JSON is scrubbed.** The Tier-3 publish step strips internal absolute paths, internal-only fields, and anything secret before the JSON lands here. What arrives is the DSL tree + portable metadata, nothing more.

## Why both rules together

If the website repo could import Darwin, a leak in the website would expose Darwin's internals and secrets. If the website committed any key, the public repo would leak it directly. Keeping the repos separate **and** keeping secrets out means a full compromise of this repo exposes only public, already-published data.

## The checklist (from the plan's §9)

- [ ] No import path reaches `src/config/secrets.py` or any Darwin internal module.
- [ ] No API keys committed; keyless sources or CI/host secrets only.
- [ ] No trading/order/write endpoints exposed publicly.
- [ ] Published strategy JSONs are scrubbed (no absolute paths, no internal-only fields).
- [ ] `.env` and credentials git-ignored.

## Related

- [three-tier-separation.md](three-tier-separation.md) — the one-way boundary this enforces.
- [public-site-is-read-only.md](public-site-is-read-only.md) — the public surface holds nothing secret.
- [subsystems/darwin-publish.md](../subsystems/darwin-publish.md) — the scrub/publish step.

## Source files

- `.gitignore` — must ignore `.env*` and any credential files.
- `paper_trading/strategies/*.json` — scrubbed king exports (when published).
- The Darwin repo's `scripts/publish_deployed_kings.py` — does the scrubbing (when built).
