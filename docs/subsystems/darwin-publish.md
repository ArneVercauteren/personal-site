# Subsystem — Darwin → site publish step (Tier 3)

> **Status: stub.** The publish script isn't written yet. It lives in the **Darwin repo**, not this one. This page states what it will own and the contract it must honour.

## What this will own

The single, one-way coupling between Darwin and this website: a script in the **Darwin** repo that selects which king strategies are "deployed to the live site", scrubs them to portable JSON, and pushes them into this repo's `paper_trading/strategies/`.

## Planned shape (in the Darwin repo)

Adapt existing tooling rather than writing from scratch:

- **`scripts/select_on_date_yf.py`** (wrapping `src/backtest/select_on_date.py`) — already
  evaluates a strategy formula on a given date via pure-Python feature computation + keyless
  yfinance (no feature store, no native engine, no secrets). This is the **rebalance
  evaluator** the secured pipeline reuses; it *is* "option A". `scripts/reconcile_portfolio_to_target.py`
  is a secondary reference for turning picks into weights.
- **`scripts/deploy_to_site.py`** (new) — the one-shot deploy action:
  1. Scrub the chosen king to a portable formula JSON (no internal paths / secrets).
  2. Attach non-secret metadata: `portfolio_size`, `base_currency`, `rebalance_cadence_days`,
     `visibility`, `cost_model`, `blurb` (see [data-contract.md](../concepts/data-contract.md)).
  3. Push formula + metadata into the **private** repo's `strategies/` (secured) — or PR into
     the **public** repo's `paper_trading/strategies/` (open).
  4. Stamp the rebalance cadence: write `rebalance_cadence_days` + `next_rebalance_date` so the
     private repo's daily `rebalance.yml` rebalances this strategy when due (per-strategy
     cadence, one shared workflow). See [secured-updater.md](secured-updater.md).

## The contract it must honour

- **One-way push, JSON only.** Darwin writes JSON into this repo; this repo never calls back into Darwin. See [concepts/three-tier-separation.md](../concepts/three-tier-separation.md).
- **Scrubbed output.** The exported JSON contains the DSL tree + portable metadata only — **no** internal absolute paths, **no** internal-only fields, **no** secrets. See [concepts/separation-from-darwin.md](../concepts/separation-from-darwin.md).
- **This repo never imports Darwin** to read these files. The updater consumes the scrubbed JSON as plain data.

## What this repo guarantees in return

- It treats `paper_trading/strategies/*.json` as an input contract: a stable, documented JSON shape the [updater](paper-trading-updater.md) knows how to evaluate.

## The export format (the exact JSON the site needs)

A deployed strategy is one `*.json` file matching the strategy-spec the updater reads
(`paper_trading/update.py` / the secured `update_secured.py`). Same shape for open and secured;
`visibility` and *where it's pushed* differ. Exact shape:

```json
{
  "id": "balanced_king_v3",
  "name": "Balanced King",
  "visibility": "secured",                       // "open" → public repo; "secured" → private repo
  "blurb": "Balanced risk/return king from epoch 7.",
  "deployed_on": "2026-06-02",                    // export date; sim starts here
  "next_rebalance_date": "2026-07-14",            // deployed_on + cadence (secured only needs this)
  "portfolio_size": 100000,
  "base_currency": "USD",
  "rebalance_cadence_days": 42,
  "cost_model": {                                 // the Darwin run's actual cost config (see below)
    "commission_bps": 5.0, "slippage_bps": 5.0,
    "spread_ref_price": 50.0, "volume_impact_coef": 0.5,
    "vol_scaled_cost_enable": true, "vol_cost_k": 0.75,
    "vol_cost_realized_window": 63, "vol_cost_long_window": 252, "vol_cost_mult_max": 3.0
  },
  "universe": ["AAPL", "MSFT", "..."],            // the strategy's tradable set
  "formula": { "mode": "top_n", "top_n": 8, "kind": "...", "children": [] },  // BOTH open + secured
  "formula_ref": "/projects/darwin"                // open only: link to the public writeup
}
```

