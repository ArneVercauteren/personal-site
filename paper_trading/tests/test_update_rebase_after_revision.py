"""Regression coverage for rebasing after a reviewed boundary correction."""

from __future__ import annotations

import pandas as pd
import pytest

from paper_trading import portfolio, update


BOUNDARY = pd.Timestamp("2026-01-02")


def _snapshot_id(prices: dict[str, float]) -> str:
    return portfolio._price_snapshot_id(BOUNDARY, pd.Series(prices), sorted(prices))


def _checkpoint() -> dict:
    adjusted = {"A": 10.0, "B": 20.0}
    raw = {"A": 10.0, "B": 20.0}
    return {
        "strategy_id": "s",
        "last_processed_session": BOUNDARY.strftime("%Y-%m-%d"),
        "cash": 20.0,
        "shares": {"A": 2.0, "B": 3.0},
        "equity": 100.0,
        "price_snapshot_scope": "held_positions_v3",
        "price_tickers": ["A", "B"],
        "price_snapshot": adjusted,
        "raw_price_snapshot": raw,
        "price_snapshot_id": _snapshot_id(adjusted),
        "raw_price_snapshot_id": _snapshot_id(raw),
    }


class _CaptureLedger:
    def __init__(self) -> None:
        self.commits: list[tuple[str, list[dict], dict]] = []

    def commit(self, strategy_id: str, events: list[dict], checkpoint: dict) -> int:
        self.commits.append((strategy_id, events, checkpoint))
        return len(events)


def test_later_dividend_rebase_preserves_reviewed_basis_gap(monkeypatch):
    checkpoint = _checkpoint()

    # First boundary change is mixed: A is a safe adjusted-only rebase while B
    # has a reviewed raw-price correction. Acceptance deliberately preserves the
    # historical equity (100.0) while the accepted price basis marks at 100.3.
    first_adjusted = {"A": 9.9, "B": 20.1}
    first_raw = {"A": 10.0, "B": 20.1}
    with pytest.raises(portfolio.BoundaryPriceRevision) as excinfo:
        portfolio._verify_checkpoint_prices(
            checkpoint,
            pd.Series(first_adjusted),
            raw_row=pd.Series(first_raw),
        )
    accepted = portfolio.accept_boundary_revision(checkpoint, excinfo.value.details)

    accepted_mark = accepted["cash"] + sum(
        accepted["shares"][ticker] * accepted["price_snapshot"][ticker]
        for ticker in accepted["shares"]
    )
    assert accepted["equity"] == pytest.approx(100.0)
    assert accepted_mark == pytest.approx(100.3)

    # A later distribution changes A's adjusted basis again while raw prices are
    # unchanged. The low-level rebase still targets checkpoint["equity"], which
    # exposes the historical correction gap that used to crash the updater.
    second_adjusted = {"A": 9.8, "B": 20.1}
    rebase = portfolio._verify_checkpoint_prices(
        accepted,
        pd.Series(second_adjusted),
        raw_row=pd.Series(first_raw),
    )
    assert rebase is not None
    with pytest.raises(portfolio.BoundaryPriceRevision, match="re-based book"):
        portfolio.rebase_checkpoint(accepted, rebase)

    ledger = _CaptureLedger()
    monkeypatch.setattr(update, "LEDGER_STORE", ledger)
    restated = update._rebase_boundary("s", accepted, BOUNDARY, rebase)

    assert restated["equity"] == accepted["equity"]
    restated_mark = restated["cash"] + sum(
        restated["shares"][ticker] * second_adjusted[ticker]
        for ticker in restated["shares"]
    )
    assert restated_mark == pytest.approx(accepted_mark)
    assert len(ledger.commits) == 1
    assert ledger.commits[0][0] == "s"
    assert ledger.commits[0][1][0]["event_type"] == "basis_rebased"
