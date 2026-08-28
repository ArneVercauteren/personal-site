"""Append-only paper ledger, checkpoints, hashes, and reconciliation."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contracts import CONTRACT_VERSION, ENGINE_VERSION, ContractError, canonical_json, content_hash

EVENT_TYPES = {
    "strategy_deployed", "migration_checkpoint", "session_marked",
    "rebalance_reviewed", "targets_computed", "fills_applied", "costs_charged",
    "correction_proposed", "correction_accepted", "basis_rebased",
}


def stable_event_id(strategy_id: str, event_type: str, session: str, payload: dict) -> str:
    return content_hash({
        "strategy_id": strategy_id,
        "event_type": event_type,
        "session": session,
        "engine_version": ENGINE_VERSION,
        "payload": payload,
    })[:24]


def make_event(strategy_id: str, event_type: str, session: str, payload: dict) -> dict:
    if event_type not in EVENT_TYPES:
        raise ContractError(f"unsupported ledger event {event_type}")
    event = {
        "schema_version": CONTRACT_VERSION,
        "event_id": stable_event_id(strategy_id, event_type, session, payload),
        "strategy_id": strategy_id,
        "event_type": event_type,
        "session": session,
        "engine_version": ENGINE_VERSION,
        "payload": payload,
    }
    validate_event(event)
    return event


def validate_event(event: dict) -> None:
    if event.get("schema_version") != CONTRACT_VERSION:
        raise ContractError("unsupported ledger schema version")
    if event.get("event_type") not in EVENT_TYPES:
        raise ContractError("invalid ledger event type")
    if event.get("engine_version") != ENGINE_VERSION:
        raise ContractError("unsupported ledger engine version")
    expected = stable_event_id(
        event["strategy_id"], event["event_type"], event["session"], event["payload"]
    )
    if event.get("event_id") != expected:
        raise ContractError("ledger event id does not match its content")


def validate_checkpoint(checkpoint: dict) -> None:
    required = {
        "schema_version", "strategy_id", "last_processed_session", "cash", "shares",
        "equity", "peak_equity", "portfolio_state", "deployment_hash", "formula_hash",
        "universe_snapshot_id", "price_snapshot_id", "cost_model_hash", "engine_version",
    }
    missing = required - set(checkpoint)
    if missing:
        raise ContractError(f"checkpoint missing: {', '.join(sorted(missing))}")
    if checkpoint["schema_version"] != CONTRACT_VERSION:
        raise ContractError("unsupported checkpoint schema version")
    if checkpoint["equity"] <= 0 or checkpoint["peak_equity"] <= 0:
        raise ContractError("checkpoint equity values must be positive")
    if not isinstance(checkpoint["shares"], dict):
        raise ContractError("checkpoint shares must be an object")


def reconcile_checkpoint(checkpoint: dict, close_prices: dict[str, float], tolerance: float = 0.02) -> None:
    validate_checkpoint(checkpoint)
    marked = float(checkpoint["cash"])
    for ticker, quantity in checkpoint["shares"].items():
        if abs(float(quantity)) <= 1e-12:
            continue
        if ticker not in close_prices:
            raise ContractError(f"missing reconciliation price for {ticker}")
        marked += float(quantity) * float(close_prices[ticker])
    if abs(marked - float(checkpoint["equity"])) > tolerance:
        raise ContractError(
            f"checkpoint does not reconcile: marked={marked:.6f}, equity={checkpoint['equity']:.6f}"
        )


def reconcile_ledger_to_checkpoint(events: list[dict], checkpoint: dict, tolerance: float = 0.02) -> None:
    """Verify the last immutable mark is the accounting state in the checkpoint."""
    validate_checkpoint(checkpoint)
    marks = [event for event in events if event["event_type"] == "session_marked"]
    if not marks:
        raise ContractError("ledger has no session mark")
    mark = marks[-1]
    if mark["session"] != checkpoint["last_processed_session"]:
        raise ContractError("latest ledger mark session does not match checkpoint")
    payload = mark["payload"]
    for key in ("cash", "equity"):
        if abs(float(payload[key]) - float(checkpoint[key])) > tolerance:
            raise ContractError(f"latest ledger {key} does not match checkpoint")
    marked_shares = payload.get("shares", {})
    if set(marked_shares) != set(checkpoint["shares"]):
        raise ContractError("latest ledger shares do not match checkpoint tickers")
    for ticker, quantity in checkpoint["shares"].items():
        if abs(float(marked_shares[ticker]) - float(quantity)) > 1e-9:
            raise ContractError(f"latest ledger shares do not match checkpoint for {ticker}")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@dataclass
class LedgerStore:
    root: Path

    def transaction_path(self, strategy_id: str) -> Path:
        return self.root / "paper_state" / ".transactions" / f"{strategy_id}.json"

    def _recover(self, strategy_id: str) -> None:
        """Finish an interrupted two-file commit before serving either record."""
        path = self.transaction_path(strategy_id)
        if not path.exists():
            return
        transaction = json.loads(path.read_text(encoding="utf-8"))
        _atomic_write(self.ledger_path(strategy_id), transaction["ledger"])
        _atomic_write(self.checkpoint_path(strategy_id), transaction["checkpoint"])
        path.unlink()

    def checkpoint_path(self, strategy_id: str) -> Path:
        return self.root / "paper_state" / f"{strategy_id}.json"

    def ledger_path(self, strategy_id: str) -> Path:
        return self.root / "paper_ledger" / f"{strategy_id}.jsonl"

    def load_checkpoint(self, strategy_id: str) -> dict | None:
        self._recover(strategy_id)
        path = self.checkpoint_path(strategy_id)
        if not path.exists():
            return None
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        validate_checkpoint(checkpoint)
        return checkpoint

    def read_events(self, strategy_id: str) -> list[dict]:
        self._recover(strategy_id)
        path = self.ledger_path(strategy_id)
        if not path.exists():
            return []
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        seen: set[str] = set()
        previous = ""
        for event in events:
            validate_event(event)
            if event["event_id"] in seen:
                raise ContractError("duplicate ledger event id")
            if event["session"] < previous:
                raise ContractError("ledger sessions are not monotonic")
            seen.add(event["event_id"])
            previous = event["session"]
        return events

    def commit(self, strategy_id: str, events: Iterable[dict], checkpoint: dict) -> int:
        validate_checkpoint(checkpoint)
        existing = self.read_events(strategy_id)
        previous_checkpoint = self.load_checkpoint(strategy_id)
        known = {event["event_id"] for event in existing}
        occupied = {
            (event["event_type"], event["session"]): event["event_id"]
            for event in existing
            if not event["event_type"].startswith("correction_")
        }
        appended = []
        for event in events:
            validate_event(event)
            if event["strategy_id"] != strategy_id:
                raise ContractError("event strategy does not match ledger")
            key = (event["event_type"], event["session"])
            if (
                not event["event_type"].startswith("correction_")
                and key in occupied
                and occupied[key] != event["event_id"]
            ):
                raise ContractError(
                    f"historical {event['event_type']} changed on {event['session']}; "
                    "record a correction proposal instead"
                )
            if event["event_id"] not in known:
                appended.append(event)
                known.add(event["event_id"])
                if not event["event_type"].startswith("correction_"):
                    occupied[key] = event["event_id"]
        combined = existing + appended
        for left, right in zip(combined, combined[1:]):
            if right["session"] < left["session"]:
                raise ContractError("new event would make ledger non-monotonic")
        # An accepted correction is the one sanctioned way to restate a checkpoint
        # in place: it carries a reviewer and an immutable record of what changed.
        # Without one, a same-session checkpoint edit is a silent history rewrite.
        accepts_correction = any(
            event["event_type"] in {"correction_accepted", "basis_rebased"}
            for event in appended
        )
        if (
            previous_checkpoint is not None
            and previous_checkpoint["last_processed_session"] == checkpoint["last_processed_session"]
            and canonical_json(previous_checkpoint) != canonical_json(checkpoint)
            and not accepts_correction
        ):
            raise ContractError(
                "checkpoint changed without a new market session; record a correction proposal"
            )
        ledger_text = "".join(canonical_json(event) + "\n" for event in combined)
        checkpoint_text = json.dumps(checkpoint, indent=2, sort_keys=True) + "\n"
        transaction = json.dumps({"ledger": ledger_text, "checkpoint": checkpoint_text})
        _atomic_write(self.transaction_path(strategy_id), transaction)
        _atomic_write(self.ledger_path(strategy_id), ledger_text)
        _atomic_write(self.checkpoint_path(strategy_id), checkpoint_text)
        self.transaction_path(strategy_id).unlink()
        return len(appended)
