# Personal site and Darwin integration plan

**Created:** 2026-08-24  
**Status:** in progress — ledger, publication, and receiver-side protocol work implemented; Darwin exporter integration remains  
**Scope:** public site, paper-trading record, Darwin deployment boundary, publication pipeline,
product positioning, accessibility, testing, and documentation  
**Relationship to the earlier plan:** preserves the invariants and most work in
`CODEBASE_AND_SITE_IMPROVEMENT_PLAN.md`, but inserts semantic conformance before the ledger and
expands the product and Darwin-integration work.

## Executive decision

Keep the static-first Next.js site, paper-only constraint, dark visual identity, and strict one-way
privacy boundary. Do not add a broker, continuously running backend, or direct runtime dependency
from the public site to the private Darwin repository.

Change the product from an engine brochure with a large backtest viewer into an auditable live
research record. Treat Darwin-to-site deployment as a versioned protocol rather than an informal
JSON handoff. Make the live ledger authoritative, historical replay diagnostic-only, and the public
UI lead with forward evidence.

```text
Darwin research engine
        |
        v
versioned deployment bundle + conformance vectors
        |
        v
incremental append-only paper ledger
        |
        v
validated, sanitized public projections
        |
        v
small static site payloads + downloadable research files
```

## Findings that change the delivery order

### Cadence semantics are not a stable cross-repo contract

The deployed `gen0194` spec carries `rebalance_cadence_unit: trading_days` and a transition anchor,
and this repo tests the legacy schedule through 2026-08-10 before counting 42 observed sessions.
Darwin's exporter emits only `rebalance_cadence_days`, derives `next_rebalance_date` with calendar
arithmetic, and does not emit the unit or anchor. A future export can regress the corrected schedule.

### The site does not consume Darwin's complete current cost model

Darwin exports `execution_max_days`, `execution_participation_rate`,
`execution_delay_risk_coef`, and `execution_overflow_penalty_bps` because its native backtester uses
sliced-execution impact. The public paper engine ignores those fields and applies its older
square-root impact calculation. The public claim that forward tracking uses “the same cost model as
the backtests” is therefore stronger than the implementation supports.

### Parity is optional and narrower than the real protocol

The parity suite covers a small group of stateless selection formulas plus one prior-weight case.
It skips when Darwin cannot be imported, including in public CI, and its helper converts any
import/setup exception into a skip. It does not pin the deployed formula's complete selection,
portfolio-state, calendar, cost, fill, or portfolio-equity behavior.

### Consequence

Do not freeze the current replay into the permanent ledger yet. First make cadence and cost
semantics explicit, add versioned conformance fixtures, and independently verify the migration
checkpoint. Otherwise an immutable ledger could preserve behavior already different from Darwin's
intended behavior.

## Audit of `CODEBASE_AND_SITE_IMPROVEMENT_PLAN.md`

Repository state checked on 2026-08-24:

| Earlier phase | Status | Evidence and remaining gaps |
|---|---|---|
| Phase 0 — cadence and guardrails | **Mostly implemented** | Trading-session migration, next-open fixture, public allowlist, path rejection, payload budget, CI jobs, log cleanup, and chart warning fix are present. Branch protection cannot be verified from the checkout and the earlier plan records it as outstanding. Darwin still lacks explicit cadence-unit/anchor export fields. |
| Phase 1 — immutable ledger | **Not implemented** | No `paper_state/`, `paper_ledger/`, event IDs, correction records, replay reconciliation, or incremental processor. The updater still reconstructs and replaces published open-strategy entries. |
| Phase 2 — point-in-time inputs and schema | **Not implemented** | No versioned JSON Schema, generated runtime validation, universe snapshot history, per-event provenance, or dependency lock/constraints file. TypeScript loaders still cast `JSON.parse` results. |
| Phase 3 — publication/data architecture | **Partially implemented** | Public performance uses an allowlist and `strategies.json` has a 4 MiB budget. Data remains monolithic; large static pages embed detailed curves/analytics; downsampling, full-resolution downloads, and loader memoization are absent. |
| Phase 4 — live-first redesign | **Partially implemented** | Labels, disclaimers, phase shading, live stats, open formulas, secured exposure, and deep analytics exist. The default is still a multi-decade curve; the strategy remains `gen0194` with an empty blurb; freshness, live relative return, current drawdown, observations, schedule status, recent costs, and accessible chart summaries are absent. |
| Phase 5 — operations and maintenance | **Mostly not implemented** | The updater runs twice on weekdays, writes files sequentially, and pushes `[skip ci]` commits. No atomic manifest, shared writer coordination, stale/rebalance alerts, or retry publication exists. Actions use mutable major tags, many docs remain stale, and no concise deployment runbook exists. Log cleanup is complete. |

