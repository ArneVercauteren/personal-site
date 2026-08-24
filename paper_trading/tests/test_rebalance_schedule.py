"""Rebalance cadence tests, including the gen0194 forward-only migration."""

from __future__ import annotations

import pandas as pd
import pytest

from paper_trading import portfolio


def _market_index() -> pd.DatetimeIndex:
    # Labor Day is the only full-market closure between the transition anchor
    # and expected next review. The production scheduler uses downloaded bars
    # in exactly the same way instead of needing an exchange-calendar dependency.
    return pd.bdate_range("2025-12-01", "2026-10-09").drop(pd.Timestamp("2026-09-07"))


def test_calendar_schedule_remains_the_backward_compatible_default():
    dates = portfolio._rebalance_dates(
        _market_index(), pd.Timestamp("2025-12-01"), 42,
    )
    assert [d.strftime("%Y-%m-%d") for d in dates] == [
        "2025-12-01",
        "2026-01-12",
        "2026-02-23",
        "2026-04-06",
        "2026-05-18",
        "2026-06-29",
        "2026-08-10",
        "2026-09-21",
    ]


def test_transition_preserves_history_then_counts_trading_sessions():
    dates = portfolio._rebalance_dates(
        _market_index(),
        pd.Timestamp("2025-12-01"),
        42,
        cadence_unit="trading_days",
        transition_anchor="2026-08-10",
    )
    assert [d.strftime("%Y-%m-%d") for d in dates] == [
        "2025-12-01",
        "2026-01-12",
        "2026-02-23",
        "2026-04-06",
        "2026-05-18",
        "2026-06-29",
        "2026-08-10",
        "2026-10-08",
    ]


def test_trading_day_schedule_without_transition_counts_price_bars():
    index = _market_index()
    dates = portfolio._rebalance_dates(
        index,
        index[0],
        42,
        cadence_unit="trading_days",
    )
    assert dates[:3] == [index[0], index[42], index[84]]


def test_transition_anchor_must_be_an_existing_legacy_review():
    with pytest.raises(ValueError, match="not a legacy review date"):
        portfolio._rebalance_dates(
            _market_index(),
            pd.Timestamp("2025-12-01"),
            42,
            cadence_unit="trading_days",
            transition_anchor="2026-08-11",
        )


def test_transition_review_fills_at_the_next_open(monkeypatch):
    index = _market_index()
    opens = pd.DataFrame(100.0, index=index, columns=["A", "B"])
    closes = opens.copy()
    calls = 0

    def alternating_target(*_args, **_kwargs):
        nonlocal calls
        target = {"A": 1.0} if calls % 2 == 0 else {"B": 1.0}
        calls += 1
        return target

    monkeypatch.setattr(portfolio.signals, "evaluate", alternating_target)
    strategy = {
        "id": "transition_test",
        "name": "Transition test",
        "deployed_on": "2025-12-01",
        "portfolio_size": 100_000,
        "rebalance_cadence_days": 42,
        "rebalance_cadence_unit": "trading_days",
        "rebalance_transition_anchor": "2026-08-10",
        "cost_model": {"commission_bps": 0.0, "slippage_bps": 0.0},
        "signal": {},
    }

    result = portfolio.simulate(strategy, opens, closes)

    assert calls == 8
    assert result.trades
    assert {trade["d"] for trade in result.trades} == {"2026-10-09"}
