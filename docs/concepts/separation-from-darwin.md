# Concept — Separate from Darwin; no secrets in the repo

This repo is **independent** of the Darwin repo, and it contains **no secrets**. These two properties protect each other.

## Separate repo, separate deployment

`personal-site` is its own repository with its own deployment. It is not a subfolder of Darwin and does not share Darwin's Python environment.

- **No import path into Darwin internals.** Nothing here imports `src/config/secrets.py`, `src/...` modules, or otherwise path-reaches into the Darwin tree. To evaluate a real king's DSL formula, Tier 2 uses a *vendored, scrubbed copy* of Darwin's pure-Python evaluator — `paper_trading/darwin_eval/` (the plan's option B). It is a copy, not an import: the `src.config`/`src.config.paths` couplings were replaced with vendored constants, and no secret lives there. Fidelity to the original is enforced by `paper_trading/tests/test_evaluator_parity.py`, which (when a local Darwin checkout is present via `DARWIN_REPO`) asserts bit-identical selections/weights against Darwin's own `select_tickers_on_date`. That test is the *only* place that imports Darwin, and it is test-only and skipped in CI.
- **The only coupling is one-way JSON.** Darwin's publish step (Tier 3) writes portable king JSON into this repo's `paper_trading/strategies/`. That is the entire interface.

## No secrets in the repo

- **Price-data sources are keyless** to start (yfinance / stooq). If a source ever needs a credential, it comes from a **GitHub Actions secret** (for Tier 2) or a **Vercel/Cloudflare env var** (for Tier 1) — never a committed value.
- **`.env*` is git-ignored.** No credential file is ever committed.
- **Published strategy JSON is scrubbed.** The Tier-3 publish step strips internal absolute paths, internal-only fields, and anything secret before the JSON lands here. What arrives is the DSL tree + portable metadata, nothing more. As defense in depth — the exporter's `open_diagnostics` has leaked a `sector_map_source` pointing at an absolute Darwin-repo path before — the open updater **re-scrubs** the pass-through `performance` block via `paper_trading/publish_sanitize.py` (`scrub_internal_paths` + the `assert_no_internal_paths` guard) so a drive-letter / home-dir / UNC path fails the updater rather than reaching `public/data/`.

## Why both rules together

If the website repo could import Darwin, a leak in the website would expose Darwin's internals and secrets. If the website committed any key, the public repo would leak it directly. Keeping the repos separate **and** keeping secrets out means a full compromise of this repo exposes only public, already-published data.

## The checklist (from the plan's §9)

- [x] No production import path reaches `src/config/secrets.py` or a Darwin internal module.
- [x] No API keys committed; keyless sources or CI/host secrets only.
- [x] No trading/order/write endpoints exposed publicly.
- [x] Published strategy JSONs are scrubbed and contract-tested.
- [x] `.env` and credentials are git-ignored.

## Related

- [three-tier-separation.md](three-tier-separation.md) — the one-way boundary this enforces.
- [public-site-is-read-only.md](public-site-is-read-only.md) — the public surface holds nothing secret.
- [subsystems/darwin-publish.md](../subsystems/darwin-publish.md) — the scrub/publish step.

## Source files

- `.gitignore` — must ignore `.env*` and any credential files.
- `paper_trading/darwin_eval/` — the vendored, scrubbed DSL evaluator (no `src.` imports).
- `paper_trading/tests/test_evaluator_parity.py` — the test-only parity gate (the sole, guarded Darwin import).
- `paper_trading/strategies/*.json` — scrubbed king exports (when published).
- `paper_trading/publish_sanitize.py` — the open-updater path-scrub backstop (`scrub_internal_paths` / `assert_no_internal_paths`); `paper_trading/tests/test_publish_sanitize.py` also asserts no committed `public/data/*.json` carries an absolute path.
- The Darwin repo's `scripts/publish_deployed_kings.py` — produces the one-way scrubbed export.
