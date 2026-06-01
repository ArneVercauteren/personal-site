# Playbook — Workflow for an AI making changes

A condensed checklist. Refer to it; don't skip steps.

## Before touching code

1. **Locate the tier.** Is this Tier 1 (the public site — `app/`, `components/`, `lib/`, `content/`), Tier 2 (the updater — `paper_trading/`, `.github/workflows/`), or Tier 3 (the Darwin publish step, which lives in the Darwin repo)? Name it before editing.
2. **Read the relevant `subsystems/` page** and any `concepts/` it links.
3. **If the change crosses the Tier 2 ↔ Tier 1 boundary, it touches the data contract.** Plan to change `lib/data.ts` and the `paper_trading/` writer together.

## While editing

1. **Keep the public site read-only.** Nothing in Tier 1 may fetch market data at request time, hold a credential, or expose a write/order endpoint. See [concepts/public-site-is-read-only.md](../concepts/public-site-is-read-only.md).
2. **Keep secrets out.** No API key, no `.env` value, no broker path enters the repo. Keyless data sources or CI/host secrets only. See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md).
3. **Don't reach into Darwin.** No import or path into the Darwin tree (especially `src/config/secrets.py`). The only Darwin coupling is scrubbed king JSON arriving via the publish step.
4. **Preserve the paper-only disclaimer.** Any page showing portfolio data keeps "simulated paper portfolio, not investment advice." See [concepts/paper-trading-only.md](../concepts/paper-trading-only.md).

## Coupling: if you change the data contract

Update all of these in the same commit:

- `lib/data.ts` — the type definitions + typed loaders (reader).
- `paper_trading/update.py` (and helpers) — the JSON writer (Tier 2).
- Any sample/fixture `public/data/*.json`.
- The dashboard components that consume the changed field.
- The tests pinning the shape (see [playbook/test-maintenance.md](test-maintenance.md)).

## Before committing

1. **Build the site.** `npm run build` must pass. Run `npm run lint`.
2. **If you touched `paper_trading/`, run the updater locally.** `python -m paper_trading.update` and eyeball the regenerated JSON.
3. **If you changed the AI working agreement**, edit `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md` and run `python scripts/sync_ai_docs.py` — never hand-edit `CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`.
4. **Update the docs.** See [playbook/doc-maintenance.md](doc-maintenance.md).
5. **Update the tests.** See [playbook/test-maintenance.md](test-maintenance.md).

## Final mental model

The fastest way to get this repo wrong is to treat the public site as a place where things *happen*. They don't. The site renders pre-computed JSON; all computation and any secret live offline in Tier 2/Tier 3. The four properties to never break:

- The public site is read-only.
- Secrets never enter the repo and the repo never reaches into Darwin.
- Trading is paper-only, deterministic, and disclaimed.
- The data contract changes on both sides at once.

Preserve those and you can change this site safely.
