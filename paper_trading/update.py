"""Entry point — regenerate the OPEN-strategy entries of public/data/*.json.

Run locally or by GitHub Actions:

    python -m paper_trading.update

For each open strategy declared in `paper_trading/strategies/*.json` this:
  1. fetches daily bars for its universe (`prices`),
  2. simulates the paper portfolio (`portfolio` + `signals`),
  3. writes its entry into `portfolio.json`, `trades.json`, `strategies.json`.

It is a **merge, not an overwrite**: secured entries (pushed into this repo by
the private updater) are preserved untouched. Only ids owned by this repo's
open strategies are rewritten. This keeps the open and secured writers from
clobbering each other in the shared files — see
`docs/concepts/data-contract.md` and `docs/concepts/open-vs-secured-strategies.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import portfolio, prices
from .darwin_eval.select_on_date import collect_all_needed_features, required_history_days

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_DIR = Path(__file__).resolve().parent / "strategies"
DATA_DIR = REPO_ROOT / "public" / "data"

# Extra history before deployed_on so the first signal has its full lookback.
WARMUP_DAYS = 400


def load_strategy_specs() -> list[dict]:
    specs = []
    for path in sorted(STRATEGY_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("visibility") != "open":
            raise ValueError(
                f"{path.name}: only 'open' strategies belong in the public repo; "
                f"got visibility={spec.get('visibility')!r}"
            )
        specs.append(spec)
    return specs


def read_json(name: str) -> dict | None:
    path = DATA_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def write_json(name: str, payload: dict) -> None:
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def merge_by_id(existing: list[dict], owned: list[dict], owned_ids: set[str]) -> list[dict]:
    """Replace entries whose id we own; keep everyone else (e.g. secured)."""
    preserved = [e for e in existing if e.get("id") not in owned_ids]
    return preserved + owned


def run() -> str:
    specs = load_strategy_specs()
    if not specs:
        print("no open strategies declared; nothing to do")
        return ""

    owned_ids = {s["id"] for s in specs}
    portfolio_entries: list[dict] = []
    meta_entries: list[dict] = []
    open_trades: list[dict] = []
    latest_date = ""

    for spec in specs:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")

        if "formula" in spec:
            # Real DSL king: warm up enough history for the longest feature window.
            needed = collect_all_needed_features(spec["formula"], include_exit_root=True)
            warmup = max(WARMUP_DAYS, int(required_history_days(needed) * 1.6) + 30)
            start = (pd.Timestamp(spec["deployed_on"]) - pd.Timedelta(days=warmup)).strftime("%Y-%m-%d")
            # The evaluator needs the long OHLCV frame.
            long = prices.get_ohlcv(spec["universe"], start, end)
            opens, closes = prices.long_to_wide(long)
            result = portfolio.simulate(spec, opens, closes, prices_long=long)
        else:
            start = (pd.Timestamp(spec["deployed_on"]) - pd.Timedelta(days=WARMUP_DAYS)).strftime("%Y-%m-%d")
            opens, closes = prices.get_price_history(spec["universe"], start, end)
            result = portfolio.simulate(spec, opens, closes)
        latest_date = max(latest_date, result.as_of)

        entry = {
            "id": spec["id"],
            "name": spec["name"],
            "visibility": "open",
            "equity_curve": result.equity_curve,
            "stats": result.stats,
            "positions": result.positions,
        }
        if spec.get("formula_ref"):
            entry["formula_ref"] = spec["formula_ref"]
        portfolio_entries.append(entry)

        meta_entries.append({
            "id": spec["id"],
            "name": spec["name"],
            "visibility": "open",
            "portfolio_size": spec["portfolio_size"],
            "base_currency": spec["base_currency"],
            "rebalance_cadence_days": spec["rebalance_cadence_days"],
            "deployed_on": spec["deployed_on"],
            "cost_model": spec["cost_model"],
            "blurb": spec["blurb"],
        })

        open_trades.extend(dict(strategy_id=spec["id"], **t) for t in result.trades)
        print(f"  {spec['id']}: {result.stats} ({len(result.equity_curve)} pts)")

    # --- portfolio.json (mixed open + secured) ---
    pf = read_json("portfolio.json") or {"base_currency": "USD", "strategies": []}
    pf["base_currency"] = specs[0]["base_currency"]
    pf["as_of"] = max(latest_date, pf.get("as_of", ""))
    pf["strategies"] = merge_by_id(pf.get("strategies", []), portfolio_entries, owned_ids)
    write_json("portfolio.json", pf)

    # --- strategies.json (metadata for all) ---
    meta = read_json("strategies.json") or {"strategies": []}
    meta["as_of"] = max(latest_date, meta.get("as_of", ""))
    meta["strategies"] = merge_by_id(meta.get("strategies", []), meta_entries, owned_ids)
    write_json("strategies.json", meta)

    # --- trades.json (open trade log) ---
    trades = read_json("trades.json") or {"trades": []}
    trades["as_of"] = max(latest_date, trades.get("as_of", ""))
    kept = [t for t in trades.get("trades", []) if t.get("strategy_id") not in owned_ids]
    trades["trades"] = kept + open_trades
    write_json("trades.json", trades)

    return latest_date


if __name__ == "__main__":
    as_of = run()
    print(f"done; as_of={as_of} (synthetic={prices.use_synthetic()})")
