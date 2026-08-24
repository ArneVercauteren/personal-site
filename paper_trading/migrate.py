"""Create and approve a one-time live-ledger migration candidate.

Generation is read-only with respect to the authoritative ledger. Approval is
an explicit second command so the replay, public-history comparison, hashes,
and checkpoint can be reviewed before the incremental updater trusts them.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import portfolio, prices, universe, update
from .contracts import canonical_json, content_hash, file_hash
from .ledger import LedgerStore, make_event, reconcile_checkpoint, validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_DIR = ROOT / "paper_migration"


def _candidate_path(strategy_id: str) -> Path:
    return CANDIDATE_DIR / f"{strategy_id}.candidate.json"


def generate(strategy_id: str) -> Path:
    specs = update.load_strategy_specs({strategy_id})
    spec = specs[0]
    spec = {**spec, "_universe_snapshot_id": universe.resolve_universe_snapshot_id(spec)}
    public = update.read_json("portfolio.json") or {}
    published = next(
        (item for item in public.get("strategies", []) if item.get("id") == strategy_id), None
    )
    if published is None:
        raise ValueError(f"{strategy_id}: no published history to migrate")
    boundary = public["as_of"]
    end = (pd.Timestamp(boundary) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    long_all = update._fetch_all_prices([spec], end)
    tickers, start = update._spec_fetch_window(spec)
    long = long_all[
        long_all["ticker"].isin(set(tickers))
        & (long_all["date"] >= pd.Timestamp(start))
        & (long_all["date"] <= pd.Timestamp(boundary))
    ].reset_index(drop=True)
    opens, closes = prices.long_to_wide(long)
    raw_closes, dollar_volume = prices.wide_raw_and_dollar_volume(long)
    # Published history predates the sliced-execution fields being honored by
    # this runtime. Reproduce that legacy path through the boundary, then stamp
    # the accepted checkpoint with the current deployment/cost hashes so the
    # new model applies prospectively without rewriting the 2026-08-11 fill.
    replay_spec = {**spec, "cost_model": {
        key: value for key, value in spec["cost_model"].items()
        if not key.startswith("execution_") and key != "impact_lookback_days"
    }}
    result = portfolio.simulate(
        replay_spec, opens, closes, prices_long=long if "formula" in spec else None,
        dollar_volume=dollar_volume, raw_closes=raw_closes,
    )
    if result.as_of != boundary:
        raise ValueError(f"replay ended {result.as_of}, expected migration boundary {boundary}")
    if result.checkpoint is None:
        raise ValueError("simulator produced no checkpoint")
    replay_curve = result.equity_curve
    published_curve = published["equity_curve"]
    replay_dates = [point["d"] for point in replay_curve]
    published_dates = [point["d"] for point in published_curve]
    if replay_dates != published_dates:
        raise ValueError("replay date grid does not match the published history")
    prefix_length = len(spec.get("darwin_equity_curve") or [])
    if replay_curve[:prefix_length] != published_curve[:prefix_length]:
        raise ValueError("authoritative Darwin prefix does not match the published history")

    public_positions = {item["ticker"]: float(item["weight"]) for item in published["positions"]}
    replay_positions = {item["ticker"]: float(item["weight"]) for item in result.positions}
    if set(public_positions) != set(replay_positions):
        raise ValueError("replay holdings differ from the published migration-boundary basket")
    max_weight_delta = max(
        (abs(public_positions[ticker] - replay_positions[ticker]) for ticker in public_positions),
        default=0.0,
    )
    if max_weight_delta > 0.0002:
        raise ValueError(f"replay boundary weights drifted by {max_weight_delta:.6f}")

    public_trades = [
        {key: trade[key] for key in ("d", "ticker", "side", "weight")}
        for trade in (update.read_json("trades.json") or {}).get("trades", [])
        if trade.get("strategy_id") == strategy_id
    ]
    replay_trades = [
        {key: trade[key] for key in ("d", "ticker", "side", "weight")}
        for trade in result.trades
    ]
    if public_trades != replay_trades:
        raise ValueError("replay fill basket does not match the published 2026-08-11 fill")

    published_end = float(published_curve[-1]["v"])
    replay_end = float(result.checkpoint["equity"])
    scale = published_end / replay_end
    exact_match = replay_curve == published_curve
    if not exact_match:
        result.checkpoint["cash"] *= scale
        result.checkpoint["shares"] = {
            ticker: float(quantity) * scale
            for ticker, quantity in result.checkpoint["shares"].items()
        }
        result.checkpoint["equity"] = published_end
        result.checkpoint["peak_equity"] = max(float(point["v"]) for point in published_curve)
        if result.checkpoint.get("equity_at_previous_review") is not None:
            result.checkpoint["equity_at_previous_review"] *= scale
        result.checkpoint["portfolio_state"]["peak_equity"] *= scale
    result.checkpoint.update(portfolio._checkpoint_hashes(spec))
    validate_checkpoint(result.checkpoint)
    reconcile_checkpoint(
        result.checkpoint,
        {
            ticker: float(closes.at[pd.Timestamp(boundary), ticker])
            for ticker in result.checkpoint["shares"]
        },
    )

    legacy_hashes = {
        name: file_hash(update.DATA_DIR / name)
        for name in ("portfolio.json", "trades.json", "strategies.json", "benchmark.json")
    }
    boundary_events = []
    for event in result.ledger_events:
        if event["session"] == result.checkpoint.get("last_review_session") and event["event_type"] in {
            "rebalance_reviewed", "targets_computed",
        }:
            boundary_events.append(event)
        elif event["session"] == "2026-08-11" and event["event_type"] == "fills_applied":
            payload = event["payload"]
            boundary_events.append(make_event(strategy_id, "fills_applied", event["session"], {
                **payload,
                "equity_open": float(payload["equity_open"]) * scale,
                "cash_after": float(payload["cash_after"]) * scale,
                "shares_after": {
                    ticker: float(quantity) * scale
                    for ticker, quantity in payload["shares_after"].items()
                },
                "migration_scaled": not exact_match,
            }))
        elif event["session"] == "2026-08-11" and event["event_type"] == "costs_charged":
            boundary_events.append(make_event(strategy_id, "costs_charged", event["session"], {
                **event["payload"],
                "amount": float(event["payload"]["amount"]) * scale,
                "migration_scaled": not exact_match,
            }))
    boundary_events.append(make_event(strategy_id, "session_marked", boundary, {
        "equity": published_end,
        "cash": result.checkpoint["cash"],
        "shares": result.checkpoint["shares"],
        "price_snapshot_id": result.checkpoint["price_snapshot_id"],
        "migration_boundary": True,
    }))
    events = [
        make_event(strategy_id, "strategy_deployed", spec["deployed_on"], {
            "deployment_hash": result.checkpoint["deployment_hash"],
            "formula_hash": result.checkpoint["formula_hash"],
            "engine_version": result.checkpoint["engine_version"],
        }),
        *boundary_events,
        make_event(strategy_id, "migration_checkpoint", boundary, {
            "legacy_public_hashes": legacy_hashes,
            "checkpoint_hash": content_hash(result.checkpoint),
            "curve_hash": content_hash(published_curve),
            "prospective_cost_model": True,
            "boundary_scale": scale,
            "replay_was_exact": exact_match,
        }),
    ]
    candidate = {
        "strategy_id": strategy_id,
        "boundary": boundary,
        "checkpoint": result.checkpoint,
        "events": events,
        "review": {
            "published_curve_hash": content_hash(published_curve),
            "replayed_curve_hash": content_hash(replay_curve),
            "legacy_file_hashes": legacy_hashes,
            "exact_match": exact_match,
            "boundary_reconciled": True,
            "boundary_scale": scale,
            "max_weight_delta": max_weight_delta,
            "max_equity_delta": max(
                abs(float(left["v"]) - float(right["v"]))
                for left, right in zip(published_curve, replay_curve)
            ),
        },
    }
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _candidate_path(strategy_id)
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote review candidate {path.relative_to(ROOT)}")
    return path


def approve(strategy_id: str, reviewer: str) -> int:
    if not reviewer.strip():
        raise ValueError("--reviewer is required for approval")
    path = _candidate_path(strategy_id)
    candidate = json.loads(path.read_text(encoding="utf-8"))
    if candidate["review"].get("boundary_reconciled") is not True:
        raise ValueError("migration candidate did not pass boundary reconciliation")
    if content_hash(candidate["checkpoint"]) != next(
        event["payload"]["checkpoint_hash"]
        for event in candidate["events"]
        if event["event_type"] == "migration_checkpoint"
    ):
        raise ValueError("candidate checkpoint hash is invalid")
    approval = make_event(strategy_id, "correction_accepted", candidate["boundary"], {
        "kind": "migration_approval",
        "reviewer": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "candidate_hash": content_hash(candidate),
    })
    store = LedgerStore(ROOT)
    count = store.commit(
        strategy_id, [*candidate["events"], approval], candidate["checkpoint"]
    )
    approved_path = CANDIDATE_DIR / f"{strategy_id}.approved.json"
    approved_path.write_text(
        canonical_json({**candidate, "approval_event": approval}) + "\n", encoding="utf-8"
    )
    print(f"approved {strategy_id}: {count} immutable events")
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate or approve a paper-ledger migration")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reviewer")
    args = parser.parse_args(argv)
    if args.approve:
        approve(args.strategy, args.reviewer or "")
    else:
        generate(args.strategy)


if __name__ == "__main__":
    main()