### CI matrix audit

Implemented:

- Python compilation and unit tests.
- ESLint, TypeScript, and production build.
- Schedule migration tests.
- Secured-publication sanitization.
- Public internal-path scanning and a metadata size budget.

Missing or incomplete:

- Strategy/public/ledger JSON Schema validation.
- Ledger determinism and reconciliation fixtures.
- Full monotonicity, finiteness, accounting, freshness, and manifest data checks.
- Required cross-repo conformance fixtures that cannot silently skip.
- Accessibility automation, frontend unit tests, browser smoke tests, and visual regressions.
- Verified required branch-protection checks.

## Phase A — correctness freeze and semantic conformance

### Work

- Treat the current full-replay updater as legacy behavior; do not use it to create the permanent
  migration checkpoint yet.
- Make live paper execution reproduce Darwin's sliced-execution cost model.
- Add all execution parameters to the public Python and TypeScript cost contracts and implement the
  same per-name volatility, capacity, delay-risk, and overflow behavior.
- Until parity is restored, replace “same cost model” copy with a precise description.
- Extend Darwin's exporter with an explicit cadence object:

  ```json
  {
    "unit": "trading_sessions",
    "interval": 42,
    "anchor_review_session": "2026-08-10",
    "execution": "next_session_open"
  }
  ```

- Remove duplicate interval conversion from `scripts/deploy_to_site.py`; use one canonical Darwin
  function.
- Compute the next review from an explicit exchange/session calendar or leave it to the receiving
  runtime. Never label calendar addition as a trading-session schedule.
- Only a missing optional Darwin checkout may skip local parity. A present but broken checkout must
  fail with the original import error.
- Reconcile all published review dates, fills, costs, positions, and equity through the migration
  boundary.

### Acceptance criteria

- One fixture produces identical review sessions, next-open fills, targets, cost components, cash,
  positions, and closing equity in Darwin and the paper runtime.
- The actual deployed formula is covered, including every portfolio-state feature it uses.
- Unsupported cost/cadence/evaluator versions fail closed.
- A Darwin export cannot omit cadence semantics or restore calendar-day behavior.
- The migration checkpoint has a written reconciliation report and reviewer sign-off.

## Phase B — versioned Darwin deployment protocol

### Bundle contents

Each Darwin deployment produces one immutable bundle containing:

- deployment schema version;
- stable strategy ID and separate public display name;
- formula and formula hash;
- Darwin engine commit/build ID and evaluator semantic version;
- cost-model version and complete parameters;
- eligibility/universe-policy version;
- training cutoff, OOS window, deployment session, and data-source provenance;
- explicit cadence and execution timing;
- portfolio size, capacity policy, and base currency;
- visibility, generated timestamp, and bundle hash;
- deterministic conformance vectors.

### Work

- Define a versioned JSON Schema and matching validated Python and TypeScript representations.
- Validate inside Darwin, at paper-runtime import, before publication, and during the site build.
- Have Darwin produce safe fixture vectors for representative dates: expected eligibility, scores,
  picks, weights, cost breakdowns, and schedule decisions.
- Commit only public-safe fixtures here. Secured strategies run the same protocol privately and
  publish aggregate projections only.
- Document whether Darwin is the internal codename and Astralanx the public product name.

### Acceptance criteria

- Both repos validate the same bundle schema.
- The runtime supports a declared set of evaluator/cost/calendar versions.
- CI runs conformance vectors without importing Darwin and cannot skip them.
- An incompatible deployment fails before site or ledger state changes.
- The one-way privacy boundary remains intact.

