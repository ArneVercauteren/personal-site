# Playbook — Test maintenance

**If your change shifts a contract a test pins — the data-contract shape, a formatting helper's output, a snapshot fixture — update the test in the same change.**

A test that fails because the contract intentionally moved on is an outdated test, not a regression. Fix the assertion (or replace the fixture with one that still exercises the original intent) instead of suppressing the failure.

## The workflow

1. Run the suite before finishing any non-trivial change (`npm test` for the site once tests exist; `pytest paper_trading/` for the updater).
2. For each failure, decide: is this a real regression in my change, or did a contract move and this test still asserts the old one?
3. If the contract moved: update the assertion to match. If the test's original intent is still valuable (e.g. it pins the JSON shape), keep a companion test that exercises the new shape explicitly.
4. **Never silence a test with `.skip` / `xfail` / `--ignore` / `it.only`-narrowing to make the suite pass.** The only acceptable skips are documented environment gates.
5. If you delete a module, delete its dedicated test in the same change.

## The contracts most worth pinning here

- **The data contract.** A test (either side) that loads a sample `public/data/*.json` and asserts it satisfies the `lib/data.ts` types catches Tier 2 / Tier 1 drift early. If you change the shape, update both the writer's output test and the reader's type/fixture test together. See [concepts/data-contract.md](../concepts/data-contract.md).
- **Formatting helpers** (`lib/format.ts`). Percent/currency/date formatting is easy to break silently; pin representative cases.
- **The simulator's determinism.** Given fixed inputs, `paper_trading` should produce a fixed equity curve. A golden-snapshot test guards [paper-trading-only.md](../concepts/paper-trading-only.md)'s "deterministic and re-runnable" claim.

## Don't refactor the test suite cosmetically

Only fix what your change broke. The suite's structure lets a reader (or CI) locate the right assertion fast; cosmetic refactors invalidate everyone's grep memory.

## Status

No test suite exists yet — this repo is being scaffolded. When the first tests land (the plan's build order reaches the data contract and the updater), this page gets concrete file names. Until then, treat the principles above as the standing agreement.