**Both open and secured exports carry `formula`** — the updater *runs* the tree, so the file the
private repo holds must contain it. The security boundary is enforced **later**, at publish time:
the secured pipeline strips the formula/positions from the *public snapshot* (`assert_sanitized`),
never letting them reach the public site. The only export-time differences are `visibility` and the
open-only public `formula_ref`. The secured file is kept secret simply by living **only in the
private repo**; the open file's formula is published for auditability.

The `formula` tree is exactly what `paper_trading`'s vendored evaluator already consumes, so the
exporter should reuse Darwin's existing serializer **`src/dsl/serialize.py::to_dict(strategy)`**
(it emits the `{mode, top_n, kind, name, params, children}` tree, including the top-level
selection mode) rather than hand-building JSON.

### cost_model — pull from the run, don't hard-code

To stay faithful to the backtest the king was selected on, the exporter reads the **actual** cost
config of that run, not literals:

| Field | Darwin source |
|---|---|
| `commission_bps` | the run's `--cost-bps` (CLI default **5.0**) |
| `slippage_bps` | the run's `--slip-bps` (CLI default **5.0**) |
| `spread_ref_price`, `volume_impact_coef` | `cfg.financial_realism` (defaults 50.0, 0.5) |
| `vol_scaled_cost_enable`, `vol_cost_k`, `vol_cost_realized_window`, `vol_cost_long_window`, `vol_cost_mult_max` | `cfg.backtest_diag` (defaults true, 0.75, 63, 252, 3.0) |

> **Open decision — impact sizing.** Darwin's volume-impact term sizes against
> `cfg.financial_realism.portfolio_size` (**$1,000,000**), while the live paper sim sizes against
> the strategy's own `portfolio_size` (e.g. $100k). sqrt-impact scales with √size, so a smaller
> book pays less. Either set the deployed `portfolio_size` to match Darwin's, or add a separate
> `impact_portfolio_size` field to `cost_model`. Decide at deploy time; default to the strategy's
> own `portfolio_size` (what it actually trades).

## UI export button (Darwin frontend)

The Darwin UI already has a generic export dropdown — **`ui/frontend/components/ExportMenu.tsx`** —
whose items are either a synchronous backend download (`path`) or an async job. Adding "deploy to
site" is small:

1. **Backend (FastAPI):** `GET /api/strategies/{id}/site-spec` in **`ui/backend/routes/exports.py`**,
   backed by **`ui/backend/exports/site.py`**. It loads the king (`adapters.get_strategy`), uses the
   strategy's round-trippable `raw_json` tree, reads the engine's cost config + `rebalance_days`
   metadata, and returns the spec above as a JSON download. Query params: `visibility=open|secured`,
   `universe` (comma-separated), `portfolio_size`, `commission_bps`, `slippage_bps`, `blurb`,
   `formula_ref`. Both variants include `formula`; secured just omits the public `formula_ref`.
2. **Frontend:** two `ExportItem`s under a "Deploy to site" group in `StrategyDrawer.tsx`'s
   `ExportMenu` — "Open strategy (public repo)" and "Secured strategy (private repo)" — each a
   direct download from the endpoint with the matching `visibility`.
3. **Where it lands:** the downloaded file is dropped into the **public** repo's
   `paper_trading/strategies/` (open) or the **private** repo's `strategies/` (secured). A later
   `scripts/deploy_to_site.py` can automate that placement; the button gives the correct file today.
   `universe` and `portfolio_size` are deploy-time choices the operator finalizes in the file.

**Status: built** (Darwin repo) — `ui/backend/exports/site.py`, the `site-spec` route, and the two
`StrategyDrawer` menu items. This keeps Darwin's UI as the single deploy surface and produces the
*exact* spec the updater already runs — no second format to maintain.

## To fill this in

When `scripts/deploy_to_site.py` / the `fmt=site` endpoint are written (in Darwin), document here:
how a king is marked "deployed", and the push mechanism (commit vs. artifact). Keep the
authoritative implementation notes in the Darwin repo; this page records the *contract* from the
website's side.

## Source files

- Darwin repo: `scripts/deploy_to_site.py` (new, when built), `scripts/select_on_date_yf.py` + `src/backtest/select_on_date.py` (adapted for the rebalance eval).
- Private repo: `strategies/<king>.json` + metadata — the received, scrubbed secured exports.
- This repo: `paper_trading/strategies/*.json` — open exports; `public/data/strategies.json` — published metadata.
