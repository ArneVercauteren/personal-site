# Codebase and site improvement plan

**Created:** 2026-08-24  
**Status:** complete — Phases 0–5 implemented and verified on 2026-08-24
**Scope:** public site, open-strategy paper engine, published data contract, CI, and repository hygiene

## Implementation record

Completed and locally verified on 2026-08-24:

- Phase 0: moved `gen0194` to an explicit 42-trading-session cadence after the preserved 2026-08-10
  review, pinned the 2026-10-08/09 review/fill fixture, added allowlisted publishing and path-safety gates,
  and added complete pull-request CI.
- Phase 1: introduced versioned checkpoints in `paper_state/`, immutable JSONL ledgers in `paper_ledger/`,
  stable event ids, exact accounting reconciliation, crash recovery, correction proposals, a reviewed
  migration boundary, an incremental-only updater, and a read-only point-in-time audit command.
- Phase 2: archived hash-addressed universe snapshots, recorded causal OHLCV/formula/universe/cost/engine
  hashes, added JSON Schemas plus matching Python and TypeScript runtime validation, and pinned the complete
  Python environment.
- Phase 3: replaced the frontend's monolithic read path with a content-addressed, manifest-last snapshot
  containing a small index and route-specific live, analytics, research, rebalance, provenance, and benchmark
  payloads. Builds verify every file hash, size, schema, and path-safety rule before reading it.
- Phase 4: made the dashboard and strategy pages live-first, added plain-language strategy context and a
  traceable rebalance timeline, separated research from forward evidence, added downloads and accessible
  chart summaries, and shipped canonical metadata, Open Graph, robots, sitemap, and structured data.
- Phase 5: moved the updater after the US close with bounded retries, coordinated all data writers with one
  concurrency group, added stale-data alerting, pinned Actions, upgraded the frontend to Next.js 16 with zero
  known npm audit findings, self-hosted fonts, removed runtime debris, and added a deployment runbook.

Verification evidence: the committed data/ledger validator and point-in-time audit pass; 132 Python tests
pass (7 skipped optional/native tests); ESLint, TypeScript, the Next.js production build, static-content checks,
and rendered WCAG/keyboard/layout checks pass. The compatibility JSON files remain only as a transition surface
for the independently deployed secured writer; the site itself reads one immutable manifest snapshot.

One repository-host setting cannot be encoded in this codebase: enable branch protection/rulesets on `main`
and require the `paper-trading` and `frontend` jobs. CI defines and enforces both jobs; an administrator must
make them required in GitHub.

## Objective

Make the live paper-strategy record auditable and append-only, make the publication boundary explicit
and small, and make the site lead with forward evidence rather than a large historical simulation.
Preserve the current visual identity and static-first deployment model where they remain useful.

## Non-negotiable invariants

1. Never rewrite an already-published live fill or daily equity point silently.
2. Never publish an internal filesystem path, secret formula, or secured ticker weight.
3. A strategy has one authoritative cadence, expressed with an explicit unit and review anchor.
4. Signal review, next-open fill, costs, universe version, and price snapshot are independently auditable.
5. Data-contract changes are versioned, validated in Python and TypeScript, and backward compatible during migration.
6. The site remains paper-only: no broker credentials, order placement, or implication of real-money execution.
7. Existing live history is preserved unless a labelled correction record explains a migration.

## Risks identified at planning time

- The daily updater replays the full continuation with the latest shared universe. A universe refresh can
  therefore alter earlier simulated holdings and returns.
- The live trade file keeps only the most recent reconstructed rebalance rather than an immutable history.
- The public strategy metadata is a 9.7 MB monolith and contains large `artifacts`/`holdings` payloads the
  TypeScript contract intentionally does not model or display.
- Strategy source JSON can contain internal absolute paths even though the final public snapshot scrubs them.
- JSON readers use TypeScript casts rather than runtime contract validation.
- Scheduled writers can publish without a pull-request CI gate covering Python tests, TypeScript, the site build,
  and public-data invariants.
- The dashboard visually prioritizes a multi-decade compounded backtest over the much shorter forward record.
- Tracked local development logs contain chart sizing warnings and do not belong in the repository.

## Phase 0 — cadence correction and immediate guardrails

### Work

- Preserve legacy `gen0194` review dates through 2026-08-10.
- Count 42 actual price-index sessions after the transition anchor.
- Keep next-open execution semantics unchanged.
- Publish cadence wording as “trading days” and annualize turnover with 252 sessions.
- Replace pass-through performance publishing with an explicit allowlist.
- Reject internal paths in both generated public data and committed open-strategy source files.
- Remove tracked development logs and fix known chart-container warnings.
- Add pull-request CI for Python and frontend checks.

### Acceptance criteria

- No 2026-09-21 review.
- Next review is 2026-10-08 and next-open fill is 2026-10-09.
- Published review history through 2026-08-10 is unchanged.
- `artifacts`, raw `holdings`, and internal paths cannot enter public metadata.
- The public metadata payload shrinks materially without removing any rendered field.
- A pull request cannot merge when contract, path-safety, Python, type, lint, or build checks fail.

## Phase 1 — immutable paper ledger and checkpoints

### Target model

Add two durable records per strategy:

```text
paper_state/<strategy-id>.json
paper_ledger/<strategy-id>.jsonl
```

The checkpoint stores:

- schema and engine version;
- last processed market session;
- cash and share quantities;
- current equity and peak;
- serialized portfolio-state windows needed by the DSL;
- last review date and next scheduled review;
- formula hash, universe snapshot id, price snapshot id, and cost-model hash.

The append-only ledger records events such as:

```text
strategy_deployed
session_marked
rebalance_reviewed
targets_computed
fills_applied
costs_charged
correction_recorded
```

