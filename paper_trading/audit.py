"""Point-in-time replay auditor. Never writes checkpoints, ledgers, or public data."""

from __future__ import annotations

import argparse
import json

import pandas as pd

from . import portfolio, prices, universe, update
from .contracts import canonical_json, content_hash


ACCOUNTING_EVENTS = {
    "session_marked", "rebalance_reviewed", "targets_computed",
    "fills_applied", "costs_charged",
}


def run(strategy_id: str) -> None:
    spec = update.load_strategy_specs({strategy_id})[0]
    accepted = update.LEDGER_STORE.load_checkpoint(strategy_id)
    if accepted is None:
        raise ValueError(f"{strategy_id}: no accepted checkpoint")
    events = update.LEDGER_STORE.read_events(strategy_id)
    boundary = accepted["last_processed_session"]
    migration = next(
        (event for event in events
         if event["event_type"] == "migration_checkpoint"),
        None,
    )
    if migration is None:
        raise ValueError(f"{strategy_id}: ledger has no reviewed migration boundary")
    migration_boundary = migration["session"]
    approved_path = update.REPO_ROOT / "paper_migration" / f"{strategy_id}.approved.json"
    approved = json.loads(approved_path.read_text(encoding="utf-8"))
    checkpoint = approved["checkpoint"]
    if content_hash(checkpoint) != migration["payload"]["checkpoint_hash"]:
        raise ValueError("approved migration checkpoint hash does not match the ledger")

    public = update.read_json("portfolio.json") or {}
    entry = next(
        (item for item in public.get("strategies", []) if item.get("id") == strategy_id),
        None,
    )
    if entry is None:
        raise ValueError(f"{strategy_id}: public curve is missing")
    curve = [point for point in entry["equity_curve"] if point["d"] <= migration_boundary]
    if content_hash(curve) != migration["payload"]["curve_hash"]:
        raise ValueError("published history before the migration boundary was rewritten")

    review_snapshots = {
        event["session"]: event["payload"]["universe_snapshot_id"]
        for event in events
        if event["event_type"] == "rebalance_reviewed"
        and migration_boundary < event["session"] <= boundary
    }
    memberships = {
        snapshot_id: universe.load_universe_snapshot(snapshot_id, spec)
        for snapshot_id in set(review_snapshots.values()) | {checkpoint["universe_snapshot_id"]}
    }

    if migration_boundary < boundary:
        all_tickers = sorted(
            set(checkpoint.get("shares", {}))
            | set(checkpoint.get("pending_target", {}))
            | {ticker for members in memberships.values() for ticker in members}
        )
        fetch_spec = {**spec, "universe": all_tickers}
        end = (pd.Timestamp(boundary) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        long = update._fetch_all_prices([fetch_spec], end)
        opens, closes = prices.long_to_wide(long)
        raw_closes, dollar_volume = prices.wide_raw_and_dollar_volume(long)
        generated: list[dict] = []
        for day in closes.index[(closes.index > pd.Timestamp(migration_boundary)) & (closes.index <= pd.Timestamp(boundary))]:
            session = day.strftime("%Y-%m-%d")
            snapshot_id = review_snapshots.get(session, checkpoint["universe_snapshot_id"])
            day_spec = {**spec, "_universe_snapshot_id": snapshot_id}
            result = portfolio.simulate_incremental(
                day_spec, checkpoint, curve, opens.loc[:day], closes.loc[:day],
                prices_long=long[long["date"] <= day] if "formula" in spec else None,
                dollar_volume=dollar_volume.loc[:day], raw_closes=raw_closes.loc[:day],
                active_universe=memberships[snapshot_id],
            )
            if result.checkpoint is None:
                raise ValueError("point-in-time audit produced no checkpoint")
            generated.extend(result.ledger_events)
            checkpoint = result.checkpoint
            curve = result.equity_curve

        stored_events = [
            event for event in events
            if migration_boundary < event["session"] <= boundary
            and event["event_type"] in ACCOUNTING_EVENTS
        ]
        if canonical_json(generated) != canonical_json(stored_events):
            raise ValueError("point-in-time replay diverges from immutable ledger events")

    if canonical_json(checkpoint) != canonical_json(accepted):
        raise ValueError("full replay diverges from the accepted ledger checkpoint")
    print(f"point-in-time audit passed for {strategy_id} through {boundary}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit a ledger checkpoint with point-in-time inputs")
    parser.add_argument("--strategy", required=True)
    args = parser.parse_args(argv)
    run(args.strategy)


if __name__ == "__main__":
    main()
