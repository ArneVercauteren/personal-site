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

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from . import benchmark, portfolio, prices, universe
from .darwin_eval.select_on_date import collect_all_needed_features, required_history_days
from .publish_sanitize import assert_no_internal_paths, scrub_internal_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_DIR = Path(__file__).resolve().parent / "strategies"
DATA_DIR = REPO_ROOT / "public" / "data"

# Extra history before the Yahoo-backed simulation start so the first signal has its full lookback.
WARMUP_DAYS = 400


def _split_strategy_ids(values: list[str] | None = None) -> set[str] | None:
    raw: list[str] = []
    for value in values or []:
        raw.extend(value.split(","))
    for env_name in ("PAPER_TRADING_STRATEGY", "PAPER_TRADING_STRATEGIES"):
        if os.environ.get(env_name):
            raw.extend(os.environ[env_name].split(","))
    ids = {v.strip() for v in raw if v.strip()}
    return ids or None


def load_strategy_specs(strategy_ids: set[str] | None = None) -> list[dict]:
    specs = []
    seen: set[str] = set()
    for path in sorted(STRATEGY_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("visibility") != "open":
            raise ValueError(
                f"{path.name}: only 'open' strategies belong in the public repo; "
                f"got visibility={spec.get('visibility')!r}"
            )
        seen.add(spec["id"])
        if strategy_ids is None or spec["id"] in strategy_ids:
            specs.append(spec)
    if strategy_ids is not None:
        missing = sorted(strategy_ids - seen)
        if missing:
            raise ValueError(f"unknown open strategy id(s): {', '.join(missing)}")
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


def _spec_fetch_window(spec: dict) -> tuple[list[str], str]:
    """The tickers and earliest start date this spec's simulation needs.

    The Yahoo-backed window begins `warmup` days before the simulation curve
    start (the Astralanx prefix's last date when present, else `backfill_start` /
    `deployed_on`), with enough lookback for the longest feature window.
    """
    tickers = universe.resolve_universe(spec)
    curve_start = portfolio.simulation_curve_start(spec)
    if "formula" in spec:
        needed = collect_all_needed_features(spec["formula"], include_exit_root=True)
        # `required_history_days` already converts the longest feature window from
        # trading days to a calendar-day estimate (it multiplies by 1.6 and adds a
        # margin internally), so it's used directly here. Applying that weekend
        # margin a second time only pulled ~1.6x more history than any window needs.
        warmup = max(WARMUP_DAYS, required_history_days(needed) + 30)
    else:
        warmup = WARMUP_DAYS
    start = (pd.Timestamp(curve_start) - pd.Timedelta(days=warmup)).strftime("%Y-%m-%d")
    return tickers, start


def _fetch_all_prices(specs: list[dict], end: str) -> pd.DataFrame:
    """Fetch the OHLCV every spec needs, fetching each ticker exactly once.

    Different strategies often share the same self-refreshing universe, so a
    naive per-strategy fetch would pull the same bars several times. Instead we
    take, for each ticker, the **earliest** start date any spec requires, group
    tickers by that start, and fetch each group once through the polite,
    rate-limited chunked path. The result is sliced per spec by the caller.
    """
    earliest: dict[str, str] = {}
    for spec in specs:
        tickers, start = _spec_fetch_window(spec)
        for t in tickers:
            cur = earliest.get(t)
            if cur is None or start < cur:
                earliest[t] = start

    by_start: dict[str, list[str]] = {}
    for t, start in earliest.items():
        by_start.setdefault(start, []).append(t)

    session = prices.make_limiter_session()
    frames: list[pd.DataFrame] = []
    total = len(earliest)
    print(f"fetching {total} unique tickers in {len(by_start)} date-group(s) "
          f"through {end}")
    for start, tickers in sorted(by_start.items()):
        frames.append(
            prices.get_ohlcv_chunked(sorted(tickers), start, end, session=session)
        )
    return pd.concat(frames, ignore_index=True)


def run(strategy_ids: set[str] | None = None) -> str:
    specs = load_strategy_specs(strategy_ids)
    if not specs:
        print("no open strategies declared; nothing to do")
        return ""
    if strategy_ids is not None:
        print(f"selected strategies: {', '.join(sorted(strategy_ids))}")

    owned_ids = {s["id"] for s in specs}
    portfolio_entries: list[dict] = []
    meta_entries: list[dict] = []
    open_trades: list[dict] = []
    latest_date = ""

    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    # One deduplicated, rate-limited fetch for every ticker any spec needs; each
    # spec then slices its own tickers + window out of this shared frame.
    long_all = _fetch_all_prices(specs, end)

    for spec in specs:
        tickers, start = _spec_fetch_window(spec)
        wanted = set(tickers)
        long = long_all[
            long_all["ticker"].isin(wanted) & (long_all["date"] >= pd.Timestamp(start))
        ].reset_index(drop=True)

        opens, closes = prices.long_to_wide(long)
        raw_closes, dollar_volume = prices.wide_raw_and_dollar_volume(long)
        if "formula" in spec:
            # Real DSL king: the evaluator needs the long OHLCV frame.
            result = portfolio.simulate(
                spec, opens, closes, prices_long=long,
                dollar_volume=dollar_volume, raw_closes=raw_closes,
            )
        else:
            result = portfolio.simulate(
                spec, opens, closes,
                dollar_volume=dollar_volume, raw_closes=raw_closes,
            )
        latest_date = max(latest_date, result.as_of)

        entry = {
            "id": spec["id"],
            "name": spec["name"],
            "visibility": "open",
            "equity_curve": result.equity_curve,
            "stats": result.stats,
            "stats_backtest": result.stats_backtest,
            "stats_live": result.stats_live,
            "live_since": spec["deployed_on"],
            "positions": result.positions,
        }
        # Publish the DSL score tree for open formula-strategies so the site can
        # render it (open formulas are public for auditability; the security
        # boundary lives on the secured side — secured entries never carry it).
        if "formula" in spec:
            entry["formula"] = spec["formula"]
        if spec.get("formula_ref"):
            entry["formula_ref"] = spec["formula_ref"]
        portfolio_entries.append(entry)

        meta_entry = {
            "id": spec["id"],
            "name": spec["name"],
            "visibility": "open",
            "portfolio_size": spec["portfolio_size"],
            "base_currency": spec["base_currency"],
            "rebalance_cadence_days": spec["rebalance_cadence_days"],
            "deployed_on": spec["deployed_on"],
            "cost_model": spec["cost_model"],
            "blurb": spec["blurb"],
        }
        # Optional Astralanx provenance for the detail page: the three single-seed
        # runs (training / OOS / combined) plus king-level liquidity measures.
        # Passed through, but scrubbed first: the exporter's `open_diagnostics`
        # embeds absolute Darwin-repo paths (e.g. `sector_map_source`) that must
        # never reach the public CDN-served JSON. `scrub_internal_paths` redacts
        # them and `assert_no_internal_paths` fails the updater if any remains.
        # See `docs/concepts/separation-from-darwin.md` and `publish_sanitize.py`.
        for key in ("performance", "active_share", "capacity"):
            if spec.get(key) is not None:
                meta_entry[key] = assert_no_internal_paths(scrub_internal_paths(spec[key]))
        meta_entries.append(meta_entry)

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

    benchmark_payload = benchmark.write_live_benchmark_snapshot(end=end)
    benchmark_as_of = benchmark_payload["as_of"]
    print(
        "wrote public/data/benchmark.json "
        f"({len(benchmark_payload['benchmarks'][0]['equity_curve'])} pts, "
        f"as_of={benchmark_as_of})"
    )

    return latest_date


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(
        description="Regenerate open paper-trading JSON snapshots."
    )
    parser.add_argument(
        "--strategy",
        action="append",
        default=[],
        help=(
            "Only update the given open strategy id. May be repeated or "
            "comma-separated. Env: PAPER_TRADING_STRATEGY / PAPER_TRADING_STRATEGIES."
        ),
    )
    args = parser.parse_args(argv)
    strategy_ids = _split_strategy_ids(args.strategy)
    as_of = run(strategy_ids)
    print(f"done; as_of={as_of} (synthetic={prices.use_synthetic()})")
    return as_of


if __name__ == "__main__":
    main()