Every event has a stable id, timestamp/session date, input hashes, engine version, and enough information to
reconcile cash, shares, costs, and account equity.

### Migration

1. Treat the currently published 2026-08-11 fill and 2026-08-21 mark as the migration boundary.
2. Build a one-time checkpoint from the verified current simulation.
3. Store a migration event with hashes of the old public files.
4. From that point forward, process only unseen market sessions.
5. Keep full replay as a separate audit command that compares against the ledger but never overwrites it.

### Acceptance criteria

- Re-running an updater for an already-processed session is a no-op.
- A universe refresh cannot alter prior ledger events, fills, or equity marks.
- A price revision produces a labelled correction proposal rather than a silent rewrite.
- Ledger replay reconciles exactly to the latest checkpoint.
- Failure midway through an update cannot publish a partial state.

## Phase 2 — point-in-time inputs and versioned contract

### Work

- Version universe snapshots by effective date and hash.
- Record the universe snapshot used by every rebalance.
- Snapshot or hash the exact OHLCV inputs used for each review and mark.
- Introduce a versioned JSON Schema for strategy specs, public summaries, analytics, checkpoints, and ledger events.
- Generate or validate equivalent Python and TypeScript types from that schema.
- Validate at strategy import, updater startup, before publication, and during the site build.
- Pin Python dependencies with a reproducible lock/constraints file.

### Acceptance criteria

- Every displayed figure can be traced to formula, universe, price, engine, and cost hashes.
- Python and TypeScript reject the same malformed payloads.
- Historical replay uses the point-in-time universe rather than today’s membership.
- CI installs deterministic dependency versions.

## Phase 3 — publication and data architecture

### Target layout

```text
public/data/index.json
public/data/strategies/<id>/summary.json
public/data/strategies/<id>/live.json
public/data/strategies/<id>/analytics.json
public/data/strategies/<id>/rebalances.json
public/data/benchmarks/sp500.json
```

### Work

- Keep the dashboard index small and load detailed files only on their routes.
- Publish only allowlisted fields.
- Remove duplicated diagnostic artifacts and standalone raw holdings exports.
- Downsample long chart series for rendering while offering full-resolution downloads separately.
- Add file-size budgets and payload checks in CI.
- Cache/memoize server-side JSON reads during a build.

### Acceptance criteria

- Adding a strategy does not multiply a single monolithic payload.
- The dashboard does not parse analytics or rebalance history.
- No rendered feature regresses after unused payload removal.
- Full-resolution research data remains downloadable and auditable.

## Phase 4 — live-first product redesign

### Dashboard

Lead with:

- live return and benchmark-relative return;
- current drawdown;
- live observation count and deployment date;
- data freshness and last successful update;
- last review/fill and next scheduled review;
- trading sessions remaining;
- current invested/cash allocation;
- recent fills and estimated costs.

### Strategy page

- Rename machine ids such as `gen0194` with a stable display name while retaining the id internally.
- Add a plain-language strategy thesis, expected behaviour, risks, and failure modes.
- Default charts to normalized live performance; keep training and OOS in clearly separated research views.
- Add a rebalance timeline showing review, target, fill, turnover, costs, universe version, and engine version.
- Keep formula transparency for open strategies and aggregate-only exposure for secured strategies.
- Reduce metric overload through progressive disclosure and short interpretations.

### Accessibility and metadata

- Provide accessible chart summaries and downloadable tables.
- Add keyboard and screen-reader checks for chart controls and rebalance history.
- Add canonical metadata, Open Graph images, sitemap, robots configuration, and structured project metadata.

### Acceptance criteria

- A visitor can identify what is genuinely live within a few seconds.
- Backtest results cannot be mistaken for forward results.
- The next rebalance and data freshness are visible without reading source files.
- Core pages meet automated accessibility checks and remain usable without chart interaction.

## Phase 5 — operations and repository maintenance

### Work

- Run the daily-bar updater once after confirmed US-market close, with retry-on-failure rather than a redundant
  routine morning publish.
- Publish all files atomically from a validated staging directory.
- Add stale-data and failed-rebalance alerts.
- Coordinate open, universe, and secured writers to avoid push races.
- Pin third-party GitHub Actions to reviewed versions or commit hashes.
- Remove tracked runtime logs, generated caches, obsolete plans, and stale “when built” documentation.
- Add a concise contributor/deployment runbook.

### Acceptance criteria

- The site never exposes a mixed-version set of data files.
- Failed jobs alert and leave the last good snapshot intact.
- Routine runs do not create duplicate same-session deployments.
- Repository documentation describes the implementation that actually exists.

## CI matrix

### Python

- `pytest paper_trading/tests -q`
- compile/import smoke test
- strategy-spec schema validation
- public-path and secret scan
- deterministic scheduler and ledger replay fixtures

### Frontend

- ESLint
- `tsc --noEmit`
- production build
- public-data schema validation
- accessibility smoke tests
- selected visual regressions for dashboard and strategy pages

### Data

- monotonic dates and positive finite equity
- weights/cash reconciliation
- valid visibility boundary
- unique ledger event ids
- schedule/fill consistency
- file-size budgets
- freshness and version-manifest consistency

## Delivery order

1. Finish Phase 0 guardrails.
2. Design and test the ledger/checkpoint schemas with synthetic data.
3. Perform the one-time live-state migration.
4. Switch the updater to incremental processing.
5. Split and slim public data.
6. Ship the live-first UX on the stable ledger-backed contract.
7. Tighten operations, accessibility, and repository maintenance.

## Explicitly deferred

- Real brokerage integration or real-money trading.
- Intraday execution; the strategy remains daily-bar/next-open.
- A wholesale visual redesign or replacement of the current design system.
- Rewriting already-published live history merely to make it match a cleaner replay.
