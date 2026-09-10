"""Boundary price revisions: the review report and the reviewed acceptance."""

from __future__ import annotations

import pandas as pd
import pytest

from paper_trading import migrate, portfolio, update
from paper_trading.contracts import CONTRACT_VERSION, ENGINE_VERSION, ContractError
from paper_trading.ledger import LedgerStore, make_event, validate_checkpoint

BOUNDARY = "2026-01-02"
ACCEPTED = {"A": 10.0, "B": 20.0}
RAW = {"A": 10.0, "B": 20.0}


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


def _serve(observed: dict, monkeypatch, raw: dict | None = None):
    """Stand in for the vendor at the boundary session.

    `raw` defaults to the accepted raw closes, i.e. "no corporate action", so
    the v1 checkpoint tests below exercise the revision path as before.
    """
    monkeypatch.setattr(
        migrate, "_boundary_price_rows",
        lambda checkpoint, held: (
            pd.Series(observed), pd.Series(RAW if raw is None else raw),
        ),
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


# --- corporate-action re-basing -------------------------------------------------


def _v2_checkpoint():
    """A checkpoint carrying the accepted prices and the raw-close control."""
    day = pd.Timestamp(BOUNDARY)
    return {
        **_checkpoint(),
        "price_snapshot_scope": "held_positions_v2",
        "price_snapshot": dict(ACCEPTED),
        "raw_price_snapshot_id": portfolio._price_snapshot_id(
            day, pd.Series(RAW), ["A", "B"]
        ),
    }


def _v3_checkpoint():
    """A checkpoint with authoritative adjusted and raw maps per ticker."""
    return {
        **_v2_checkpoint(),
        "price_snapshot_scope": "held_positions_v3",
        "raw_price_snapshot": dict(RAW),
    }


def _verify(checkpoint, adj, raw):
    return portfolio._verify_checkpoint_prices(
        checkpoint, pd.Series(adj), raw_row=None if raw is None else pd.Series(raw)
    )


def test_dividend_rebases_instead_of_failing():
    """A distribution moves the adjusted close but not the raw one."""
    rebase = _verify(_v2_checkpoint(), {"A": 9.9, "B": 20.0}, RAW)

    assert isinstance(rebase, portfolio.BoundaryBasisRebase)
    assert rebase.factors["A"] == pytest.approx(0.99)
    assert rebase.factors["B"] == pytest.approx(1.0)


def test_rebase_preserves_the_accepted_mark_exactly():
    checkpoint = _v2_checkpoint()
    rebase = _verify(checkpoint, {"A": 9.9, "B": 20.0}, RAW)
    restated = portfolio.rebase_checkpoint(checkpoint, rebase)

    # The distribution is absorbed as extra shares, which is what marking the
    # whole history on one adjusted basis does implicitly.
    assert restated["shares"]["A"] == pytest.approx(2.0 / 0.99)
    assert restated["shares"]["B"] == pytest.approx(3.0)
    assert restated["cash"] == checkpoint["cash"]
    assert restated["equity"] == checkpoint["equity"]

    marked = restated["cash"] + sum(
        restated["shares"][t] * p for t, p in {"A": 9.9, "B": 20.0}.items()
    )
    assert marked == pytest.approx(checkpoint["equity"])


def test_rebased_checkpoint_verifies_clean_on_the_new_basis():
    checkpoint = _v2_checkpoint()
    rebase = _verify(checkpoint, {"A": 9.9, "B": 20.0}, RAW)
    restated = portfolio.rebase_checkpoint(checkpoint, rebase)

    assert _verify(restated, {"A": 9.9, "B": 20.0}, RAW) is None


def test_marking_forward_without_rebasing_drops_the_distribution():
    """Why the re-base exists, stated as an assertion."""
    checkpoint = _v2_checkpoint()
    naive = checkpoint["cash"] + sum(
        checkpoint["shares"][t] * p for t, p in {"A": 9.9, "B": 20.0}.items()
    )
    assert naive == pytest.approx(99.8)  # 0.2 of value silently gone

    rebase = _verify(checkpoint, {"A": 9.9, "B": 20.0}, RAW)
    restated = portfolio.rebase_checkpoint(checkpoint, rebase)
    rebased = restated["cash"] + sum(
        restated["shares"][t] * p for t, p in {"A": 9.9, "B": 20.0}.items()
    )
    assert rebased == pytest.approx(100.0)


def test_a_moved_raw_close_is_still_a_reviewable_revision():
    """A split or a corrected print changes the raw close too."""
    with pytest.raises(portfolio.BoundaryPriceRevision):
        _verify(_v2_checkpoint(), {"A": 5.0, "B": 20.0}, {"A": 5.0, "B": 20.0})


def test_rebasing_needs_the_raw_control():
    """Without raw closes there is no way to tell an action from a bad print."""
    with pytest.raises(portfolio.BoundaryPriceRevision):
        _verify(_v2_checkpoint(), {"A": 9.9, "B": 20.0}, None)


def test_legacy_checkpoint_without_accepted_prices_still_fails_closed():
    legacy = _checkpoint()  # v1: hash only, no price_snapshot
    with pytest.raises(portfolio.BoundaryPriceRevision):
        _verify(legacy, {"A": 9.9, "B": 20.0}, RAW)


def test_nvdy_shaped_rebase_recovers_the_dropped_dividend():
    """The 2026-08-28 failure, to scale: $0.093 on 99,229.5657 shares."""
    shares, close, dividend = 99229.5657687936, 12.4, 0.093
    factor = (close - dividend) / close
    accepted = {"NVDY": close}
    checkpoint = {
        **_checkpoint(),
        "shares": {"NVDY": shares},
        "cash": 66410575.0961701,
        "equity": 66410575.0961701 + shares * close,
        "price_snapshot_scope": "held_positions_v2",
        "price_snapshot": accepted,
        "price_tickers": ["NVDY"],
        "price_snapshot_id": portfolio._price_snapshot_id(
            pd.Timestamp(BOUNDARY), pd.Series(accepted), ["NVDY"]
        ),
        "raw_price_snapshot_id": portfolio._price_snapshot_id(
            pd.Timestamp(BOUNDARY), pd.Series(accepted), ["NVDY"]
        ),
    }
    observed = {"NVDY": close * factor}

    dropped = checkpoint["equity"] - (checkpoint["cash"] + shares * observed["NVDY"])
    assert dropped == pytest.approx(shares * dividend, rel=1e-9)

    rebase = _verify(checkpoint, observed, accepted)
    restated = portfolio.rebase_checkpoint(checkpoint, rebase)
    marked = restated["cash"] + restated["shares"]["NVDY"] * observed["NVDY"]
    assert marked == pytest.approx(checkpoint["equity"])


@pytest.fixture
def ledger_v2(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "ROOT", tmp_path)
    store = LedgerStore(tmp_path)
    mark = make_event("s", "session_marked", BOUNDARY, {"equity": 100.0})
    store.commit("s", [mark], _v2_checkpoint())
    return store


def test_review_calls_a_distribution_a_rebase_not_a_revision(ledger_v2, monkeypatch):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch, raw=RAW)
    payload = migrate.review_revision("s")

    assert payload["kind"] == "corporate_action_rebase"
    assert payload["factors"] == {"A": pytest.approx(0.99)}


