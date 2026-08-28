"""Boundary price revisions: the review report and the reviewed acceptance."""

from __future__ import annotations

import pandas as pd
import pytest

from paper_trading import migrate, portfolio, update
from paper_trading.contracts import CONTRACT_VERSION, ENGINE_VERSION
from paper_trading.ledger import LedgerStore, make_event

BOUNDARY = "2026-01-02"
ACCEPTED = {"A": 10.0, "B": 20.0}


def _checkpoint():
    day = pd.Timestamp(BOUNDARY)
    row = pd.Series(ACCEPTED)
    return {
        "schema_version": CONTRACT_VERSION,
        "strategy_id": "s",
        "last_processed_session": BOUNDARY,
        "cash": 20.0,
        "shares": {"A": 2.0, "B": 3.0},
        "equity": 100.0,
        "peak_equity": 100.0,
        "portfolio_state": {"peak_equity": 100.0, "turnover_hist": [], "period_return_hist": []},
        "deployment_hash": "d", "formula_hash": "f", "universe_snapshot_id": "u",
        "price_snapshot_id": portfolio._price_snapshot_id(day, row, ["A", "B"]),
        "price_snapshot_scope": "held_positions_v1",
        "price_tickers": ["A", "B"],
        "cost_model_hash": "c", "engine_version": ENGINE_VERSION,
    }


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "ROOT", tmp_path)
    store = LedgerStore(tmp_path)
    mark = make_event("s", "session_marked", BOUNDARY, {"equity": 100.0})
    store.commit("s", [mark], _checkpoint())
    return store


def _serve(observed: dict, monkeypatch):
    """Stand in for the vendor, returning `observed` on the boundary session."""
    frame = pd.DataFrame([observed], index=[pd.Timestamp(BOUNDARY)])
    monkeypatch.setattr(
        migrate.prices, "get_price_history", lambda tickers, start, end: (frame, frame)
    )


def test_review_reports_nothing_when_the_boundary_still_reconciles(ledger, monkeypatch):
    _serve(ACCEPTED, monkeypatch)
    assert migrate.review_revision("s") is None


def test_review_reports_the_revision_without_writing(ledger, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch)
    payload = migrate.review_revision("s")

    assert payload["kind"] == "price_revision"
    assert payload["accepted_equity"] == 100.0
    # 2 shares of A repriced 10.00 -> 9.90, so the held book marks 0.20 lower.
    assert payload["observed_equity"] == pytest.approx(99.8)
    assert len(ledger.read_events("s")) == 1
    assert ledger.load_checkpoint("s") == _checkpoint()


def test_review_refuses_to_accept_a_missing_price(ledger, monkeypatch):
    _serve({"A": 10.0}, monkeypatch)
    with pytest.raises(ValueError, match="B"):
        migrate.review_revision("s")


def test_accept_restamps_the_basis_and_preserves_accepted_history(ledger, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch)
    before = _checkpoint()

    migrate.accept_revision("s", "a reviewer")

    after = ledger.load_checkpoint("s")
    assert after["price_snapshot_id"] != before["price_snapshot_id"]
    # Accepted accounting is untouched; only the price basis moved.
    for key in ("cash", "shares", "equity", "peak_equity", "last_processed_session"):
        assert after[key] == before[key]

    events = ledger.read_events("s")
    kinds = [event["event_type"] for event in events]
    assert kinds == ["session_marked", "correction_proposed", "correction_accepted"]
    approval = events[-1]["payload"]
    assert approval["reviewer"] == "a reviewer"
    assert approval["proposal_event_id"] == events[-2]["event_id"]
    assert approval["accepted_price_snapshot_id"] == after["price_snapshot_id"]


def test_accepted_basis_lets_the_updater_advance(ledger, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch)
    migrate.accept_revision("s", "a reviewer")

    # What the next scheduled run does before simulating: the same prices that
    # blocked it must now verify clean against the re-stamped checkpoint.
    portfolio._verify_checkpoint_prices(
        ledger.load_checkpoint("s"), pd.Series({"A": 9.9, "B": 20.0})
    )


def test_accept_requires_a_reviewer(ledger, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch)
    with pytest.raises(ValueError, match="reviewer"):
        migrate.accept_revision("s", "   ")


def test_accept_is_idempotent(ledger, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch)
    migrate.accept_revision("s", "a reviewer")
    # The basis now matches, so a second run has nothing to accept.
    assert migrate.accept_revision("s", "a reviewer") == 0
    assert len(ledger.read_events("s")) == 3


def test_proposal_payload_is_stable_across_float_noise():
    """Two runs of the same revision must produce one event id, not two.

    Summation order over the held book is not bit-stable in CI, which is how a
    single revision previously landed as two near-identical proposals.
    """
    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        portfolio._verify_checkpoint_prices(_checkpoint(), pd.Series({"A": 9.9, "B": 20.0}))
    details = excinfo.value.details

    ids = {
        make_event(
            "s", "correction_proposed", BOUNDARY,
            {**details, "observed_equity": round(equity, 6)},
        )["event_id"]
        for equity in (99.80000000000001, 99.79999999999998)
    }
    assert len(ids) == 1


def test_review_required_exits_with_the_non_retryable_status(monkeypatch):
    def boom(_ids):
        raise update.BoundaryReviewRequired("gen0194: price revision recorded")

    monkeypatch.setattr(update, "run", boom)
    with pytest.raises(SystemExit) as excinfo:
        update.main([])
    assert excinfo.value.code == update.EXIT_REVIEW_REQUIRED
