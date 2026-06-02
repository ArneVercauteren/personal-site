"""Unit tests for PortfolioState — values hand-derived from native_eval.c."""

from __future__ import annotations

import math

import pytest

from paper_trading.portfolio_state import HISTORY_CAP, PortfolioState, is_portfolio_state_feature


def test_turnover_push_and_trailing_mean():
    s = PortfolioState(100.0)
    # First rebalance from cash into 50/50 → turnover = 1.0
    assert s.push_turnover({"A": 0.5, "B": 0.5}, {}) == pytest.approx(1.0)
    # No change → turnover 0.0
    assert s.push_turnover({"A": 0.5, "B": 0.5}, {"A": 0.5, "B": 0.5}) == pytest.approx(0.0)
    # trailing mean over last 2 = (1.0 + 0.0) / 2
    out = s.scalars_for({"trailing_portfolio_turnover_2"}, equity=100.0, weights={})
    assert out["trailing_portfolio_turnover_2"] == pytest.approx(0.5)
    # window 1 → last value only
    out = s.scalars_for({"trailing_portfolio_turnover_1"}, equity=100.0, weights={})
    assert out["trailing_portfolio_turnover_1"] == pytest.approx(0.0)


def test_turnover_partial_change():
    s = PortfolioState(100.0)
    # 0.5/0.5 -> 0.7/0.3 : |0.2| + |0.2| = 0.4
    s.push_turnover({"A": 0.5, "B": 0.5}, {})  # 1.0
    t = s.push_turnover({"A": 0.7, "B": 0.3}, {"A": 0.5, "B": 0.5})
    assert t == pytest.approx(0.4)


def test_trailing_volatility_is_sample_std():
    s = PortfolioState(100.0)
    for r in (0.1, 0.2, 0.3):
        s.push_period_return(r)
    out = s.scalars_for({"trailing_portfolio_volatility_3"}, equity=100.0, weights={})
    # sample std (ddof=1) of [.1,.2,.3] = 0.1
    assert out["trailing_portfolio_volatility_3"] == pytest.approx(0.1)


def test_trailing_volatility_single_point_is_zero():
    s = PortfolioState(100.0)
    s.push_period_return(0.05)
    out = s.scalars_for({"trailing_portfolio_volatility_3"}, equity=100.0, weights={})
    assert out["trailing_portfolio_volatility_3"] == 0.0


def test_recent_hit_rate():
    s = PortfolioState(100.0)
    for r in (0.1, -0.2, 0.3, -0.4):
        s.push_period_return(r)
    out = s.scalars_for({"recent_hit_rate_4"}, equity=100.0, weights={})
    assert out["recent_hit_rate_4"] == pytest.approx(0.5)
    # window 2 → last two returns (0.3, -0.4) → one hit
    out = s.scalars_for({"recent_hit_rate_2"}, equity=100.0, weights={})
    assert out["recent_hit_rate_2"] == pytest.approx(0.5)


def test_window_exceeds_count_uses_count():
    s = PortfolioState(100.0)
    s.push_period_return(0.1)
    s.push_period_return(0.3)
    # window 100 but only 2 entries → mean over 2
    out = s.scalars_for({"trailing_portfolio_turnover_100"}, equity=100.0, weights={})
    # no turnover pushed → 0
    assert out["trailing_portfolio_turnover_100"] == 0.0


def test_ring_buffer_caps_at_history_cap():
    s = PortfolioState(100.0)
    # push more than the cap; only the last HISTORY_CAP survive
    for i in range(HISTORY_CAP + 20):
        s.push_turnover({"A": float(i)}, {})  # turnover = |i - 0| = i
    # huge window → mean of the last HISTORY_CAP values
    out = s.scalars_for({"trailing_portfolio_turnover_100000"}, equity=100.0, weights={})
    start = (HISTORY_CAP + 20) - HISTORY_CAP
    expected = sum(range(start, HISTORY_CAP + 20)) / HISTORY_CAP
    assert out["trailing_portfolio_turnover_100000"] == pytest.approx(expected)


def test_drawdown_peak_logic():
    s = PortfolioState(100.0)
    assert s.drawdown(100.0) == 0.0  # at seed peak
    s.update_peak(120.0)
    assert s.drawdown(108.0) == pytest.approx((120.0 - 108.0) / 120.0)
    # new high → no drawdown, and peak advances
    assert s.drawdown(130.0) == 0.0
    s.update_peak(130.0)
    assert s.drawdown(130.0) == 0.0


def test_invested_cash_holdings():
    s = PortfolioState(100.0)
    out = s.scalars_for(
        {"invested_fraction", "cash_fraction", "current_holdings_count"},
        equity=100.0,
        weights={"A": 0.3, "B": 0.2},
    )
    assert out["invested_fraction"] == pytest.approx(0.5)
    assert out["cash_fraction"] == pytest.approx(0.5)
    assert out["current_holdings_count"] == pytest.approx(2.0)


def test_invested_fraction_clamped():
    s = PortfolioState(100.0)
    out = s.scalars_for({"invested_fraction", "cash_fraction"}, equity=100.0, weights={"A": 1.5})
    assert out["invested_fraction"] == 1.0
    assert out["cash_fraction"] == 0.0


def test_is_portfolio_state_feature():
    assert is_portfolio_state_feature("current_portfolio_drawdown")
    assert is_portfolio_state_feature("trailing_portfolio_turnover_6")
    assert is_portfolio_state_feature("recent_hit_rate_12")
    assert is_portfolio_state_feature("trailing_portfolio_volatility_3")
    assert not is_portfolio_state_feature("sma_50")
    assert not is_portfolio_state_feature("z60_roc_20")


def test_scalars_only_returns_requested():
    s = PortfolioState(100.0)
    out = s.scalars_for({"invested_fraction"}, equity=100.0, weights={"A": 0.4})
    assert set(out) == {"invested_fraction"}


def test_std_matches_math():
    s = PortfolioState(100.0)
    vals = [0.02, -0.01, 0.05, 0.03, -0.04]
    for v in vals:
        s.push_period_return(v)
    out = s.scalars_for({"trailing_portfolio_volatility_5"}, equity=100.0, weights={})
    mean = sum(vals) / len(vals)
    expected = math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))
    assert out["trailing_portfolio_volatility_5"] == pytest.approx(expected)