## Phase C — append-only ledger and incremental state

### Durable state

```text
paper_state/<strategy-id>.json
paper_ledger/<strategy-id>.jsonl
```

The checkpoint stores schema versions, deployment hash, engine/evaluator versions, last session,
cash, shares, equity, peak, required DSL state, review schedule, and universe/price/formula/cost
hashes.

Ledger events include:

```text
strategy_deployed
session_marked
rebalance_reviewed
targets_computed
fills_applied
costs_charged
correction_proposed
correction_accepted
```

### Work

- Design schemas and pure reconciliation against synthetic fixtures first.
- Build the verified migration checkpoint without replacing the live updater.
- Record legacy public-file hashes in the migration event.
- Switch to unseen-session processing with stable, idempotent event IDs.
- Store price revisions as correction proposals; never mutate old events silently.
- Keep full replay as a non-publishing audit command.
- Make event/checkpoint updates transactional and recoverable.

### Acceptance criteria

- Reprocessing an existing session is a no-op.
- A universe refresh cannot change old reviews, fills, costs, positions, or marks.
- Ledger replay reconciles exactly to the checkpoint.
- An interrupted run cannot leave partial state.
- Every public live figure resolves to events and input hashes.

## Phase D — atomic publication and small data products

### Target layout

```text
public/data/manifest.json
public/data/index.json
public/data/strategies/<id>/summary.json
public/data/strategies/<id>/live.json
public/data/strategies/<id>/analytics.json
public/data/strategies/<id>/rebalances.json
public/data/strategies/<id>/research-full.json
public/data/benchmarks/sp500.json
```

### Work

- Give each writer independent per-strategy paths; stop merging open and secured entries into shared
  arrays.
- Generate into staging, validate everything, and publish the manifest last.
- Validate schemas, visibility, hashes, dates, finiteness, cash/weights, schedules, and size budgets.
- Serialize public ingestion under one workflow/concurrency group or implement safe retry/rebase.
- Publish once after confirmed US-market close; retain manual recovery dispatch.
- Add stale-snapshot, failed-review, and failed-publication alerts.
- Keep dashboard data small and load details only on their routes.
- Downsample display curves and offer hashed full-resolution downloads.
- Memoize validated server-side reads during builds.
- Decide whether bot data should stay on the source branch, move to a data branch, or use low-cost
  object storage.

### Acceptance criteria

- Readers never observe mixed-version files.
- Failed publication leaves the last good manifest active.
- Adding a strategy does not multiply a monolithic payload.
- Dashboard HTML excludes analytics and full rebalance history.
- Full-resolution data remains downloadable and traceable.
- Routine runs do not duplicate same-session deployments.

## Phase E — live-first site redesign

### Dashboard

Default every card to a normalized live window and show:

- live total return rather than short-window annualized CAGR;
- benchmark-relative live return;
- current drawdown;
- live session count and deployment date;
- freshness and last successful mark;
- last review/fill, next review, and sessions remaining;
- invested/cash allocation;
- recent turnover and costs.

Put backtest and OOS material behind an explicit Research History action or tab.

### Strategy detail

- Give `gen0194` a stable human display name while retaining its machine ID.
- Add thesis, expected behavior, risks, suitable environment, and falsification criteria.
- Default to live performance rebased to 100 with a benchmark.
- Separate Live Record, Research History, Methodology, Formula, and Deep Analytics progressively.
- Add a rebalance timeline connecting review, target, fill, turnover, cost, universe, prices, and
  evaluator version.
- Keep open formulas/baskets public and secured strategies aggregate-only.
- Replace metric walls with short interpretations and expandable details.

### Methodology credibility

- Distinguish Tiingo research data from Yahoo forward-paper data.
- Disclose universe revisions, gaps, capacity assumptions, and execution differences.
- Replace line-count vanity metrics with throughput, reproducibility, OOS, test, and live evidence.
- Pair performance claims with benchmarks/environments and give limitations equal prominence.

### Acceptance criteria

- Visitors can quickly identify live start, duration, return, drawdown, benchmark comparison,
  freshness, and next review.
