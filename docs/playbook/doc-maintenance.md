# Playbook — Doc maintenance

**If your work invalidates any claim in `docs/`, update the doc in the same change.** Stale docs are worse than no docs.

**Do not add speculative, aspirational, or out-of-scope material just because you touched nearby code.** Keep these docs limited to facts, invariants, and workflows your change actually affects. This repo is young — a stub that honestly says "not built yet" beats a page describing code that doesn't exist.

## The AI instruction files are generated — don't hand-edit them

`CLAUDE.md`, `AGENTS.md`, and `.github/copilot-instructions.md` are rendered from `plans_and_text_files/AI_AGENT_SHARED_INSTRUCTIONS.md` by `python scripts/sync_ai_docs.py`. To change the working agreement, edit the shared source and re-run the script. Editing the generated files directly will be overwritten on the next sync. CI can verify sync with `python scripts/sync_ai_docs.py --check`.

## Triggers that almost always require a doc update

- A new module or directory under `app/`, `components/`, `lib/`, or `paper_trading/`.
- A change to the **data contract** (`lib/data.ts` types / the `public/data/*.json` shape).
- A change to build/deploy commands, the GitHub Actions workflow, or env vars / CI secrets.
- A new deployed strategy, a new dashboard page, or a new chart type.
- A change to the Tier-3 publish step or what it scrubs.
- Anything that shifts one of the six invariants in the [concepts/](../concepts/) tree.

## Where each kind of update goes

| Change | Page(s) to update |
|---|---|
| New module/dir under `app/`, `lib/`, `paper_trading/` | the relevant `subsystems/` page, [reference/file-layout.md](../reference/file-layout.md), [INDEX.md](../INDEX.md) routing if it surfaces a new concept |
| Data-contract shape change | [concepts/data-contract.md](../concepts/data-contract.md) |
| New build/deploy command | [reference/build-and-dev.md](../reference/build-and-dev.md) |
| New env var / CI secret | [reference/env-vars.md](../reference/env-vars.md) |
| New file on disk | [reference/file-layout.md](../reference/file-layout.md) |
| New invariant | new page under [concepts/](../concepts/), linked from [INDEX.md](../INDEX.md) |
| New "how to add X" recipe | new page under [tasks/](../tasks/), linked from [INDEX.md](../INDEX.md) |

## Filling a stub

When you build a feature whose `subsystems/` or `tasks/` page is still a stub: replace the stub with the real content in the same change, and remove the "Status: stub" marker. The stub already states what the page should own — honour that scope.

## Source-file pointers

Every doc page ends with a **"Source files"** section listing the modules it documents. **Do not include line numbers** — they drift. Module and symbol names are stable enough; a reader greps for the line.

## Don't expand cosmetically

When you touch a doc, update only what your change broke. Don't refactor the doc layout while you're there. The structure has a job: keeping the AI's lookup map shallow and the human's mental scaffold clean.

## INDEX.md is special

`INDEX.md` is the routing map — the only file an AI loads up-front. Keep it under ~150 lines. Don't put content in it; only pointers.
