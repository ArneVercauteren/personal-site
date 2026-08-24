# Concept — Three tiers, strictly separated

The architecture is three tiers with a one-way data flow. Getting this boundary right is what keeps the system cheap, safe, and simple.

```
TIER 3 — Darwin engine        (your PC, PRIVATE)
   Runs evolution, picks king strategies.
   Deploys a king ONCE: pushes its scrubbed formula to the private updater repo.
        │   one-way push: JSON only, NO secrets
        ▼
TIER 2 — Paper-trading updaters (GitHub Actions, free)
   ├─ 2a SECURED (PRIVATE repo): holds secret formulas + weights; rebalances and
   │      marks to market; pushes ONLY sanitized curve+stats+exposure to the public repo.
   └─ 2b OPEN    (PUBLIC repo):  runs public formulas; writes full JSON incl. positions.
        │   commits/pushes data/*.json to the Tier-1 repo
        ▼
TIER 1 — Public website        (Next.js on Vercel, free)
   Renders static content + reads the published JSON.
   Auto-deploys on git push.
```

The Tier-2 split exists because of the [open vs secured](open-vs-secured-strategies.md)
strategy classes: secret formulas and weights must never touch the public repo, so secured
strategies are computed in a **private** repo (2a) and only their sanitized performance is
pushed out. Open strategies have nothing to hide and run in the public repo (2b).

## The rules

1. **Data flows one way: outward.** Tier 3 → Tier 2 → Tier 1. Nothing downstream ever calls back upstream. Tier 1 cannot trigger Tier 2; Tier 2 cannot reach into Tier 3's internals.
2. **Only JSON crosses a boundary.** No code imports, no live objects, no database handles. Each boundary is a file/commit of plain JSON conforming to the [data contract](data-contract.md).
3. **Secrets never travel down the chain.** Tier 3 has the Darwin internals and any private keys; it strips them at the publish step. Tier 2 may use a CI secret for price data, but never commits it. Tier 1 has nothing secret at all.

## Why three tiers

- **Tier 3 is heavy and private.** The Darwin engine, its data, and its config stay on your machine. It is never publicly reachable, so it is never an attack surface.
- **Tier 2 is the only thing that "trades"** — and it only trades on paper, in CI, with no public endpoint.
- **Tier 1 is the only public surface** — and it is [read-only](public-site-is-read-only.md), so a compromise yields nothing.

The separation is also what makes the [static-first](static-first.md) design possible: because Tier 2 does the work ahead of time and commits the result, Tier 1 needs no server.

## What each tier owns

| Tier | Lives in | Owns | Never has |
|---|---|---|---|
| 3 — Darwin engine | the Darwin repo / your PC | evolution, king selection, the publish script | any public exposure |
| 2a — secured updater | private repo `personal-site-trading` | secret formulas + weights, rebalance + daily mark, sanitization | a public endpoint; any published ticker weight |
| 2b — open updater | `paper_trading/` + `.github/workflows/` (public) | open-strategy sim + full JSON output | committed secrets |
| 1 — site | `app/`, `components/`, `content/`, `lib/`, `public/data/` | rendering, charts, MDX | trading logic; credentials |

## How to keep it

- A change that needs a secret or causes an external side effect belongs in Tier 2 or 3 — never Tier 1.
- A change to the JSON shape touches the [data contract](data-contract.md): update the Tier-2 writer and the Tier-1 reader (`lib/data.ts`) in the **same** commit.
- The Tier-3 → site coupling is exactly one thing: the publish script that pushes scrubbed king JSON. See [separation-from-darwin.md](separation-from-darwin.md) and [subsystems/darwin-publish.md](../subsystems/darwin-publish.md).

## Related

- [public-site-is-read-only.md](public-site-is-read-only.md)
- [static-first.md](static-first.md)
- [separation-from-darwin.md](separation-from-darwin.md)
- [data-contract.md](data-contract.md)

## Source files

- `paper_trading/`, `paper_state/`, `paper_ledger/` — Tier 2 engine and immutable accounting.
- `public/data/manifest.json` plus `public/data/snapshots/` — the Tier 2 → Tier 1 boundary artifacts.
- Darwin's `site-spec` export — the scrubbed Tier 3 → site strategy-spec boundary.