def test_accept_refuses_a_rebase_and_writes_nothing(ledger_v2, monkeypatch, capsys):
    _serve({"A": 9.9, "B": 20.0}, monkeypatch, raw=RAW)

    assert migrate.accept_revision("s", "a reviewer") == 0
    assert "not a revision" in capsys.readouterr().out
    assert len(ledger_v2.read_events("s")) == 1
    assert ledger_v2.load_checkpoint("s") == _v2_checkpoint()


def test_review_still_flags_a_moved_raw_close_for_a_human(ledger_v2, monkeypatch):
    _serve({"A": 5.0, "B": 20.0}, monkeypatch, raw={"A": 5.0, "B": 20.0})
    assert migrate.review_revision("s")["kind"] == "price_revision"


def test_rebase_leaves_untouched_positions_bit_identical():
    """Re-rounding the whole book moved the smallest positions in the last bit."""
    checkpoint = {**_v2_checkpoint(), "shares": {"A": 2.0, "B": 3.000000000000001}}
    rebase = _verify(checkpoint, {"A": 9.9, "B": 20.0}, RAW)
    restated = portfolio.rebase_checkpoint(checkpoint, rebase)

    assert rebase.factors["B"] == 1.0
    assert restated["shares"]["B"] is checkpoint["shares"]["B"]
    assert restated["shares"]["A"] != checkpoint["shares"]["A"]


