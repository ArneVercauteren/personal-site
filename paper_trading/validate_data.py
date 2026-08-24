"""CI/build gate for compatibility data, immutable state, and snapshot budgets."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .contracts import CONTRACT_VERSION, ContractError, file_hash, validate_public_files
from .conformance import validate_all as validate_conformance
from .ledger import LedgerStore, reconcile_ledger_to_checkpoint
from .publish_sanitize import assert_no_internal_paths

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
MAX_BYTES = {
    "index.json": 150_000,
    "summary.json": 500_000,
    "live.json": 2_000_000,
    "analytics.json": 4_000_000,
    "rebalances.json": 2_000_000,
    "research-full.json": 8_000_000,
}


def validate(*, max_age_days: int | None = None) -> None:
    validate_conformance()
    compatibility = {
        name: json.loads((DATA / name).read_text(encoding="utf-8"))
        for name in ("portfolio.json", "strategies.json", "trades.json", "benchmark.json")
    }
    validate_public_files(compatibility)
    assert_no_internal_paths(compatibility)
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != CONTRACT_VERSION:
        raise ContractError("unsupported manifest version")
    snapshot = DATA / "snapshots" / manifest["snapshot_id"]
    if not snapshot.is_dir():
        raise ContractError("manifest snapshot directory is missing")
    for relative, expected in manifest.get("files", {}).items():
        target = snapshot / relative
        if not target.is_file() or target.stat().st_size != expected["bytes"]:
            raise ContractError(f"snapshot size mismatch: {relative}")
        if file_hash(target) != expected["sha256"]:
            raise ContractError(f"snapshot hash mismatch: {relative}")
        budget = next((limit for suffix, limit in MAX_BYTES.items() if relative.endswith(suffix)), None)
        if budget is not None and target.stat().st_size > budget:
            raise ContractError(f"snapshot exceeds {budget}-byte budget: {relative}")
        assert_no_internal_paths(json.loads(target.read_text(encoding="utf-8")))
    if max_age_days is not None:
        age = (date.today() - date.fromisoformat(manifest["as_of"])).days
        if age > max_age_days:
            raise ContractError(f"public snapshot is stale: {age} calendar days old")

    store = LedgerStore(ROOT)
    for checkpoint_path in sorted((ROOT / "paper_state").glob("*.json")):
        strategy_id = checkpoint_path.stem
        checkpoint = store.load_checkpoint(strategy_id)
        events = store.read_events(strategy_id)
        if checkpoint is None or not events:
            raise ContractError(f"{strategy_id}: checkpoint has no ledger")
        marks = [event for event in events if event["event_type"] == "session_marked"]
        if not marks or marks[-1]["session"] != checkpoint["last_processed_session"]:
            raise ContractError(f"{strategy_id}: latest ledger mark does not match checkpoint")
        reconcile_ledger_to_checkpoint(events, checkpoint)
        reviews = {event["session"] for event in events if event["event_type"] == "rebalance_reviewed"}
        targets = {event["session"] for event in events if event["event_type"] == "targets_computed"}
        if reviews != targets:
            raise ContractError(f"{strategy_id}: every review must have one target event")
    print(f"validated snapshot {manifest['snapshot_id'][:12]} as of {manifest['as_of']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-days", type=int)
    args = parser.parse_args(argv)
    validate(max_age_days=args.max_age_days)


if __name__ == "__main__":
    main()