- Backtests cannot be mistaken for forward performance.
- Short live records use observations and total return, not misleading annualization.
- Live figures connect to an auditable event trail.

## Phase F — identity, content, accessibility, and discovery

Make this clearly Arne Vercauteren's personal site, with Astralanx as the flagship project rather
than the identity of the whole site. Suggested primary navigation:

```text
Arne Vercauteren | Astralanx | Live Record | Writing | About
```

Keep Contact in About/footer, Reading secondary, and unfinished Studio/Projects hidden.

### Work

- Change the global name/title hierarchy to the personal identity while preserving project branding.
- Add GitHub, résumé, and relevant professional links.
- Turn the Astralanx write-up into a case study: problem, constraints, architecture, evidence,
  limitations, and lessons.
- Edit public prose for precision, grammar, calibrated claims, and consistent naming.
- Add canonical URLs, Open Graph/Twitter images, sitemap, robots, and structured metadata.
- Add textual chart summaries, downloadable tables, and accessible names/descriptions.
- Test controls, focus, contrast, navigation, and no-chart fallbacks with keyboard/screen readers.
- Add a responsive mobile navigation treatment.

### Acceptance criteria

- The home page is a coherent personal portfolio with one flagship project.
- Social/search metadata identifies the person and correct page.
- Core evidence is understandable without chart interaction.
- Automated accessibility checks and a manual keyboard/screen-reader checklist pass.

## Phase G — maintainability, CI, and documentation

### Work

- Split large formula, strategy, and analytics modules into domain view models, small sections, and
  tested pure derivations.
- Centralize live/research metric derivation.
- Add frontend unit tests for returns, drawdown, benchmark alignment, date windows, turnover, and
  formatting edge cases.
- Add browser smoke tests, axe checks, and a few stable visual snapshots.
- Pin Python dependencies and GitHub Actions to reviewed versions/SHAs.
- Add CI for schemas, conformance, data invariants, payloads, freshness, and manifests.
- Require Python, frontend, conformance, and data-contract jobs in branch protection.
- Remove stale “when built,” placeholder, and scaffold language.
- Fix obsolete script names and the placeholder Darwin GitHub link.
- Reconcile README, overview, layout, site map, and subsystem docs with reality.
- Add contributor/development and operator deployment/recovery runbooks.
- Archive or mark superseded plans.

### Acceptance criteria

- README accurately routes a clean checkout through build, test, deploy, and recovery.
- Active docs no longer describe built code as planned or reference removed scripts.
- Contract failures are caught before data becomes public.
- CI cannot report parity success when required conformance did not run.

## Corrected delivery order

1. Fix cost/cadence mismatches and add fail-closed version fields.
2. Define the deployment schema and Darwin-generated conformance vectors.
3. Reconcile current live history and approve the migration boundary.
4. Test ledger/checkpoint schemas with synthetic data.
5. Create the migration event and switch to incremental processing.
6. Add atomic manifest publication and writer coordination.
7. Split/downsample data and add full-resolution downloads.
8. Ship live-first dashboard and strategy pages.
9. Reposition the personal identity and edit methodology/content.
10. Complete accessibility, metadata, CI, dependency, and documentation ratchets.

## Definition of done

- Live history is append-only and corrections are explicit.
- Darwin deployment is versioned, schema-validated, and backed by required conformance vectors.
- Cadence, selection, fill, cost, and accounting semantics are deliberate and tested.
- Every live figure is traceable to immutable events and input hashes.
- Visibility is validated before publication.
- One atomic manifest identifies a complete public snapshot.
- The dashboard defaults to forward evidence and payloads remain bounded.
- Core pages are accessible without chart interaction.
- The site has a coherent personal identity and calibrated methodology.
- CI and documentation enforce the system that actually exists.

## Explicit non-goals

- Real-money trading, broker connectivity, or intraday execution.
- A continuously running server without demonstrated need.
- Making the public site import or call private Darwin code.
- Publishing secured formulas, positions, or internal paths.
- Rewriting old live events to make a later replay cleaner.
- Replacing the framework or visual system without a measured product reason.