def test_per_ticker_control_separates_a_dividend_from_an_unrelated_revision():
    """A corrected raw print must not hide a safe distribution on another name."""
    checkpoint = _v3_checkpoint()
    observed_adj = {"A": 9.9, "B": 20.1}
    observed_raw = {"A": 10.0, "B": 20.1}

    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        _verify(checkpoint, observed_adj, observed_raw)

    details = excinfo.value.details
    assert set(details["automatic_rebases"]) == {"A"}
    assert details["automatic_rebases"]["A"]["factor"] == pytest.approx(0.99)
    assert set(details["revisions"]) == {"B"}
    assert details["revisions"]["B"]["equity_impact"] == pytest.approx(0.3)


def test_raw_only_revision_is_reviewed_before_it_can_poison_future_classification():
    checkpoint = _v3_checkpoint()
    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        _verify(checkpoint, ACCEPTED, {"A": 10.0, "B": 20.1})

    assert set(excinfo.value.details["revisions"]) == {"B"}
    assert excinfo.value.details["revisions"]["B"]["equity_impact"] == 0.0


def test_v3_checkpoint_rejects_a_map_that_does_not_match_its_hash():
    checkpoint = _v3_checkpoint()
    checkpoint["raw_price_snapshot"] = {**RAW, "B": 20.1}

    with pytest.raises(ContractError, match="raw price map"):
        validate_checkpoint(checkpoint)


def test_accepting_a_mixed_plan_updates_both_maps_and_rebases_only_the_dividend():
    checkpoint = _v3_checkpoint()
    observed_adj = {"A": 9.9, "B": 20.1}
    observed_raw = {"A": 10.0, "B": 20.1}
    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        _verify(checkpoint, observed_adj, observed_raw)
    payload = {**excinfo.value.details, "checkpoint_hash": "checkpoint"}

    restated = portfolio.accept_boundary_revision(checkpoint, payload)

    assert restated["price_snapshot_scope"] == "held_positions_v3"
    assert restated["price_snapshot"] == observed_adj
    assert restated["raw_price_snapshot"] == observed_raw
    assert restated["shares"]["A"] == pytest.approx(2.0 / 0.99)
    assert restated["shares"]["B"] == checkpoint["shares"]["B"]
    assert restated["cash"] == checkpoint["cash"]
    assert restated["equity"] == checkpoint["equity"]
    # The same basis now verifies, despite preserving the accepted mark. The
    # reviewed B delta enters only when the next session is marked.
    assert _verify(restated, observed_adj, observed_raw) is None


def test_an_accepted_raw_correction_no_longer_poisons_a_later_dividend():
    checkpoint = _v3_checkpoint()
    first_adj = {"A": 9.9, "B": 20.1}
    first_raw = {"A": 10.0, "B": 20.1}
    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        _verify(checkpoint, first_adj, first_raw)
    restated = portfolio.accept_boundary_revision(checkpoint, excinfo.value.details)

    second_adj = {"A": 9.8, "B": 20.1}
    rebase = _verify(restated, second_adj, first_raw)

    assert isinstance(rebase, portfolio.BoundaryBasisRebase)
    assert rebase.revisions == {}
    assert rebase.factors["A"] == pytest.approx(9.8 / 9.9)
    assert rebase.factors["B"] == 1.0


def test_mixed_review_acceptance_records_tickers_and_a_rebase_event(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "ROOT", tmp_path)
    store = LedgerStore(tmp_path)
    mark = make_event("s", "session_marked", BOUNDARY, {"equity": 100.0})
    store.commit("s", [mark], _v3_checkpoint())
    _serve({"A": 9.9, "B": 20.1}, monkeypatch, raw={"A": 10.0, "B": 20.1})

    migrate.accept_revision("s", "a reviewer")

    after = store.load_checkpoint("s")
    assert after["raw_price_snapshot"] == {"A": 10.0, "B": 20.1}
    events = store.read_events("s")
    assert [event["event_type"] for event in events] == [
        "session_marked", "correction_proposed", "correction_accepted", "basis_rebased",
    ]
    approval = events[-2]["payload"]
    assert approval["reviewed_tickers"] == ["B"]
    assert approval["automatic_rebases"] == ["A"]
