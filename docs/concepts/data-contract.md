# Concept — The data contract

The boundary between Tier 2 (the Python updater that *writes* JSON) and Tier 1 (the site that *reads* it) is a single, small, stable contract: the JSON shape. The **TypeScript types in `lib/data.ts` are the single source of truth** for that shape.

## The rule

- **`lib/data.ts` defines the shape.** The types there describe exactly what `public/data/*.json` contains. The site loads and types its data through this module; nothing else hand-parses the JSON.
- **Writer and reader change together.** If you change a field, you change the Tier-2 writer (`paper_trading/`) and `lib/data.ts` in the **same commit**. A shape change that lands on only one side is a broken contract.
- **Keep it small and stable.** The contract is a coupling point — every field is a thing both tiers must agree on forever. Add fields deliberately; don't leak internal simulator state into the public JSON.

## The files

| File | Tier | Role |
|---|---|---|
| `public/data/portfolio.json` | published | equity curve, stats, and (open only) positions per strategy |
| `public/data/trades.json` | published | trade log (open strategies) |
| `public/data/strategies.json` | published | metadata per deployed strategy |
| `lib/data.ts` | 1 (reader) | typed loaders + the type definitions |
| `paper_trading/update.py` | 2b (writer) | open-strategy JSON, in the public repo |
| private repo `daily.yml` | 2a (writer) | secured sanitized JSON, pushed to the public repo |

How an open strategy computes its weights — a lightweight momentum `signal` or a real Darwin
`formula` (DSL tree) run through the vendored evaluator — is an implementation detail of the
writer. It does **not** change this contract: both paths emit the same `portfolio.json` /
`strategies.json` / `trades.json` shape, so `lib/data.ts` is unaffected.

## `visibility` gates the shape

Every strategy entry carries `visibility: "open" | "secured"`, and that field decides which
fields are allowed. This is a **security boundary** — see
[open-vs-secured-strategies.md](open-vs-secured-strategies.md).

- **open** → may include `positions` (full ticker weights) and a `formula_ref`.
- **secured** → may include `exposure` (aggregate sector/asset-class only). **Must never
  include `positions` or any formula.**

## Example: `portfolio.json` (mixed open + secured)

```json
{
  "as_of": "2026-06-01",
  "base_currency": "USD",
  "strategies": [
    {
      "id": "open_momentum_v1",
      "name": "Momentum (Open)",
      "visibility": "open",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.081, "sharpe": 0.65, "max_dd": -0.12},
      "positions": [{"ticker": "AAPL", "weight": 0.04}],
      "formula_ref": "/writing/open-momentum"
    },
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.094, "sharpe": 0.71, "max_dd": -0.10},
      "exposure": [{"group": "Technology", "weight": 0.32},
                   {"group": "Healthcare", "weight": 0.18}]
    }
  ]
}
```

Notes on the shape:
- Keys are kept **short** (`d`/`v` for date/value) because the equity curve is the largest array — small keys keep the payload CDN-friendly.
- `as_of` is the snapshot date; the site shows it so a reader knows how fresh the data is.
- Money values are plain numbers in `base_currency`; the site formats them via `lib/format.ts`.
- `exposure[].group` is a sector / asset-class label, never a ticker.

## `strategies.json` — per-strategy metadata

A separate file carries non-secret descriptive metadata for every strategy (open and secured),
set when the strategy is deployed from Darwin and shown on the site:

```json
{
  "as_of": "2026-06-01",
  "strategies": [
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "portfolio_size": 100000,
      "base_currency": "USD",
      "rebalance_cadence_days": 42,
      "deployed_on": "2026-05-01",
      "cost_model": {"commission_bps": 1.0, "slippage_bps": 5.0,
                     "spread_ref_price": 50.0, "volume_impact_coef": 0.5,
                     "vol_scaled_cost_enable": true, "vol_cost_k": 0.75,
                     "vol_cost_realized_window": 63, "vol_cost_long_window": 252,
                     "vol_cost_mult_max": 3.0},
      "blurb": "Balanced risk/return king from epoch 7."
    }
  ]
}
```

This metadata is **not sensitive** — it describes *how the sim is run* (capital, cadence, cost
assumptions), not the formula or the basket — so it is published for secured strategies too.
`cost_model` here is the same assumption the Darwin section's Methodology page documents, so the
two stay consistent.

`cost_model` carries the full **Darwin cost model** (`paper_trading/costs.py`): `commission_bps`
and `slippage_bps` are required; `spread_ref_price`, `volume_impact_coef`, and the
`vol_*` crisis-scaling fields are optional and fall back to Darwin's engine defaults. The
simulator charges these as a per-rebalance equity haircut (turnover-scaled commission +
price-scaled slippage + sqrt volume impact), matching how the strategy was backtested in Darwin.

## Changing the contract — checklist

1. Edit the type in `lib/data.ts`.
2. Edit the **open** writer in `paper_trading/` to emit the new shape.
3. Edit the **secured** sanitizer in `paper_trading/secured.py` (`build_secured_entry`) to match
   — and re-confirm `assert_sanitized` still rejects any `positions`/formula on secured entries.
   The private repo's `daily.yml` calls this, so the shape stays locked to `lib/data.ts` here.
4. Update any sample/fixture JSON in `public/data/`.
5. Update the tests that pin the shape (see [playbook/test-maintenance.md](../playbook/test-maintenance.md)).
6. Update this page if the contract's meaning changed.

All in one commit (the private-repo writer in its own repo, kept in lockstep).

## Related

- [open-vs-secured-strategies.md](open-vs-secured-strategies.md) — what `visibility` protects.
- [three-tier-separation.md](three-tier-separation.md) — the contract is the Tier 2 → Tier 1 boundary.
- [subsystems/live-dashboard.md](../subsystems/live-dashboard.md) — the reader side.
- [subsystems/paper-trading-updater.md](../subsystems/paper-trading-updater.md) — the open writer.
- [subsystems/secured-updater.md](../subsystems/secured-updater.md) — the secured (private) writer.

## Source files

- `lib/data.ts` — type definitions + typed loaders (the source of truth) (built).
- `lib/format.ts` — `%`, `$`, date formatting helpers (built).
- `public/data/portfolio.json`, `public/data/trades.json`, `public/data/strategies.json` — the published artifacts (sample data committed).
- `paper_trading/update.py` — the open writer that must match (when built).
