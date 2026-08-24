from __future__ import annotations

import copy

import pytest

from paper_trading.contracts import CONTRACT_VERSION, ContractError, canonical_json
from paper_trading.ledger import (
    LedgerStore, make_event, reconcile_checkpoint, reconcile_ledger_to_checkpoint,
)


def _checkpoint(session="2026-01-02"):
    return {
        "schema_version": CONTRACT_VERSION,
        "strategy_id": "s",
        "last_processed_session": session,
        "cash": 50.0,
        "shares": {"A": 0.5},
        "equity": 100.0,
        "peak_equity": 100.0,
        "portfolio_state": {"peak_equity": 100.0, "turnover_hist": [], "period_return_hist": []},
        "deployment_hash": "d", "formula_hash": "f", "universe_snapshot_id": "u",
        "price_snapshot_id": "p", "cost_model_hash": "c", "engine_version": "e",
    }


def test_ledger_commit_is_idempotent(tmp_path):
    store = LedgerStore(tmp_path)
    event = make_event("s", "session_marked", "2026-01-02", {"equity": 100.0})
    assert store.commit("s", [event], _checkpoint()) == 1
    assert store.commit("s", [event], _checkpoint()) == 0
    assert len(store.read_events("s")) == 1


def test_historical_change_requires_correction(tmp_path):
    store = LedgerStore(tmp_path)
    event = make_event("s", "session_marked", "2026-01-02", {"equity": 100.0})
    store.commit("s", [event], _checkpoint())
    changed = make_event("s", "session_marked", "2026-01-02", {"equity": 99.0})
    with pytest.raises(ContractError, match="record a correction"):
        store.commit("s", [changed], _checkpoint())


def test_checkpoint_cannot_change_without_new_session(tmp_path):
    store = LedgerStore(tmp_path)
    event = make_event("s", "session_marked", "2026-01-02", {"equity": 100.0})
    store.commit("s", [event], _checkpoint())
    changed = copy.deepcopy(_checkpoint())
    changed["cash"] = 49.0
    with pytest.raises(ContractError, match="without a new market session"):
        store.commit("s", [event], changed)


def test_checkpoint_reconciliation():
    reconcile_checkpoint(_checkpoint(), {"A": 100.0})
    with pytest.raises(ContractError, match="does not reconcile"):
        reconcile_checkpoint(_checkpoint(), {"A": 90.0})


def test_ledger_reconciles_to_latest_checkpoint():
    checkpoint = _checkpoint()
    event = make_event("s", "session_marked", "2026-01-02", {
        "cash": 50.0, "equity": 100.0, "shares": {"A": 0.5},
    })
    reconcile_ledger_to_checkpoint([event], checkpoint)
    changed = {**event, "payload": {**event["payload"], "cash": 40.0}}
    with pytest.raises(ContractError, match="cash"):
        reconcile_ledger_to_checkpoint([changed], checkpoint)


def test_interrupted_two_file_commit_recovers_before_read(tmp_path):
    store = LedgerStore(tmp_path)
    event = make_event("s", "session_marked", "2026-01-02", {"equity": 100.0})
    transaction = store.transaction_path("s")
    transaction.parent.mkdir(parents=True)
    transaction.write_text(
        __import__("json").dumps({
            "ledger": canonical_json(event) + "\n",
            "checkpoint": __import__("json").dumps(_checkpoint()) + "\n",
        }),
        encoding="utf-8",
    )
    assert store.load_checkpoint("s") == _checkpoint()
    assert store.read_events("s") == [event]
    assert not transaction.exists()
